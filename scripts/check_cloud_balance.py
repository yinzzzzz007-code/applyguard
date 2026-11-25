"""Read a temporary key from stdin and report provider-reported usage."""
import os
import sys
import getpass
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.environ['APPLYGUARD_AI_API_KEY'] = getpass.getpass('API key: ').strip()
from demo_budget import install

directory = root / 'output' / 'desktop-check' / 'budget'
directory.mkdir(parents=True, exist_ok=True)
try:
    usage = install(directory)()
    print(f'provider_reported_usage={usage}', flush=True)
except Exception as exc:
    print(f'usage_lookup_failed={type(exc).__name__} status={getattr(exc, "code", "unknown")}', flush=True)
    if hasattr(exc, 'read'):
        body = exc.read(1000).decode('utf-8', 'replace')
        print('provider_error=', body.replace(os.environ['APPLYGUARD_AI_API_KEY'], '[redacted]'), flush=True)
    raise SystemExit(1)
