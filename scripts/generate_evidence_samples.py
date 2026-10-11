"""Generate fictional local evidence samples (no real personal documents)."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "evidence-samples"


def _png_rgb(width: int, height: int, pixels: bytes) -> bytes:
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    raw = b""
    stride = width * 3
    for y in range(height):
        raw += b"\x00" + pixels[y * stride : (y + 1) * stride]
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(
        b"IDAT", zlib.compress(raw, 9)
    ) + chunk(b"IEND", b"")


def _fill_rect(buf: bytearray, w: int, x0: int, y0: int, x1: int, y1: int, rgb: tuple[int, int, int]) -> None:
    height = len(buf) // (w * 3)
    for y in range(max(0, y0), min(height, y1)):
        for x in range(max(0, x0), min(w, x1)):
            i = (y * w + x) * 3
            buf[i : i + 3] = bytes(rgb)


def write_certificate_png() -> None:
    w, h = 640, 400
    buf = bytearray([245, 242, 230] * (w * h))
    _fill_rect(buf, w, 20, 20, 620, 380, (250, 248, 240))
    _fill_rect(buf, w, 40, 40, 600, 70, (40, 70, 120))  # title bar stand-in
    # Highlight region roughly where “二等奖” sits in the sidecar bbox (normalized later)
    _fill_rect(buf, w, 220, 180, 420, 230, (220, 180, 80))
    OUT.joinpath("award-programming.png").write_bytes(_png_rgb(w, h, bytes(buf)))
    sidecar = {
        "lines": [
            {"text": "获奖人：示例同学", "bbox": [0.12, 0.22, 0.55, 0.30]},
            {"text": "校级程序设计竞赛", "bbox": [0.20, 0.34, 0.78, 0.44]},
            {"text": "二等奖", "bbox": [0.34, 0.45, 0.66, 0.58]},
            {"text": "颁发单位：示例理工大学学生会（虚构）", "bbox": [0.10, 0.68, 0.90, 0.78]},
            {"text": "日期：2025年11月", "bbox": [0.30, 0.80, 0.70, 0.88]},
        ],
        "fields": {
            "recipient": "示例同学",
            "award_name": "校级程序设计竞赛",
            "grade": "二等奖",
            "issuer": "示例理工大学学生会（虚构）",
            "date": "2025-11",
        },
        "notice": "虚构演示用 OCR 旁路数据，不是真实证件。",
    }
    OUT.joinpath("award-programming.png.ocr.json").write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_markdown() -> None:
    OUT.joinpath("award-scholarship.md").write_text(
        """# 虚构奖学金证明摘录

获奖人：示例同学
奖项：校级学习优秀奖学金
等级：二等奖
颁发单位：示例理工大学（虚构）
日期：2025年10月

说明：本文件仅用于 ApplyGuard 本地证据工作区课程演示，不是真实证明材料。
""",
        encoding="utf-8",
    )


def write_text_pdf() -> None:
    # Minimal PDF with visible text operators (Latin + escaped notes). Chinese via hex is heavy;
    # store Chinese in a text stream using UTF-16BE with BOM for simple extractors may fail.
    # Use pypdf-friendly approach: write plain ASCII PDF + companion note, and a second
    # PDF built via reportlab-free Chinese by embedding as PDF text with /Identity-H is complex.
    # Instead write a PDF that pypdf can extract by using a content stream with GBK... skip.
    # Practical approach: create PDF using the `pypdf` writer after building a blank page
    # is also hard for CJK. We'll write an English+Pinyin PDF and a UTF-8 text file used as
    # "scan note"; for Chinese PDF use markdown already, and a PDF with English labels + grade.
    content = """BT /F1 18 Tf 72 720 Td (Fictional Award Certificate) Tj
0 -28 Td (Recipient: Demo Student) Tj
0 -28 Td (Contest: Campus Programming Contest) Tj
0 -28 Td (Grade: Second Prize / Er Deng Jiang) Tj
0 -28 Td (Issuer: Example University Student Union) Tj
0 -28 Td (Date: 2025-11) Tj
0 -36 Td (Chinese mirror: 校级程序设计竞赛二等奖) Tj
ET"""
    # PDF with Chinese often fails without a CJK font. Keep extractable ASCII + separate md.
    # Put Chinese in a separate text object as literal UTF-8 in a stream — pypdf may still get it.
    stream = """BT
