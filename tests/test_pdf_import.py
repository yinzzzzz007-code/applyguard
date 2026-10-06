"""PDF import checks: real parser smoke plus Chinese award recognition boundaries."""
import unittest
from unittest.mock import patch

from backend.services.pdf_extract import extract_resume_pdf


def small_text_pdf(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 40 180 Td ({text}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 240] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(result))
        result.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    start = len(result)
    result.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        result.extend(f"{offset:010d} 00000 n \n".encode())
    result.extend(f"trailer\n<< /Root 1 0 R /Size {len(offsets)} >>\nstartxref\n{start}\n%%EOF\n".encode())
    return bytes(result)


class FakePage:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self) -> str:
        return self.text


class FakeReader:
    is_encrypted = False

    def __init__(self, pages: list[str]) -> None:
        self.pages = [FakePage(page) for page in pages]


class PdfImportTests(unittest.TestCase):
    def test_actual_text_pdf_extracts_contact_and_page_count(self) -> None:
        result = extract_resume_pdf(small_text_pdf("demo@example.com 13800000001"))
        self.assertEqual(result["page_count"], 1)
        self.assertEqual(result["basic"]["email"], "demo@example.com")
        self.assertEqual(result["basic"]["phone"], "13800000001")

    def test_chinese_awards_keep_source_and_do_not_invent_rank(self) -> None:
        reader = FakeReader(["姓名：李明\n参加全国大学生算法竞赛 2025年6月\n", "虚构创新大赛 省级 一等奖 2026年5月 主办方：虚构协会"])
        with patch("backend.services.pdf_extract.PdfReader", return_value=reader):
            result = extract_resume_pdf(b"%PDF-fake")
        self.assertEqual(len(result["awards"]), 2)
        self.assertEqual(result["awards"][0]["rank"], "")
        self.assertEqual(result["awards"][0]["sourcePage"], 1)
        self.assertEqual(result["awards"][1]["rank"], "一等奖")
        self.assertEqual(result["awards"][1]["level"], "省级")
        self.assertEqual(result["awards"][1]["organizer"], "虚构协会")
        self.assertEqual(result["basic"]["name"], "李明")

    def test_corrupt_scanned_and_oversize_are_explicit_failures(self) -> None:
        with self.assertRaisesRegex(ValueError, "有效的 PDF"):
            extract_resume_pdf(b"not pdf")
        with self.assertRaisesRegex(ValueError, "8 MB"):
            extract_resume_pdf(b"")
        with patch("backend.services.pdf_extract.PdfReader", return_value=FakeReader([""])):
            with self.assertRaisesRegex(ValueError, "OCR"):
                extract_resume_pdf(b"%PDF-fake")


if __name__ == "__main__":
    unittest.main()
