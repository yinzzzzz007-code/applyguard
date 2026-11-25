"""Check the filesystem operation required by LanceDB before network work."""
import os
import secrets
import hashlib
import logging
import shutil
import tempfile
from functools import lru_cache
from pathlib import Path


def fallback_directories(value):
    identity=hashlib.sha256(str(Path(value).resolve()).encode()).hexdigest()[:16]
    if os.name=='nt':
        import ctypes
        system=os.environ.get('SystemDrive','C:').upper()
        drives=[]
        for letter in 'DEFGHIJKLMNOPQRSTUVWXYZABC':
            drive=Path(letter+':/')
            if ctypes.windll.kernel32.GetDriveTypeW(str(drive))!=3:continue
            filesystem=ctypes.create_unicode_buffer(64)
            if not ctypes.windll.kernel32.GetVolumeInformationW(str(drive),None,0,None,None,None,filesystem,len(filesystem)):continue
            if filesystem.value.upper()!='NTFS':continue
            try:free=shutil.disk_usage(drive).free
            except OSError:continue
            if free>=1024**3:drives.append((str(drive)[:2].upper()==system,-free,drive))
        return [drive/'ApplyGuard-cache'/identity/'grounding' for _,_,drive in sorted(drives,key=lambda row:(row[0],row[1]))]
    return [Path(tempfile.gettempdir())/'ApplyGuard-cache'/identity/'grounding']


@lru_cache(maxsize=16)
def resolve_index_directory(value:str)->Path:
    try:
        check_index_directory(value)
        return Path(value).resolve()
    except (OSError,RuntimeError):
        pass
    from backend.services.sag_grounding import GroundingUnavailable
    for directory in fallback_directories(value):
        try:
            check_index_directory(str(directory))
            runtime=directory.parent/'tmp';runtime.mkdir(parents=True,exist_ok=True)
            os.environ['TEMP']=os.environ['TMP']=str(runtime)
            tempfile.tempdir=None
            logging.info('SAG cache relocated to compatible local filesystem: %s',directory)
            return directory.resolve()
        except (OSError,RuntimeError):
            continue
    raise GroundingUnavailable('未找到支持索引数据库操作的本机可写缓存目录。原始材料无需移动。')

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
