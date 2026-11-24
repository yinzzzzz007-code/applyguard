import hashlib,json,sys,urllib.request
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
import argparse,os,subprocess
parser=argparse.ArgumentParser(description='Install local multilingual job similarity model; all files stay in the selected directory.')
parser.add_argument('--directory',type=Path,default=Path(__file__).resolve().parents[1]/'data/local/job-semantic')
parser.add_argument('--install-runtime',action='store_true')
args=parser.parse_args()
root=args.directory.resolve();base=root/'model';base.mkdir(parents=True,exist_ok=True)
if args.install_runtime:
    temp=root/'temp';temp.mkdir(exist_ok=True)
    environment={**os.environ,'TEMP':str(temp),'TMP':str(temp)}
    subprocess.run([sys.executable,'-m','pip','install','--target',str(root/'packages'),'--cache-dir',str(root/'cache'),'onnxruntime==1.32.0','tokenizers>=0.22,<1','numpy>=1.26,<3'],env=environment,check=True)
repo='Xenova/paraphrase-multilingual-MiniLM-L12-v2'
with urllib.request.urlopen('https://huggingface.co/api/models/'+repo+'?blobs=true',timeout=30) as response:meta=json.load(response)
sha=meta['sha'];manifest={'repository':repo,'revision':sha,'files':{}}
for remote,local in [('tokenizer.json','tokenizer.json'),('onnx/model_quantized.onnx','model_quantized.onnx')]:
    target=base/local
    entry=next(row for row in meta['siblings'] if row['rfilename']==remote)
    expected=entry.get('lfs',{}).get('sha256')
    if not target.exists() or (expected and hashlib.sha256(target.read_bytes()).hexdigest()!=expected):
        print('Downloading '+remote,flush=True)
        temp=target.with_suffix('.download')
        with urllib.request.urlopen(f'https://huggingface.co/{repo}/resolve/{sha}/{remote}',timeout=50) as response,temp.open('wb') as out:
            while chunk:=response.read(1024*1024):out.write(chunk)
        actual=hashlib.sha256(temp.read_bytes()).hexdigest()
        if expected and actual!=expected:raise ValueError('Model checksum mismatch')
        temp.replace(target)
    manifest['files'][local]={'sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'size':target.stat().st_size}
    print(local+' ready',flush=True)
(base/'UPSTREAM.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('MODEL_READY '+str(base))

print("APPLYGUARD_JOB_EMBEDDING_DIR="+str(base))
print("APPLYGUARD_JOB_EMBEDDING_PACKAGES="+str(root/"packages"))
