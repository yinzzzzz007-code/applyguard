"""Local app launcher. Key stays in process memory; does not write .env."""
import getpass
import os
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def configure():
    os.environ.setdefault('APPLYGUARD_GROUNDING_MODE','sag_atomic')
    os.environ.setdefault('APPLYGUARD_AI_BASE_URL','https://api.chatanywhere.tech/v1')
    os.environ.setdefault('APPLYGUARD_AI_MODEL','gpt-4.1-mini')
    if not os.getenv('APPLYGUARD_AI_API_KEY'):
        os.environ['APPLYGUARD_AI_API_KEY']=getpass.getpass('Model API key (hidden, memory only): ').strip()
    if not os.environ['APPLYGUARD_AI_API_KEY']:raise SystemExit('No key supplied.')

if __name__=='__main__':
    configure()
    from backend.app import main
    main()
