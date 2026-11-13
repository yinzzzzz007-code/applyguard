import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from pypdf import PdfReader
import pypdfium2

ROOT = Path(__file__).resolve().parents[1]


class ImagePDFCLITests(unittest.TestCase):
    def test_multiple_images_and_merge_preserve_pixels_and_refuse_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            images = [root/'red.jpg', root/'blue.jpg']
            Image.new('RGB',(80,120),'red').save(images[0],quality=96)
            Image.new('RGB',(120,80),'blue').save(images[1],quality=96)
            out = root/'result'
            command = [sys.executable,str(ROOT/'scripts/images_to_resume_pdfs.py'),*(str(path) for path in images),
                       '--output',str(out),'--merge','1','2']
            first = subprocess.run(command,capture_output=True,text=True)
            self.assertEqual(first.returncode,0,first.stderr)
            combined = out/'merged-1-2.pdf'
            pages = PdfReader(combined).pages
            self.assertEqual(len(pages),2)
            for page,source in zip(pages,images):
                self.assertEqual(page['/Resources']['/XObject']['/Im0'].get_object()._data,source.read_bytes())
            document = pypdfium2.PdfDocument(combined)
            try:
                first_page=document[0]
                rendered=first_page.render(scale=1).to_pil().convert('RGB')
                pixel=rendered.getpixel((rendered.width//2,rendered.height//2))
                self.assertGreater(pixel[0],200)
                self.assertLess(pixel[2],50)
                first_page.close()
            finally:
                document.close()
            second = subprocess.run(command,capture_output=True,text=True)
            self.assertNotEqual(second.returncode,0)
            self.assertEqual(len(PdfReader(combined).pages),2)


if __name__ == '__main__':
    unittest.main()
