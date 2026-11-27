"""Download and verify the pinned, optional local PII model; never uploads documents."""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import urllib.request

REVISION = '333854f6b01cbf265590c5f34ddf7b97f8d6365f'
BASE = f'https://huggingface.co/CheezOne/pii-detector-chinese-japanese-korean-english-small/resolve/{REVISION}/'
FILES = {
    'config.json': ('git', '809f6e0ca7fbcf348d847c129007939a51c21548', 3084),
    'LICENSE': ('git', 'd645695673349e3947e8e5ae42332d0ac3164cd7', 11358),
    'tokenizer.json': ('sha256', 'f34b44a6dc8a0eef651bfa10e8325057530152606a69d9c3b6ae02efb1558f0a', 34363286),
    'onnx/model_quantized.onnx': ('sha256', '59d961cb82813dfc2695509269e4a75f764f495c05a03dcfb13c9e6c0816abbb', 229834991),
}


def valid(path, kind, digest, size):
    if not path.is_file() or path.stat().st_size != size:
        return False
    h = hashlib.sha1() if kind == 'git' else hashlib.sha256()
    if kind == 'git':
        h.update(f'blob {size}\0'.encode())
    with path.open('rb') as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest() == digest


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dir', default='data/local/models/privacy-ner')
    args=parser.parse_args()
    root=Path(args.dir).resolve()
    for name,(kind,digest,size) in FILES.items():
        target=root / name
        target.parent.mkdir(parents=True,exist_ok=True)
        if valid(target,kind,digest,size):
            print(f'已校验 {name}',flush=True)
            continue
        temporary=target.with_suffix(target.suffix+'.download')
        print(f'下载 {name} ({size} bytes)',flush=True)
        try:
            with urllib.request.urlopen(BASE+name,timeout=120) as response, temporary.open('wb') as out:
                count=0
                while chunk := response.read(1024 * 1024):
                    count+=len(chunk)
                    if count>size: raise ValueError('模型文件超过预期大小')
                    out.write(chunk)
            if not valid(temporary,kind,digest,size):
                raise ValueError(f'文件校验失败：{name}')
            os.replace(temporary,target)
        finally:
            temporary.unlink(missing_ok=True)
    print('模型文件已校验；本脚本未上传任何用户材料。',flush=True)


if __name__=='__main__':main()
