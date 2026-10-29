"""Package the updated app and honest partial-evaluation report without public raw data."""
import hashlib,json,re,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output/expanded-eval'

def main():
    protocol=json.loads((OUT/'protocol.json').read_text(encoding='utf-8'))
    for name,expected in protocol['code'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=expected:raise SystemExit('Frozen evaluation code changed: '+name)
    status={'status':'INCOMPLETE_PROVIDER_BALANCE','provider_error':'HTTP 403 insufficient balance',
        'process_stopped':True,'planned_cases':260,'fully_paired_career_cases':20,
        'felm_atomic_completed':0,'felm_whole_completed':6,'no_recharge_performed':True,
        'tests':{'backend_total':165,'backend_passed':164,'backend_skipped':1,'frontend_passed':18,
            'build':'passed','lint_errors':0,'preexisting_lint_warnings':4},
        'history':'20 browser-local snapshots; restore creates a new version and invalidates approvals',
        'credentials_in_archive':False,'user_private_material_used':False}
    (OUT/'delivery-status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    subprocess.run(['git','add','--intent-to-add','--','.'],cwd=ROOT,check=True,capture_output=True)
    subprocess.run(['git','diff','--check'],cwd=ROOT,check=True,capture_output=True)
    patch=ROOT/'output/integration-v2.patch'
    patch.write_bytes(subprocess.check_output(['git','diff','--binary','HEAD'],cwd=ROOT))
    subprocess.run(['git','apply','--reverse','--check',str(patch)],cwd=ROOT,check=True,capture_output=True)
    names=set(subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','-z'],cwd=ROOT).decode().split('\0'))-{''}
    files={ROOT/name for name in names}
    files.update((ROOT/'frontend/dist').rglob('*'))
    files.update(OUT.glob('*.json'));files.update(OUT.glob('*.txt'))
    files.update([patch,ROOT/'output/integration-live.json',ROOT/'output/validation-summary.json'])
    files=sorted(p for p in files if p.is_file() and not p.is_symlink() and p!=OUT/'archive.json')
    for path in files:
        relative=path.relative_to(ROOT).as_posix()
        if path.name!='.gitkeep' and any(part in {'.venv','node_modules','.git','local','__pycache__'} for part in path.relative_to(ROOT).parts):
            raise SystemExit('Excluded runtime file: '+relative)
        if path.name=='.env' or re.search(rb'sk-[A-Za-z0-9]{30,}',path.read_bytes()):raise SystemExit('Credential candidate: '+relative)
    archive=ROOT.parent/'ApplyGuard-SAG-V2-历史回滚实验版.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in files:z.write(path,'applyguard-sag-app/'+path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:
        if z.testzip():raise SystemExit('Archive integrity failed')
    meta={'archive':str(archive),'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
        'size_bytes':archive.stat().st_size,'file_count':len(files),'status':status}
    (OUT/'archive.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
