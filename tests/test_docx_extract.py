"""Docx text-box / embedded-image extraction without LibreOffice."""

from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring

from backend.services import evidence_parsers as ep


def _build_textbox_docx(path: Path, lines: list[str]) -> None:
    """Minimal docx whose only readable text lives in w:txbxContent (not body paragraphs)."""
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    document = Element(f"{{{w}}}document")
    body = SubElement(document, f"{{{w}}}body")
    # Empty body paragraph (what python-docx would see)
    SubElement(body, f"{{{w}}}p")
    # Drawing + textbox with real content
    p = SubElement(body, f"{{{w}}}p")
    r = SubElement(p, f"{{{w}}}r")
    # Keep markup simple: put txbxContent as sibling structure Word still stores as XML
    pict = SubElement(r, f"{{{w}}}pict")
    txbx = SubElement(pict, f"{{{w}}}txbxContent")
    for line in lines:
        tp = SubElement(txbx, f"{{{w}}}p")
        tr = SubElement(tp, f"{{{w}}}r")
        tt = SubElement(tr, f"{{{w}}}t")
        tt.text = line

    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    xml = tostring(document, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", xml)


def _build_image_only_docx(path: Path, image_bytes: bytes) -> None:
    w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    document = Element(f"{{{w}}}document")
    body = SubElement(document, f"{{{w}}}body")
    SubElement(body, f"{{{w}}}p")
    content_types = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Default Extension="png" ContentType="image/png"/>'
        '<Override PartName="/word/document.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        "</Types>"
    )
    rels = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="word/document.xml"/>'
        "</Relationships>"
    )
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", tostring(document, encoding="utf-8", xml_declaration=True))
        zf.writestr("word/media/image1.png", image_bytes)


class DocxExtractTests(unittest.TestCase):
    def test_extracts_textbox_text_without_libreoffice(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "box.docx"
            _build_textbox_docx(
                docx,
                ["获奖人：示例同学", "校级程序设计竞赛", "二等奖"],
            )
            # API-only path would miss textboxes
            api_only = ep._docx_paragraphs_via_api(docx)
            self.assertEqual(api_only, [])
            texts = ep._docx_extract_text(docx)
            self.assertIn("获奖人：示例同学", texts)
            self.assertIn("二等奖", texts)

            result = ep.parse_file(docx, "box.docx", Path(tmp))
            self.assertEqual(result.state, "NEEDS_REVIEW")
            joined = "\n".join(s.raw_text for s in result.spans)
            self.assertIn("二等奖", joined)
            self.assertEqual(result.suggested_fields.get("grade"), "二等奖")

    def test_ocr_embedded_image_when_no_text_layer(self) -> None:
        # Synthetic image with clear Chinese — requires local paddle stack.
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            self.skipTest("Pillow is not installed; optional image OCR test")
        img = Image.new("RGB", (800, 400), "white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(r"C:\Windows\Fonts\msyh.ttc", 36)
        except OSError:
            self.skipTest("no Chinese font")
        draw.text((60, 120), "校级程序设计竞赛二等奖", fill="black", font=font)
        buf = io.BytesIO()
        img.save(buf, format="PNG")

        with tempfile.TemporaryDirectory() as tmp:
            docx = Path(tmp) / "img.docx"
            _build_image_only_docx(docx, buf.getvalue())
            self.assertEqual(ep._docx_extract_text(docx), [])
            spans, err = ep._docx_ocr_embedded_images(docx, Path(tmp))
            if err and ("paddle" in (err or "").lower() or "未安装" in (err or "")):
                self.skipTest(err)
            self.assertTrue(spans, err)
            joined = "\n".join(s.raw_text for s in spans)
            self.assertTrue("竞赛" in joined or "二等奖" in joined, joined)


if __name__ == "__main__":
    unittest.main()
