"""Check the filesystem operation required by LanceDB before network work."""
import os
import secrets
from functools import lru_cache
from pathlib import Path

@lru_cache(maxsize=32)
def check_index_directory(value:str)->None:
    directory=Path(value).resolve()
    directory.mkdir(parents=True,exist_ok=True)
    name='.applyguard-storage-probe-'+secrets.token_hex(10)
    source=directory/(name+'.source');target=directory/(name+'.link')
    created=False
    try:
        with source.open('xb') as stream:stream.write(b'ApplyGuard filesystem probe')
        created=True
        os.link(source,target)
    except OSError as error:
        from backend.services.sag_grounding import GroundingUnavailable
        raise GroundingUnavailable('SAG 索引目录不支持所需文件操作（Windows exFAT 常见）。请将 APPLYGUARD_GROUNDING_DIR 配置到 NTFS 目录；原始材料无需移动。') from error
    finally:
        if created:
            target.unlink(missing_ok=True);source.unlink(missing_ok=True)
