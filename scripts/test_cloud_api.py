"""Check the user-authorized gateway with a conservative per-session budget."""
import getpass
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.environ['APPLYGUARD_AI_API_KEY'] = getpass.getpass('API key: ').strip()
os.environ['APPLYGUARD_AI_BASE_URL'] = 'https://api.chatanywhere.tech/v1'
os.environ['APPLYGUARD_AI_MODEL'] = 'gemini-3.1-flash-lite-preview'
from session_budget import install
install(root / 'output' / 'desktop-check' / 'session-budget.json')
from backend.services.model_client import HttpModelClient, ModelFailure

try:
    result = HttpModelClient(max_tokens=600, timeout=45).complete_json(
        'Return a JSON object with a boolean field ok.', 'Return {"ok":true}.')
    print('model_ok=', result.get('ok') is True, flush=True)
except ModelFailure as exc:
    print('model_error=', exc.code, 'http_status=', exc.http_status, flush=True)
    raise SystemExit(1)
