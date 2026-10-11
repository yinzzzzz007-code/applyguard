"""Local extractors for evidence workspace files. No cloud OCR/vision calls."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".gif",
    ".pdf",
    ".doc",
    ".docx",
    ".md",
    ".markdown",
}
MAX_FILE_BYTES = 8_000_000
MAX_PAGES = 40
EXTRACTOR_VERSION = "1.0.0"

_AWARD_NAME = re.compile(
    r"((?:校级|省级|国家级|院级)?[\u4e00-\u9fffA-Za-z0-9·]{2,40}(?:竞赛|比赛|大赛|奖学金|奖))",
)
_GRADE = re.compile(r"([一二三特]等奖|金奖|银奖|铜奖|优胜奖)")
_ISSUER = re.compile(r"(?:颁发|主办|承办|单位)[:：\s]*([^\n]{2,40})")
_DATE = re.compile(r"(20\d{2})\s*[.\-年/]\s*(\d{1,2})")
_PERSON = re.compile(r"(?:获奖人|姓名)[:：\s]*([\u4e00-\u9fff·]{2,8})")


@dataclass
class SpanDraft:
    page: int | None = None
    bbox: list[float] | None = None
    line_start: int | None = None
    line_end: int | None = None
    raw_text: str = ""
    extractor: str = "unknown"


@dataclass
class ParseResult:
    state: str  # INDEXED | NEEDS_REVIEW | FAILED
    spans: list[SpanDraft] = field(default_factory=list)
    error: str | None = None
    media_type: str = "application/octet-stream"
    suggested_fields: dict[str, str] = field(default_factory=dict)
    is_conversion: bool = False
    conversion_note: str | None = None
    preview_path: Path | None = None


def extension_of(relative_path: str) -> str:
    return Path(relative_path).suffix.lower()


def is_hidden_path(relative_path: str) -> bool:
    """True if any path segment is a hidden folder/file (starts with '.')."""
    parts = Path(relative_path.replace("\\", "/")).parts
    return any(part.startswith(".") and part not in {".", ".."} for part in parts)


def is_allowed_path(relative_path: str) -> bool:
    path = Path(relative_path.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts:
        return False
    if is_hidden_path(relative_path):
        return False
    return extension_of(relative_path) in ALLOWED_EXTENSIONS


def guess_media_type(relative_path: str) -> str:
    ext = extension_of(relative_path)
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
        ".pdf": "application/pdf",
        ".doc": "application/msword",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
    }.get(ext, "application/octet-stream")


def infer_award_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {
        "recipient": "",
        "award_name": "",
        "grade": "",
        "issuer": "",
        "date": "",
    }
    if m := _PERSON.search(text):
        fields["recipient"] = m.group(1)
    if m := _GRADE.search(text):
        fields["grade"] = m.group(1)
    if m := _AWARD_NAME.search(text):
        fields["award_name"] = m.group(1)
    if m := _ISSUER.search(text):
        fields["issuer"] = m.group(1).strip(" 。.;；")
    if m := _DATE.search(text):
        fields["date"] = f"{m.group(1)}-{int(m.group(2)):02d}"
    return fields


def parse_file(path: Path, relative_path: str, workspace_dir: Path) -> ParseResult:
    ext = extension_of(relative_path)
    try:
        if ext in {".md", ".markdown"}:
            return _parse_markdown(path)
        if ext == ".pdf":
            return _parse_pdf(path)
        if ext in {".doc", ".docx"}:
            return _parse_word(path, relative_path, workspace_dir)
        if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif"}:
            return _parse_image(path, relative_path)
        return ParseResult(state="FAILED", error=f"不支持的扩展名：{ext}")
    except Exception as exc:  # noqa: BLE001 — surface per-file failure
        return ParseResult(state="FAILED", error=f"解析失败：{exc}", media_type=guess_media_type(relative_path))


def _parse_markdown(path: Path) -> ParseResult:
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    spans: list[SpanDraft] = []
    for idx, line in enumerate(lines, start=1):
        if line.strip():
            spans.append(
                SpanDraft(
                    line_start=idx,
                    line_end=idx,
                    raw_text=line,
                    extractor="markdown",
                )
            )
    if not spans and text.strip():
        spans.append(SpanDraft(line_start=1, line_end=max(1, len(lines)), raw_text=text, extractor="markdown"))
    joined = "\n".join(s.raw_text for s in spans)
    return ParseResult(
        state="NEEDS_REVIEW" if joined.strip() else "FAILED",
        spans=spans,
        error=None if joined.strip() else "Markdown 文件为空",
        media_type="text/markdown",
        suggested_fields=infer_award_fields(joined),
    )


def _parse_pdf(path: Path) -> ParseResult:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    if len(reader.pages) > MAX_PAGES:
        return ParseResult(
            state="FAILED",
            error=f"PDF 超过 {MAX_PAGES} 页上限",
            media_type="application/pdf",
        )
    spans: list[SpanDraft] = []
    for page_idx, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if not text:
            spans.append(
                SpanDraft(
                    page=page_idx,
                    raw_text="",
                    extractor="pdf-text-empty",
                )
            )
            continue
        for block in re.split(r"\n{2,}", text):
            block = block.strip()
            if block:
                spans.append(SpanDraft(page=page_idx, raw_text=block, extractor="pdf-text"))
    non_empty = [s for s in spans if s.raw_text.strip()]
    if non_empty:
        joined = "\n".join(s.raw_text for s in non_empty)
        return ParseResult(
            state="NEEDS_REVIEW",
            spans=non_empty,
            media_type="application/pdf",
            suggested_fields=infer_award_fields(joined),
        )

    # Scanned / image-only PDF → local OCR
    ocr_spans, ocr_error = _run_local_ocr(path)
    if ocr_spans:
        joined = "\n".join(s.raw_text for s in ocr_spans)
        return ParseResult(
            state="NEEDS_REVIEW",
            spans=ocr_spans,
            media_type="application/pdf",
            suggested_fields=infer_award_fields(joined),
        )
    return ParseResult(
        state="FAILED",
        spans=spans,
        error=ocr_error
        or "未提取到文本（可能为扫描件）。请安装本地 OCR 后点「重新识别」。",
        media_type="application/pdf",
        suggested_fields={},
    )


def _parse_word(path: Path, relative_path: str, workspace_dir: Path) -> ParseResult:
    ext = extension_of(relative_path)
    media = guess_media_type(relative_path)
    if ext == ".doc":
        # Binary .doc needs LibreOffice (or save-as .docx)
        converted = _libreoffice_to_pdf(path, workspace_dir)
        if converted is None:
            return ParseResult(
                state="FAILED",
                error=(
                    "无法解析 .doc：未找到 LibreOffice。"
                    "请安装 LibreOffice，或在 Word 中另存为 .docx / 导出为 PDF、图片后再导入。"
                ),
                media_type=media,
            )
        pdf_result = _parse_pdf(converted)
        pdf_result.is_conversion = True
        pdf_result.conversion_note = "预览为 LibreOffice 转换件，页码可能与 Word 原件分页不同"
        pdf_result.preview_path = converted
        if text_parts := [s.raw_text for s in pdf_result.spans if s.raw_text.strip()]:
            pdf_result.suggested_fields = infer_award_fields("\n".join(text_parts))
        return pdf_result

    # .docx
    try:
        text_parts = _docx_extract_text(path)
    except Exception as exc:  # noqa: BLE001
        return ParseResult(state="FAILED", error=f"读取 .docx 失败：{exc}", media_type=media)

    spans = [
        SpanDraft(page=1, raw_text=para, extractor="docx-text")
        for para in text_parts
        if para.strip()
    ]

    # Textboxes empty but certificate is a pasted image → OCR media inside the zip
    if not spans:
        image_spans, image_err = _docx_ocr_embedded_images(path, workspace_dir)
        if image_spans:
            joined = "\n".join(s.raw_text for s in image_spans)
            return ParseResult(
                state="NEEDS_REVIEW",
                spans=image_spans,
                media_type=media,
                suggested_fields=infer_award_fields(joined),
                conversion_note="正文无文字层，已对 Word 内嵌图片做 OCR",
            )
        # Last resort: LibreOffice → PDF → text/OCR
        preview = _libreoffice_to_pdf(path, workspace_dir)
        if preview is not None:
            pdf_result = _parse_pdf(preview)
            pdf_result.is_conversion = True
            pdf_result.conversion_note = "正文无文字层，已对 LibreOffice 转换预览识别"
            pdf_result.preview_path = preview
            if any(s.raw_text.strip() for s in pdf_result.spans):
                return pdf_result
            return ParseResult(
                state="FAILED",
                error=pdf_result.error
                or image_err
                or "Word 文档无可用文本（文字层与内嵌图片均未识别到字）",
                media_type=media,
                is_conversion=True,
                conversion_note="预览为 LibreOffice 转换件",
                preview_path=preview,
            )
        hint = image_err or "未从文本框/段落/表格读到文字，且文档内无可识别图片。"
        return ParseResult(
            state="FAILED",
            error=(
                f"Word 文档无可用文本。{hint}"
                " 可另存为 PDF/图片后导入，或安装 LibreOffice 后点「重新识别」。"
            ),
            media_type=media,
        )

    joined = "\n".join(s.raw_text for s in spans)
    preview = _libreoffice_to_pdf(path, workspace_dir)
    return ParseResult(
        state="NEEDS_REVIEW",
        spans=spans,
        media_type=media,
        suggested_fields=infer_award_fields(joined),
        is_conversion=preview is not None,
        conversion_note="预览为 LibreOffice 转换件，页码可能与 Word 原件分页不同" if preview else None,
        preview_path=preview,
    )


def _docx_extract_text(path: Path) -> list[str]:
    """Paragraphs, tables, headers/footers, and text boxes (via OOXML)."""
    parts: list[str] = []
    try:
        parts = _docx_paragraphs_via_api(path)
    except Exception:  # noqa: BLE001 — fall back to raw XML
        parts = []
    xml_parts = _docx_paragraphs_via_xml(path)
    # Merge while preserving order and dropping near-duplicates
    seen = {p for p in parts}
    for line in xml_parts:
        if line not in seen:
            parts.append(line)
            seen.add(line)
    return parts


def _docx_paragraphs_via_api(path: Path) -> list[str]:
    try:
        from docx import Document  # type: ignore
    except ImportError as exc:
        raise RuntimeError("未安装 python-docx，无法解析 .docx") from exc
    doc = Document(str(path))
    parts: list[str] = []
    for p in doc.paragraphs:
        text = (p.text or "").strip()
        if text:
            parts.append(text)
    for table in doc.tables:
        for row in table.rows:
            cells = [(c.text or "").strip() for c in row.cells]
            seen: set[str] = set()
            ordered: list[str] = []
            for cell in cells:
                if cell and cell not in seen:
                    seen.add(cell)
                    ordered.append(cell)
            if ordered:
                parts.append(" | ".join(ordered))
    return parts


def _docx_paragraphs_via_xml(path: Path) -> list[str]:
    """Read all w:t text including text boxes — python-docx skips w:txbxContent."""
    import zipfile
    from xml.etree import ElementTree as ET

    w_ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    parts: list[str] = []
    with zipfile.ZipFile(path) as zf:
        xml_names = [
            n
            for n in zf.namelist()
            if n.startswith("word/")
            and n.endswith(".xml")
            and (
                n == "word/document.xml"
                or "/header" in n
                or "/footer" in n
                or "footnote" in n
                or "endnote" in n
            )
        ]
        for name in xml_names:
            try:
                root = ET.fromstring(zf.read(name))
            except ET.ParseError:
                continue
            for para in root.iter(f"{{{w_ns}}}p"):
                texts = [(node.text or "") for node in para.iter(f"{{{w_ns}}}t")]
                line = "".join(texts).strip()
                if line:
                    parts.append(line)
    return parts


def _docx_ocr_embedded_images(
    path: Path, workspace_dir: Path
) -> tuple[list[SpanDraft], str | None]:
    """OCR images stored under word/media/ (common for scanned certificates pasted into Word)."""
    import zipfile

    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
    spans: list[SpanDraft] = []
    last_err: str | None = None
    media_dir = workspace_dir / "_docx_media"
    media_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(path) as zf:
            media_names = sorted(
                n
                for n in zf.namelist()
                if n.startswith("word/media/") and Path(n).suffix.lower() in image_exts
            )
            if not media_names:
                return [], "文档内没有可 OCR 的内嵌图片。"
            for idx, name in enumerate(media_names[:8], start=1):  # bound cost
                suffix = Path(name).suffix.lower() or ".png"
                dest = media_dir / f"{path.stem}_{idx}{suffix}"
                dest.write_bytes(zf.read(name))
                ocr_spans, ocr_err = _run_local_ocr(dest)
                if ocr_err and not ocr_spans:
                    last_err = ocr_err
                    continue
                for s in ocr_spans:
                    spans.append(
                        SpanDraft(
                            page=idx,
                            bbox=s.bbox,
                            raw_text=s.raw_text,
                            extractor="docx-embedded-ocr",
                        )
                    )
    except zipfile.BadZipFile as exc:
        return [], f"docx 不是有效的 ZIP 包：{exc}"
    if spans:
        return spans, None
    return [], last_err or "内嵌图片 OCR 未识别到文字。"


def _find_soffice() -> str | None:
    found = shutil.which("soffice") or shutil.which("libreoffice")
    if found:
        return found
    candidates = [
        Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
        Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
        Path("/usr/bin/soffice"),
        Path("/usr/bin/libreoffice"),
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
    ]
    for path in candidates:
        if path.is_file():
            return str(path)
    # Glob versioned Windows installs
    for pattern in (
        r"C:\Program Files\LibreOffice*\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice*\program\soffice.exe",
    ):
        for hit in Path(pattern.split("*")[0]).parent.glob("LibreOffice*/program/soffice.exe"):
            if hit.is_file():
                return str(hit)
    return None


def _libreoffice_to_pdf(source: Path, workspace_dir: Path) -> Path | None:
    soffice = _find_soffice()
    if not soffice:
        return None
    out_dir = workspace_dir / "_conversions"
    out_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ag_lo_") as tmp:
        tmp_path = Path(tmp)
        try:
            completed = subprocess.run(
                [
                    soffice,
                    "--headless",
                    "--nologo",
                    "--nolockcheck",
                    "--nodefault",
                    "--nofirststartwizard",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(tmp_path),
                    str(source),
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if completed.returncode != 0:
            return None
        pdfs = list(tmp_path.glob("*.pdf"))
        if not pdfs:
            return None
        dest = out_dir / f"{source.stem}-{source.stat().st_mtime_ns}.pdf"
        shutil.copy2(pdfs[0], dest)
        return dest


def _parse_image(path: Path, relative_path: str) -> ParseResult:
    media = guess_media_type(relative_path)
    sidecar = path.with_suffix(path.suffix + ".ocr.json")
    if not sidecar.is_file():
        # also accept name.ocr.json beside name.png
        sidecar = path.parent / f"{path.name}.ocr.json"
    if sidecar.is_file():
        return _parse_ocr_sidecar(sidecar, media, extractor="sidecar-ocr")

    ocr_spans, ocr_error = _run_local_ocr(path)
    if ocr_spans:
        joined = "\n".join(s.raw_text for s in ocr_spans)
        return ParseResult(
            state="NEEDS_REVIEW",
            spans=ocr_spans,
            media_type=media,
            suggested_fields=infer_award_fields(joined),
        )

    # Keep preview importable, but mark FAILED so UI prompts actionable fix.
    return ParseResult(
        state="FAILED",
        spans=[
            SpanDraft(
                page=1,
                bbox=[0.05, 0.05, 0.95, 0.95],
                raw_text="",
                extractor="image-preview-only",
            )
        ],
        error=ocr_error
        or "未识别到文字。可对照原图人工填写字段后确认，或检查图片是否清晰。",
        media_type=media,
        suggested_fields={},
    )


def _parse_ocr_sidecar(sidecar: Path, media: str, extractor: str) -> ParseResult:
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    lines = payload.get("lines") if isinstance(payload, dict) else None
    spans: list[SpanDraft] = []
    if isinstance(lines, list):
        for item in lines:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            bbox = item.get("bbox")
            spans.append(
                SpanDraft(
                    page=1,
                    bbox=[float(x) for x in bbox] if isinstance(bbox, list) and len(bbox) == 4 else None,
                    raw_text=text,
                    extractor=extractor,
                )
            )
    joined = "\n".join(s.raw_text for s in spans)
    fields = payload.get("fields") if isinstance(payload, dict) else None
    suggested = infer_award_fields(joined)
    if isinstance(fields, dict):
        for key in suggested:
            if isinstance(fields.get(key), str) and fields[key].strip():
                suggested[key] = fields[key].strip()
    return ParseResult(
        state="NEEDS_REVIEW",
        spans=spans or [SpanDraft(page=1, raw_text=joined, extractor=extractor)],
        media_type=media,
        suggested_fields=suggested,
    )


_OCR_ENGINE: Any = None
_OCR_ENGINE_ERROR: str | None = None


def _get_ocr_engine() -> tuple[Any | None, str | None]:
    """Lazy singleton. Supports PaddleOCR 3.x (predict) and 2.x (ocr)."""
    global _OCR_ENGINE, _OCR_ENGINE_ERROR
    if _OCR_ENGINE is not None:
        return _OCR_ENGINE, None
    if _OCR_ENGINE_ERROR:
        return None, _OCR_ENGINE_ERROR

    try:
        from paddleocr import PaddleOCR  # type: ignore
    except ImportError:
        _OCR_ENGINE_ERROR = (
            "未安装 paddleocr。请在运行后端的同一 Python 环境执行："
            "pip install paddlepaddle paddleocr"
        )
        return None, _OCR_ENGINE_ERROR

    try:
        import paddle  # type: ignore  # noqa: F401
    except ImportError:
        _OCR_ENGINE_ERROR = (
            "已安装 paddleocr，但缺少推理引擎 paddlepaddle。"
            "请执行：pip install paddlepaddle   然后重启后端，再点「重新识别」。"
        )
        return None, _OCR_ENGINE_ERROR

    # Avoid slow model-host connectivity checks on each cold start.
    # PaddlePaddle 3.3.x + oneDNN can raise ConvertPirAttribute2RuntimeAttribute;
    # force-disable mkldnn before constructing the engine.
    import os

    os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    os.environ.setdefault("FLAGS_onednn", "0")

    init_errors: list[str] = []
    for kwargs in (
        {
            "lang": "ch",
            "use_textline_orientation": False,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "enable_mkldnn": False,
        },
        {
            "lang": "ch",
            "use_textline_orientation": True,
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "enable_mkldnn": False,
        },
        {"lang": "ch", "enable_mkldnn": False},
        {"lang": "ch"},  # older builds without enable_mkldnn
        {"lang": "ch", "use_angle_cls": True},  # PaddleOCR 2.x
    ):
        try:
            _OCR_ENGINE = PaddleOCR(**kwargs)
            return _OCR_ENGINE, None
        except Exception as exc:  # noqa: BLE001
            init_errors.append(f"{list(kwargs)}: {exc}")

    _OCR_ENGINE_ERROR = "PaddleOCR 初始化失败：" + " | ".join(init_errors[:2])
    return None, _OCR_ENGINE_ERROR


def _spans_from_ocr_payload(result: Any) -> list[SpanDraft]:
    """Normalize PaddleOCR 2.x list / 3.x predict result objects into spans."""
    spans: list[SpanDraft] = []
    if result is None:
        return spans

    # 3.x: list of result objects / dict-like with rec_texts + rec_polys/dt_polys
    if isinstance(result, list) and result and not isinstance(result[0], list):
        for page_idx, page in enumerate(result, start=1):
            texts: list[str] = []
            boxes: list[Any] = []
            if isinstance(page, dict):
                texts = list(page.get("rec_texts") or page.get("rec_text") or [])
                boxes = list(page.get("rec_polys") or page.get("dt_polys") or page.get("rec_boxes") or [])
            else:
                try:
                    texts = list(page["rec_texts"])  # type: ignore[index]
                except Exception:  # noqa: BLE001
                    texts = list(getattr(page, "rec_texts", []) or [])
                try:
                    boxes = list(page["rec_polys"])  # type: ignore[index]
                except Exception:  # noqa: BLE001
                    boxes = list(
                        getattr(page, "rec_polys", None)
                        or getattr(page, "dt_polys", None)
                        or []
                    )
            for i, text in enumerate(texts):
                raw = str(text).strip()
                if not raw:
                    continue
                bbox = None
                if i < len(boxes):
                    box = boxes[i]
                    try:
                        xs = [float(p[0]) for p in box]
                        ys = [float(p[1]) for p in box]
                        bbox = [min(xs), min(ys), max(xs), max(ys)]
                    except Exception:  # noqa: BLE001
                        bbox = None
                spans.append(
                    SpanDraft(page=page_idx, bbox=bbox, raw_text=raw, extractor="paddleocr")
                )
        if spans:
            return spans

    # 2.x: [[ [box, (text, conf)], ... ], ...]
    pages = result if isinstance(result, list) else [result]
    for page_idx, page in enumerate(pages, start=1):
        if not page:
            continue
        if isinstance(page, dict) or hasattr(page, "rec_texts"):
            # Already handled above; skip odd leftovers
            continue
        for line in page:
            try:
                box, (text, _conf) = line
                xs = [float(p[0]) for p in box]
                ys = [float(p[1]) for p in box]
                bbox = [min(xs), min(ys), max(xs), max(ys)]
                if text and str(text).strip():
                    spans.append(
                        SpanDraft(
                            page=page_idx,
                            bbox=bbox,
                            raw_text=str(text).strip(),
                            extractor="paddleocr",
                        )
                    )
            except (TypeError, ValueError, IndexError):
                continue
    return spans


def _run_local_ocr(path: Path) -> tuple[list[SpanDraft], str | None]:
    """Run local OCR. Returns (spans, error). Empty spans + error when unavailable."""
    engine, err = _get_ocr_engine()
    if engine is None:
        return [], err

    try:
        if hasattr(engine, "predict"):
            result = engine.predict(str(path))
        else:
            try:
                result = engine.ocr(str(path), cls=True)
            except TypeError:
                result = engine.ocr(str(path))
    except Exception as exc:  # noqa: BLE001
        return [], f"OCR 执行失败：{exc}"

    spans = _spans_from_ocr_payload(result)
    if not spans:
        return [], "OCR 已运行但未识别到文字（图片可能过糊、无中文，或为空白页）"
    return spans, None


def _try_local_ocr(path: Path) -> list[SpanDraft] | None:
    """Backward-compatible helper: None if OCR unavailable."""
    spans, err = _run_local_ocr(path)
    if err and not spans:
        # Distinguish unavailable vs empty: unavailable messages mention install
        if err.startswith("未安装") or "paddlepaddle" in err or "初始化失败" in err:
            return None
        return []
    return spans


def conflict_between_claim_and_fields(claim_text: str, fields: dict[str, Any]) -> list[str]:
    """Return conflict reasons when claim overstates award fields."""
    reasons: list[str] = []
    grade = str(fields.get("grade") or "")
    recipient = str(fields.get("recipient") or "")
    award_name = str(fields.get("award_name") or "")
    claim_grade = _GRADE.search(claim_text)
    if grade and claim_grade and claim_grade.group(1) != grade:
        reasons.append(f"陈述等级「{claim_grade.group(1)}」与证据「{grade}」不一致")
    if "一等奖" in claim_text and grade and grade != "一等奖":
        if not any("一等奖" in r for r in reasons):
            reasons.append(f"陈述含「一等奖」，证据为「{grade}」")
    if recipient and recipient not in claim_text and _PERSON.search(claim_text):
        m = _PERSON.search(claim_text)
        if m and m.group(1) != recipient:
            reasons.append(f"陈述姓名「{m.group(1)}」与证据「{recipient}」不一致")
    if award_name and "一等奖" not in reasons:
        # soft check: if claim invents a different contest name with 奖
        pass
    return reasons