/F1 16 Tf
72 700 Td
(Fictional Campus Programming Contest) Tj
0 -24 Td
(Grade: Second Prize) Tj
0 -24 Td
(Keywords: ErDengJiang programming contest) Tj
ET
"""
    stream_bytes = stream.encode("latin-1")
    objects = []
    objects.append(b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n")
    objects.append(b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n")
    objects.append(
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>endobj\n"
    )
    objects.append(
        f"4 0 obj<< /Length {len(stream_bytes)} >>stream\n".encode("latin-1")
        + stream_bytes
        + b"\nendstream\nendobj\n"
    )
    objects.append(b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n")
    xref_positions = []
    out = bytearray(b"%PDF-1.4\n")
    for obj in objects:
        xref_positions.append(len(out))
        out.extend(obj)
    xref_start = len(out)
    out.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    out.extend(b"0000000000 65535 f \n")
    for pos in xref_positions:
        out.extend(f"{pos:010d} 00000 n \n".encode("latin-1"))
    out.extend(
        f"trailer<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode(
            "latin-1"
        )
    )
    OUT.joinpath("award-programming-text.pdf").write_bytes(bytes(out))
    # Scanned PDF stand-in: empty content page (no extractable text)
    empty_stream = b"BT ET"
    objects2 = [
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n",
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n",
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>endobj\n",
        f"4 0 obj<< /Length {len(empty_stream)} >>stream\n".encode("latin-1")
        + empty_stream
        + b"\nendstream\nendobj\n",
    ]
    out2 = bytearray(b"%PDF-1.4\n")
    xref2 = []
    for obj in objects2:
        xref2.append(len(out2))
        out2.extend(obj)
    xref_start2 = len(out2)
    out2.extend(f"xref\n0 {len(objects2) + 1}\n".encode("latin-1"))
    out2.extend(b"0000000000 65535 f \n")
    for pos in xref2:
        out2.extend(f"{pos:010d} 00000 n \n".encode("latin-1"))
    out2.extend(
        f"trailer<< /Size {len(objects2) + 1} /Root 1 0 R >>\nstartxref\n{xref_start2}\n%%EOF\n".encode(
            "latin-1"
        )
    )
    OUT.joinpath("award-scanned-stub.pdf").write_bytes(bytes(out2))


def write_docx() -> None:
    try:
        from docx import Document
    except ImportError:
        OUT.joinpath("award-programming.docx.README.txt").write_text(
            "Install python-docx then re-run this script to generate award-programming.docx\n",
            encoding="utf-8",
        )
        return
    doc = Document()
    doc.add_heading("虚构奖状摘录", level=1)
    doc.add_paragraph("获奖人：示例同学")
    doc.add_paragraph("校级程序设计竞赛")
    doc.add_paragraph("二等奖")
    doc.add_paragraph("颁发单位：示例理工大学学生会（虚构）")
    doc.add_paragraph("日期：2025年11月")
    doc.add_paragraph("说明：课程演示虚构材料，非真实证件。")
    doc.save(str(OUT / "award-programming.docx"))


def write_readme() -> None:
    OUT.joinpath("README.md").write_text(
        """# 虚构证据样本（课程演示）

本目录文件均为虚构演示材料，不包含真实个人证件。

| 文件 | 用途 |
| --- | --- |
| `award-programming.png` + `.ocr.json` | 奖状图片 + 本地 OCR 旁路（可高亮「二等奖」） |
| `award-programming-text.pdf` | 文本型 PDF |
| `award-scanned-stub.pdf` | 无文字扫描件占位（应提示需人工/OCR） |
| `award-programming.docx` | Word 文档 |
| `award-scholarship.md` | Markdown 证明摘录 |

导入方式：在证据工作区选择本文件夹，或逐个上传这些文件。
""",
        encoding="utf-8",
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    write_certificate_png()
    write_markdown()
    write_text_pdf()
    write_docx()
    write_readme()
    print(f"Wrote samples to {OUT}")


if __name__ == "__main__":
    main()
