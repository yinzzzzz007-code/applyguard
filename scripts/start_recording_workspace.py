"""Run a loopback-only recording workspace on its own origin and storage."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def configure(workspace,cache,port):
    workspace.mkdir(parents=True,exist_ok=True)
    os.environ.update(APPLYGUARD_LOCAL_DIR=str(workspace/'local'), APPLYGUARD_EVIDENCE_DIR=str(workspace/'evidence'),
        APPLYGUARD_GROUNDING_DIR=str(cache), APPLYGUARD_HOST='127.0.0.1',APPLYGUARD_PORT=str(port),
        APPLYGUARD_JOBS_AUTO_REFRESH='false',APPLYGUARD_GROUNDING_MODE='sag_atomic',
        APPLYGUARD_AI_MODEL='gemini-3.1-flash-lite-preview', APPLYGUARD_COMPLEX_AI_MODEL='gemini-3.1-flash-lite-preview',
        APPLYGUARD_AI_BASE_URL='https://api.chatanywhere.tech/v1',APPLYGUARD_AI_TIMEOUT='90')
    empty=workspace/'empty-vault.json'
    if not empty.exists():
        empty.write_text(json.dumps({'candidate_id':'cand_demo_001','profile':{},'experiences':[],'awards':[]}),encoding='utf-8')
    os.environ['APPLYGUARD_VAULT_PATH']=str(empty)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--port',type=int,default=8021)
    parser.add_argument('--cache',type=Path,required=True,help='Independent SAG cache; use NTFS on Windows')
    parser.add_argument('--cloud',action='store_true',help='Use a metered ChatAnywhere key for this process')
    args=parser.parse_args()
    configure(args.workspace.resolve(),args.cache.resolve(),args.port)
    if args.cloud:
        from demo_budget import install
        key = os.getenv('APPLYGUARD_AI_API_KEY', '').strip() or getpass.getpass('ChatAnywhere key (hidden): ').strip()
        if not key:
            parser.error('Cloud mode requires a ChatAnywhere API key.')
        os.environ['APPLYGUARD_AI_API_KEY'] = key
        used=install(args.workspace.resolve())
        usage = used()
        if usage >= 15:
            parser.error('The cumulative 15 CA demo budget has been reached.')
        print('Cumulative usage before starting:',usage,flush=True)
    else:os.environ.pop('APPLYGUARD_AI_API_KEY',None)
    from backend import app
    if not args.cloud:
        os.environ.pop('APPLYGUARD_AI_API_KEY',None)
    app.main()

if __name__=='__main__':main()
