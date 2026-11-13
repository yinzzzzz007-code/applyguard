"""Wrap JPEG images in separate image-only PDFs, preserving original JPEG bytes."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from PIL import Image
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, EncodedStreamObject, NameObject, NumberObject


def write_pdf(images, destination):
    writer = PdfWriter()
    for path in images:
        data = path.read_bytes()
        with Image.open(path) as image:
            if image.format != 'JPEG' or image.mode not in {'RGB', 'L'}:
                raise ValueError(f'{path.name}: only RGB or grayscale JPEG is supported')
            if image.getexif().get(274, 1) != 1:
                raise ValueError(f'{path.name}: normalize EXIF orientation first')
            width, height = image.size
            color = '/DeviceRGB' if image.mode == 'RGB' else '/DeviceGray'
        page = writer.add_blank_page(width=width*.48, height=height*.48)
        obj = EncodedStreamObject()
        obj._data = data
        obj.update({NameObject('/Type'):NameObject('/XObject'), NameObject('/Subtype'):NameObject('/Image'),
                    NameObject('/Width'):NumberObject(width), NameObject('/Height'):NumberObject(height),
                    NameObject('/ColorSpace'):NameObject(color), NameObject('/BitsPerComponent'):NumberObject(8),
                    NameObject('/Filter'):NameObject('/DCTDecode')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/XObject'):DictionaryObject({NameObject('/Im0'):writer._add_object(obj)})})
        stream = DecodedStreamObject()
        stream.set_data(f'q {width*.48:.4f} 0 0 {height*.48:.4f} 0 0 cm /Im0 Do Q\n'.encode('ascii'))
        page[NameObject('/Contents')] = writer._add_object(stream)
    with destination.open('wb') as file:
        writer.write(file)
    pages = PdfReader(destination).pages
    if len(pages) != len(images):
        raise ValueError('Unexpected page count')
    for page, original in zip(pages, images):
        embedded = page['/Resources']['/XObject']['/Im0'].get_object()._data
        if hashlib.sha256(embedded).digest() != hashlib.sha256(original.read_bytes()).digest():
            raise ValueError(f'{original.name}: embedded JPEG differs from input')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('images',nargs='+',type=Path,help='JPEG files in the requested page order')
    parser.add_argument('--output',required=True,type=Path,help='New output directory; never overwrites an existing one')
    parser.add_argument('--merge',nargs='+',type=int,help='1-based image indices to also combine in the given order')
    args=parser.parse_args()
    if args.merge and any(index<1 or index>len(args.images) for index in args.merge):
        parser.error('merge indices must refer to supplied images')
    if any(not path.is_file() for path in args.images):
        parser.error('one or more input images do not exist')
    args.output.mkdir(parents=True,exist_ok=False)
    files=[]
    for index,path in enumerate(args.images,1):
        dest=args.output/f'{index:02}_{path.stem}.pdf'
        write_pdf([path],dest)
        files.append({'input':path.name,'pdf':dest.name,'pages':1,'original_jpeg_exact':True})
    if args.merge:
        dest=args.output/('merged-'+'-'.join(str(index) for index in args.merge)+'.pdf')
        write_pdf([args.images[index-1] for index in args.merge],dest)
        files.append({'input_indices':args.merge,'pdf':dest.name,'pages':len(args.merge),'original_jpeg_exact':True})
    with zipfile.ZipFile(args.output/'pdf-collection.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for entry in files:
            archive.write(args.output/entry['pdf'],entry['pdf'])
    (args.output/'manifest.json').write_text(json.dumps({'files':files,'notice':'Image-only PDFs; no OCR text layer.'},ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'images':len(args.images),'pdfs':len(files),'bundle':str((args.output/'pdf-collection.zip').resolve())},ensure_ascii=False))


if __name__ == '__main__':
    main()
