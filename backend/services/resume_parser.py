"""Extract campus-resume fields from PDF text. Never invent facts not present in the source."""

from __future__ import annotations

import base64
import re
from datetime import date
from io import BytesIO
from typing import Any

from pypdf import PdfReader

from backend.services.model_client import HttpModelClient, ModelFailure

MAX_PDF_BYTES = 5 * 1024 * 1024
MAX_TEXT_CHARS = 20000
MAX_PDF_PAGES = 20
MAX_BASE64_CHARS = 4 * ((MAX_PDF_BYTES + 2) // 3)

_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
_BIRTH = re.compile(r"(?:出生(?:日期|年月)?|生日)[:：\s]*(\d{4})\s*[.\-年/]\s*(\d{1,2})(?!\d)(?:\s*[.\-月/]\s*(\d{1,2})(?!\d)日?)?")
_NAME = re.compile(r"(?:姓名|名字)[:：\s]*([\u4e00-\u9fff·]{2,8})")
_GENDER = re.compile(r"(?:性别)[:：\s]*(男|女)")
_ETHNICITY = re.compile(r"(?:民族)[:：\s]*([\u4e00-\u9fff]{1,8})")
_POLITICS = re.compile(r"(?:政治面貌)[:：\s]*([\u4e00-\u9fff]{2,12})")
_ID_NO = re.compile(r"(?:身份证|证件号)[:：\s]*([0-9Xx]{15,18})")
_CITY = re.compile(r"(?:现居(?:住地)?|居住地|所在地)[:：\s]*([^\n]{2,30})")
_HUKOU = re.compile(r"(?:户口(?:所在地)?)[:：\s]*([^\n]{2,30})")
_SCHOOL = re.compile(r"([\u4e00-\u9fff]{2,20}(?:大学|学院|职业技术学院))")
_DEGREE = re.compile(r"(博士|硕士|本科|专科|高中)")
_MAJOR = re.compile(r"(?:专业)(?!排名|方向|课程)[:：\s]+([^\n，,；;]{2,30})")
_EXPECT_ROLE = re.compile(r"(?:求职意向|期望职位|应聘岗位)[:：\s]*([^\n]{2,40})")
_EXPECT_CITY = re.compile(r"(?:期望城市|意向城市)[:：\s]*([^\n]{2,40})")
_DATE = re.compile(r"(20\d{2})\s*[.\-年/]\s*(\d{1,2})")
_AWARD_HEADING = re.compile(
    r"^(?:获奖|荣誉|奖项|竞赛|比赛|学科竞赛)(?:情况|经历|成果|获奖)?$",
)
_CONTEST_MARK = re.compile(
    r"奖|竞赛|比赛|大赛|杯赛|挑战杯|建模|优胜|冠军|亚军|季军|金奖|银奖|铜奖|一等|二等|三等|成功参赛",
)
_STOP = [
    r"项目经历",
    r"实习经历",
    r"工作经历",
    r"专业技能",
    r"技能特长",
    r"(?<![\u3400-\u9fff])技能",
    r"自我评价",
    r"教育经历",
    r"获奖(?:情况|经历)?",
    r"荣誉(?:奖项|称号)?",
    r"奖项",
    r"竞赛经历",
    r"比赛经历",
    r"学科竞赛",
    r"竞赛获奖",
]

_EXTRACT_SYSTEM = """你是简历信息抽取器。只根据用户给出的简历原文填写 JSON，不要编造。
原文没有的字段用空字符串或空数组。日期保留原文精度：缺月只保留年份，不补01月。生日只有完整、有效的年月日才能填写；缺日留空并在summary保留原文。
只输出一个 JSON 对象，字段如下：
{
  "basic": {"name":"","gender":"","birthday":"","ethnicity":"","politics":"","phone":"","email":"","idType":"","idNo":"","city":"","hukou":""},
  "intention": {"projectType":"","expectRole":"","expectCity":"","availability":""},
  "education": [{"school":"","degree":"","major":"","fullTime":"","start":"","end":"","rank":""}],
  "internships": [{"organization":"","title":"","role":"","start":"","end":"","description":""}],
  "projects": [{"organization":"","title":"","role":"","start":"","end":"","description":""}],
  "awards": [{"name":"","issuer":"","date":"","description":""}],
  "extras": {"skills":"","awards":"","summary":""}
}
gender 只能是 男、女 或空。idType 若能判断为身份证则填 居民身份证。projectType 若能判断则用 应届生/实习生/社招，否则空。
fullTime 用 是 或 否 或空。skills 用顿号分隔。
awards 必须覆盖原文中的竞赛、比赛、学科竞赛、挑战杯、数学建模、获奖情况：一场比赛或一项荣誉一条，不要把比赛写进 internships 或 projects。"""


def empty_extracted() -> dict[str, Any]:
    return {
        "basic": {
            "name": "",
            "gender": "",
            "birthday": "",
            "ethnicity": "",
            "politics": "",
            "phone": "",
            "email": "",
            "idType": "",
            "idNo": "",
            "city": "",
            "hukou": "",
        },
        "intention": {"projectType": "", "expectRole": "", "expectCity": "", "availability": ""},
        "education": [],
        "internships": [],
        "projects": [],
        "awards": [],
        "extras": {"skills": "", "awards": "", "summary": ""},
    }


def _first(pattern: re.Pattern[str], text: str, group: int = 1) -> str:
    match = pattern.search(text)
    return match.group(group).strip() if match else ""


def _section(text: str, heading: str, next_headings: list[str]) -> str:
    start = re.search(heading, text)
    if not start:
        return ""
    rest = text[start.end() :]
    end = None
    for item in next_headings:
        found = re.search(item, rest)
        if found and (end is None or found.start() < end):
            end = found.start()
    return rest[:end].strip() if end is not None else rest.strip()


def _parse_award_block(text: str) -> list[dict[str, str]]:
    """Turn a 获奖/竞赛 section into one entry per contest or honor line."""
    awards: list[dict[str, str]] = []
    pending: dict[str, str] | None = None
    for raw in text.splitlines():
        line = raw.strip(" \t·•-—、;；")
        if not line or _AWARD_HEADING.match(line):
            continue
        date = ""
        found_date = _DATE.search(line)
        if found_date:
            date = f"{found_date.group(1)}-{int(found_date.group(2)):02d}"
        is_item = bool(_CONTEST_MARK.search(line))
        if is_item:
            if pending:
                awards.append(pending)
            pending = {
                "name": line[:80],
                "issuer": "",
                "date": date,
                "description": line[:500],
            }
            continue
        if pending:
            pending["description"] = (pending["description"] + " " + line).strip()[:500]
            if date and not pending["date"]:
                pending["date"] = date
            continue
        if len(line) >= 4:
            pending = {"name": line[:80], "issuer": "", "date": date, "description": line[:500]}
    if pending:
        awards.append(pending)
    return awards[:8]


def _harvest_contest_lines(text: str, already: list[dict[str, str]]) -> list[dict[str, str]]:
    """Catch contest lines that never sat under a 获奖/竞赛 heading."""
    known = {item["name"] for item in already}
    extras: list[dict[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip(" \t·•-—、;；")
        if not line or _AWARD_HEADING.match(line):
            continue
        if not re.search(r"竞赛|比赛|大赛|挑战杯|数学建模", line):
            continue
        if re.search(r"项目经历|实习经历|负责开发|实现了", line) and not _CONTEST_MARK.search(line):
            continue
        if any(line[:20] in name or name[:20] in line for name in known if name):
            continue
        date = ""
        found_date = _DATE.search(line)
        if found_date:
            date = f"{found_date.group(1)}-{int(found_date.group(2)):02d}"
        extras.append({"name": line[:80], "issuer": "", "date": date, "description": line[:500]})
        known.add(line[:80])
        if len(already) + len(extras) >= 8:
            break
    if len(already) + len(extras) < 8 and (len(text.splitlines()) <= 3 or any(len(line) > 80 for line in text.splitlines())):
        for match in re.finditer(
            r"(?:20\d{2}[.\-年/]\d{1,2}\s*)?[^。；;\n]{0,28}(?:竞赛|比赛|大赛|挑战杯|数学建模)[^。；;\n]{0,24}",
            text,
        ):
            snippet = match.group(0).strip(" \t·•-—、;；")
            if len(snippet) < 4:
                continue
            if re.search(r"项目经历|实习经历|负责开发", snippet) and not _CONTEST_MARK.search(snippet):
                continue
            if any(snippet[:16] in name or name[:16] in snippet for name in known if name):
                continue
            date = ""
            found_date = _DATE.search(snippet)
            if found_date:
                date = f"{found_date.group(1)}-{int(found_date.group(2)):02d}"
            extras.append({"name": snippet[:80], "issuer": "", "date": date, "description": snippet[:500]})
            known.add(snippet[:80])
            if len(already) + len(extras) >= 8:
                break
    return extras


def extract_resume_from_text(text: str) -> dict[str, Any]:
    """Deterministic field harvest; empty when a fact is not written in the source."""
    result = empty_extracted()
    compact = text.replace("\r", "")
    basic = result["basic"]
    email = _EMAIL.search(compact)
    basic["email"] = email.group(0) if email else ""
    basic["phone"] = _first(_PHONE, compact)
    birth = _BIRTH.search(compact)
    if birth and birth.group(3):
        try:
            basic["birthday"] = date(*(int(birth.group(i)) for i in (1,2,3))).isoformat()
        except ValueError:
            pass
    basic["name"] = _first(_NAME, compact)
    basic["gender"] = _first(_GENDER, compact)
    basic["ethnicity"] = _first(_ETHNICITY, compact)
    basic["politics"] = _first(_POLITICS, compact)
    basic["idNo"] = _first(_ID_NO, compact)
    if basic["idNo"]:
        basic["idType"] = "居民身份证"
    city = _first(_CITY, compact)
    basic["city"] = re.sub(r"\s+", "", city)[:40]
    hukou = _first(_HUKOU, compact)
    basic["hukou"] = re.sub(r"\s+", "", hukou)[:40]

    intention = result["intention"]
    intention["expectRole"] = _first(_EXPECT_ROLE, compact)
    intention["expectCity"] = _first(_EXPECT_CITY, compact)

    school = _first(_SCHOOL, compact)
    if school:
        degree = _DEGREE.search(compact)
        result["education"] = [
            {
                "school": school,
                "degree": degree.group(1) if degree else "",
                "major": _first(_MAJOR, compact),
                "fullTime": "",
                "start": "",
                "end": "",
                "rank": "",
            }
        ]

    intern_text = _section(compact, r"实习经历|工作经历", _STOP)
    if intern_text and len(intern_text) > 8:
        result["internships"] = [
            {
                "organization": intern_text.splitlines()[0][:40],
                "title": "",
                "role": "",
                "start": "",
                "end": "",
                "description": intern_text[:800],
            }
        ]
    project_text = _section(compact, r"项目经历", _STOP)
    if project_text and len(project_text) > 8:
        result["projects"] = [
            {
                "organization": "",
                "title": project_text.splitlines()[0][:40],
                "role": "",
                "start": "",
                "end": "",
                "description": project_text[:800],
            }
        ]
    award_chunks = [
        _section(
            compact,
            r"获奖(?:情况|经历)?|荣誉(?:奖项|称号)?|奖项|竞赛经历|比赛经历|学科竞赛|竞赛获奖|比赛获奖",
            _STOP,
        )
    ]
    awards: list[dict[str, str]] = []
    seen: set[str] = set()
    for chunk in award_chunks:
        if not chunk or len(chunk) < 2:
            continue
        for item in _parse_award_block(chunk):
            key = item["name"]
            if key and key not in seen:
                awards.append(item)
                seen.add(key)
    for item in _harvest_contest_lines(compact, awards):
        awards.append(item)
    if awards:
        result["awards"] = awards[:8]
        result["extras"]["awards"] = "；".join(item["name"] for item in result["awards"])
    skills = _section(compact, r"专业技能|技能特长|(?<![\u3400-\u9fff])技能", _STOP)
    if skills:
        result["extras"]["skills"] = re.sub(r"\s+", "、", skills)[:300].strip("、")
    from backend.services.resume_sections import enrich_sections
    result = enrich_sections(result, compact)
    if birth and not basic['birthday']:
        result['extras']['summary'] = '\n'.join(filter(None, (result['extras']['summary'], birth.group(0))))
    return result


def pdf_bytes_to_text(data: bytes) -> str:
    if len(data) > MAX_PDF_BYTES:
        raise ValueError("PDF 不能超过 5MB")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            raise ValueError('PDF 已加密，请先在本地解除密码保护再上传。')
        count = len(reader.pages)
        if not 1 <= count <= MAX_PDF_PAGES:
            raise ValueError(f'PDF 页数须为1至{MAX_PDF_PAGES}页，请拆分后上传。')
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("无法读取该 PDF，请确认文件未损坏且为标准 PDF") from exc
    pages: list[str] = []
    length = 0
    for index in range(count):
        try:
            page = reader.pages[index]
            text = page.extract_text() or ''
            # An actual empty page is harmless; nonempty drawing/image content without
            # extracted text may hide career evidence, and must not disappear silently.
            contents = page.get_contents() if not text.strip() else None
            if not text.strip() and contents is not None and contents.get_data().strip():
                raise ValueError('该页存在内容但未能提取文字')
        except Exception as exc:
            raise ValueError(f'第{index+1}页未能完整读取文字，请检查损坏、扫描或图片内容；未返回部分结果。') from exc
        length += len(text) + (1 if pages else 0)
        if length > MAX_TEXT_CHARS:
            raise ValueError(f'PDF 文字超过{MAX_TEXT_CHARS}字符，请拆分后上传；未截断内容。')
        pages.append(text)
    text = "\n".join(pages).strip()
    if len(text) < 8:
        raise ValueError("未能从 PDF 抽出文字。扫描件或图片型简历无法识别，请换可复制文字的 PDF。")
    return text


def _sanitize_extracted(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ModelFailure('Model extraction must be an object',retryable=False)
    base = empty_extracted()
    basic_in = payload.get("basic") if isinstance(payload.get("basic"), dict) else {}
    for key in base["basic"]:
        value = basic_in.get(key, "")
        base["basic"][key] = value.strip() if isinstance(value, str) else ""
    if base["basic"]["gender"] not in ("", "男", "女"):
        base["basic"]["gender"] = ""
    intention_in = payload.get("intention") if isinstance(payload.get("intention"), dict) else {}
    for key in base["intention"]:
        value = intention_in.get(key, "")
        base["intention"][key] = value.strip() if isinstance(value, str) else ""
    extras_in = payload.get("extras") if isinstance(payload.get("extras"), dict) else {}
    for key in base["extras"]:
        value = extras_in.get(key, "")
        base["extras"][key] = value.strip() if isinstance(value, str) else ""

    def rows(raw: Any, fields: tuple[str, ...]) -> list[dict[str, str]]:
        if not isinstance(raw, list):
            return []
        out: list[dict[str, str]] = []
        if len(raw)>50:
            raise ModelFailure('Model returned too many resume entries',retryable=False)
        for item in raw:
            if not isinstance(item, dict):
                continue
            row = {field: item[field].strip() if isinstance(item.get(field), str) else "" for field in fields}
            if any(row.values()):
                out.append(row)
        return out

    edu_fields = ("school", "degree", "major", "fullTime", "start", "end", "rank")
    exp_fields = ("organization", "title", "role", "start", "end", "description")
    award_fields = ("name", "issuer", "date", "description")
    base["education"] = rows(payload.get("education"), edu_fields)
    base["internships"] = rows(payload.get("internships"), exp_fields)
    base["projects"] = rows(payload.get("projects"), exp_fields)
    base["awards"] = rows(payload.get("awards"), award_fields)
    if base["awards"] and not base["extras"]["awards"]:
        base["extras"]["awards"] = "；".join(item["name"] for item in base["awards"] if item.get("name"))
    elif not base["awards"] and base["extras"]["awards"]:
        base["awards"] = [{"name": base["extras"]["awards"], "issuer": "", "date": "", "description": ""}]
    return base


def parse_resume_pdf(pdf_base64: str, filename: str, *, parse_mode: str = "offline") -> dict[str, Any]:
    if not isinstance(parse_mode,str) or parse_mode not in {"offline", "dynamic"}:
        raise ValueError("parse_mode must be offline or dynamic")
    if not isinstance(pdf_base64, str) or not pdf_base64.strip():
        raise ValueError("请上传 PDF")
    if not isinstance(filename, str) or not filename.lower().endswith(".pdf"):
        raise ValueError("只接受 .pdf 文件")
    if len(filename)>255 or any(ord(c)<32 for c in filename):
        raise ValueError('文件名过长或包含无效控制字符。')
    if len(pdf_base64)>MAX_BASE64_CHARS:
        raise ValueError('PDF 编码长度超限，文件不能超过5MB。')
    try:
        data = base64.b64decode(pdf_base64, validate=True)
    except Exception as exc:
        raise ValueError("PDF 编码无效") from exc
    if not data.startswith(b"%PDF"):
        raise ValueError("文件不是 PDF")
    text = pdf_bytes_to_text(data)
    rules = extract_resume_from_text(text)
    extractor = "规则抽取"
    notice = "本次使用本地规则抽取，没有向模型服务发送简历；请在经历库核对。"
    client = HttpModelClient() if parse_mode == "dynamic" else None
    if client is not None and not client.api_key:
        notice = "未配置模型密钥，已使用本地规则抽取。"
    if client is not None and client.api_key:
        try:
            modeled = client.complete_json(_EXTRACT_SYSTEM, f"简历文件名：{filename}\n\n简历原文：\n{text}")
            sanitized = _sanitize_extracted(modeled)
            def leaves(value):
                if isinstance(value, dict):
                    return [leaf for child in value.values() for leaf in leaves(child)]
                if isinstance(value, list):
                    return [leaf for child in value for leaf in leaves(child)]
                return [value] if isinstance(value, str) and value.strip() else []
            normalized = lambda value: re.sub(r"[^\w]", "", value.casefold())
            source = normalized(text)
            harvested = {normalized(value) for value in leaves(rules)}
            if not leaves(sanitized):
                raise ModelFailure('Model returned no usable fields',retryable=False)
            if any(normalized(value) not in source and normalized(value) not in harvested for value in leaves(sanitized)):
                raise ModelFailure("Model fields contain text not grounded in the PDF", retryable=False)
            # Model extraction fills missing groups/fields; it cannot erase the
            # complete deterministic result with an empty or shorter response.
            for group in ('basic','intention','extras'):
                for field,value in sanitized[group].items():
                    if not rules[group][field]:rules[group][field]=value
            for group in ('education','internships','projects','awards'):
                if not rules[group]:rules[group]=sanitized[group]
            extractor = "模型抽取"
            notice = "已用模型从 PDF 正文抽字段。请在经历库核对，未出现的信息不要补造。"
        except ModelFailure:
            extractor = "规则抽取（模型不可用）"
            notice = "模型调用失败或结果无效，已保留本地规则抽取结果。请在经历库核对。"
    return {
        "filename": filename,
        "extractor": extractor,
        "notice": notice,
        "char_count": len(text),
        "preview": text[:400],
        "form": rules,
    }
