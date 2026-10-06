"""Conservative PDF resume preview. Extraction never writes an active draft."""
from __future__ import annotations

import io
import re
from typing import Any

from pypdf import PdfReader

MAX_PDF_BYTES = 8 * 1024 * 1024
MAX_PAGES = 20
SECTION = re.compile(r"^(基本信息|教育经历|教育背景|实习经历|工作经历|项目经历|获奖经历|奖项荣誉|竞赛经历|技能特长|自我评价)\s*[:：]?$", re.I)
AWARD = re.compile(r"竞赛|比赛|大赛|挑战赛|奖学金|获奖|一等奖|二等奖|三等奖|特等奖|金奖|银奖|铜奖|冠军|亚军|季军")
RANK = re.compile(r"特等奖|一等奖|二等奖|三等奖|金奖|银奖|铜奖|优胜奖|冠军|亚军|季军")
DATE = re.compile(r"(?<!\d)(20\d{2})[./年-](0?[1-9]|1[0-2])")


def _first(pattern: str, text: str) -> str:
    found = re.search(pattern, text, re.I | re.M)
    return found.group(1).strip() if found else ""


def _section_entries(lines: list[tuple[int, str]], heading: str, prefix: str) -> list[dict[str, str]]:
    content: list[str] = []
    in_section = False
    for _, line in lines:
        if SECTION.fullmatch(line):
            if in_section:
                break
            in_section = line.startswith(heading)
            continue
        if in_section:
            content.append(line)
    if not content:
        return []
    text = "\n".join(content[:30])
    date = DATE.search(text)
    title = content[0][:100]
    return [{"id": f"{prefix}_pdf_001", "organization": "", "title": title,
             "role": title, "start": f"{date.group(1)}-{int(date.group(2)):02d}" if date else "",
             "end": "", "description": text}]


def extract_resume_pdf(data: bytes) -> dict[str, Any]:
    if not data or len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF 文件大小须在 1 字节至 8 MB 之间")
    if not data.startswith(b"%PDF-"):
        raise ValueError("文件不是有效的 PDF")
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted:
            raise ValueError("加密 PDF 暂不支持，请先解密或直接填写经历库")
        if not 0 < len(reader.pages) <= MAX_PAGES:
            raise ValueError("PDF 页数须在 1 至 20 页之间")
        lines = [(index + 1, line.strip()) for index, page in enumerate(reader.pages)
                 for line in (page.extract_text() or "").splitlines() if line.strip()]
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("PDF 无法解析，请检查文件或直接填写经历库") from exc
    if not lines:
        raise ValueError("未提取到文字；扫描版 PDF 暂不支持 OCR，请直接填写经历库")
    text = "\n".join(line for _, line in lines)
    awards = []
    for page, line in lines:
        if SECTION.fullmatch(line) or not AWARD.search(line):
            continue
        award_id = f"award_pdf_{len(awards) + 1:03d}"
        matched_date = DATE.search(line)
        awards.append({"id": award_id, "name": line[:160],
                       "category": "竞赛" if re.search(r"竞赛|比赛|大赛|挑战赛", line) else "荣誉",
                       "organizer": _first(r"主办(?:方|单位)?\s*[:：]\s*([^，,；;]+)", line),
                       "level": _first(r"(国家级|省级|市级|校级)", line),
                       "rank": (RANK.search(line).group(0) if RANK.search(line) else ""),
                       "date": f"{matched_date.group(1)}-{int(matched_date.group(2)):02d}" if matched_date else "",
                       "role": "", "sourcePage": page, "sourceLine": line[:300]})
        if len(awards) >= 30:
            break
    education = []
    for _, line in lines:
        if re.search(r"大学|学院", line) and re.search(r"本科|硕士|博士|专科|软件工程|计算机", line):
            education.append({"id": "edu_pdf_001", "school": _first(r"([^\s，,；;]{2,30}(?:大学|学院))", line),
                              "degree": _first(r"(本科|硕士|博士|专科)", line),
                              "major": _first(r"(?:专业[:：]?\s*)([^\s，,；;]+)", line),
                              "fullTime": "", "start": "", "end": "", "rank": ""})
            break
    basic = {"name": _first(r"(?:^|\n)姓名\s*[:：]\s*([^\s，,；;]{2,12})", text),
             "phone": _first(r"(?<!\d)(1[3-9]\d{9})(?!\d)", text),
             "email": _first(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})", text),
             "city": _first(r"(?:现居住地|现居地)\s*[:：]\s*([^\n，,；;]+)", text)}
    warnings = ["提取结果仅供预览；请核对姓名、日期、竞赛名次和来源后确认替换。"]
    if not any(basic.values()) and not awards and not education:
        warnings.append("自动识别的结构化字段较少，请手动补全。")
    return {"page_count": len(reader.pages), "basic": basic, "education": education,
            "internships": _section_entries(lines, "实习经历", "exp_internship"),
            "projects": _section_entries(lines, "项目经历", "exp_project"),
            "awards": awards, "warnings": warnings,
            "text_preview": text[:2000]}
