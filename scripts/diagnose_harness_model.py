"""Diagnose the configured model's text, streaming tool call and tool-result continuation."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app import _load_dotenv
from backend.services.harness_setup import setup_info

_load_dotenv(ROOT / '.env')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Model endpoint redirect refused')


def main() -> int:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--timeout', type=int, default=45)
    parser.add_argument('--route', choices=['system', 'direct'], default='system')
    args = parser.parse_args()
    if not 5 <= args.timeout <= 120:
        parser.error('--timeout must be between 5 and 120 seconds')
    settings = setup_info()
    endpoint = settings['base_url'].rstrip('/')
    if not endpoint.startswith('https://'):
        parser.error('Model endpoint must use HTTPS')
    key = os.getenv('APPLYGUARD_AI_API_KEY') or getpass.getpass('Model API Key (hidden): ').strip()
    if not key:
        parser.error('Model API key is required')
    output = ROOT / 'output' / 'test-reports' / (datetime.now().strftime('%Y%m%d_%H%M%S') + '_harness-model-diagnosis')
    output.mkdir(parents=True)
    opener = build_opener(NoRedirect) if args.route == 'system' else build_opener(ProxyHandler({}), NoRedirect)
    rows = []

    def request(stage, payload=None, *, stream=False):
        started = time.monotonic()
        row = {'stage':stage}
        rows.append(row)
        try:
            req = Request(endpoint + ('/models' if payload is None else '/chat/completions'),
                          data=None if payload is None else json.dumps(payload).encode(),
                          headers={'Authorization':'Bearer ' + key, 'Content-Type':'application/json'})
            with opener.open(req, timeout=args.timeout) as response:
                row.update(http_status=response.status, first_byte_seconds=round(time.monotonic()-started, 3))
                if not stream:
                    raw = response.read(65537)
                    if len(raw) > 65536:
                        raise ValueError('Diagnostic response exceeded size limit')
                    data = json.loads(raw)
                else:
                    call = {'id':'', 'type':'function', 'function':{'name':'', 'arguments':''}}
                    size = 0
                    for line in response:
                        size += len(line)
                        if size > 65536:
                            raise ValueError('Diagnostic stream exceeded size limit')
                        if time.monotonic() - started > args.timeout:
                            raise TimeoutError('Diagnostic stream deadline reached')
                        text = line.decode('utf-8').strip()
                        if text == 'data: [DONE]':
                            break
                        if not text.startswith('data: '):
                            continue
                        item = json.loads(text[6:])
                        for choice in item.get('choices', []):
                            for delta in choice.get('delta', {}).get('tool_calls', []):
                                if delta.get('index', 0) != 0:
                                    raise ValueError('Unexpected additional diagnostic tool')
                                if delta.get('id'):
                                    call['id'] = delta['id']
                                for field in ['name', 'arguments']:
                                    call['function'][field] += delta.get('function', {}).get(field) or ''
                                if delta.get('extra_content'):
                                    call['extra_content'] = delta['extra_content']
                    data = call
            return data, row
        except HTTPError as error:
            raw = error.read(2048).decode('utf-8', 'replace').replace(key, '<REDACTED>')
            row.update(http_status=error.code, error='HTTP_ERROR', detail=re.sub(r'sk-[A-Za-z0-9_-]+', '<REDACTED>', raw)[:400])
        except (ValueError, OSError) as error:
            row.update(error=type(error).__name__, detail=str(error).replace(key, '<REDACTED>')[:300])
        finally:
            row['elapsed_seconds'] = round(time.monotonic() - started, 3)
        return None, row

    try:
        models, row = request('models')
        row['passed'] = models is not None and any(x.get('id') == settings['model'] for x in models.get('data', []))
        if not row['passed']:
            return 1
        common = {'model':settings['model'], 'temperature':0, 'max_tokens':128}
        text, row = request('text', {**common, 'stream':False, 'messages':[{'role':'user', 'content':'Reply with OK only.'}]})
        row['passed'] = text is not None and text.get('choices', [{}])[0].get('message', {}).get('content', '').strip() == 'OK'
        if not row['passed']:
            return 1
        tool = {'type':'function', 'function':{'name':'probe_echo', 'description':'Return the diagnostic message.',
                'parameters':{'type':'object', 'properties':{'message':{'type':'string'}}, 'required':['message'], 'additionalProperties':False}}}
        messages = [{'role':'user', 'content':'Call probe_echo with message=OK. After the tool result, reply with OK only.'}]
        call, row = request('streaming_tool_call', {**common, 'stream':True, 'messages':messages, 'tools':[tool],
                            'tool_choice':{'type':'function', 'function':{'name':'probe_echo'}}}, stream=True)
        row['passed'] = bool(call and call['id'] and call['function']['name'] == 'probe_echo' and json.loads(call['function']['arguments']) == {'message':'OK'})
        if not row['passed']:
            return 1
        messages += [{'role':'assistant', 'content':'', 'tool_calls':[call]},
                     {'role':'tool', 'tool_call_id':call['id'], 'content':'{"message":"OK"}'}]
        final, row = request('tool_result_continuation', {**common, 'stream':False, 'messages':messages, 'tools':[tool], 'tool_choice':'none'})
        row['passed'] = final is not None and final.get('choices', [{}])[0].get('message', {}).get('content', '').strip() == 'OK'
        return 0 if row['passed'] else 1
    except (KeyError, IndexError, TypeError, ValueError) as error:
        if rows:
            rows[-1].update(passed=False,error='INVALID_MODEL_RESPONSE',detail=type(error).__name__)
        return 1
    finally:
        report = {'time':datetime.now(timezone.utc).isoformat(), 'model':settings['model'], 'endpoint':endpoint,
                  'route':args.route, 'timeout_seconds':args.timeout,
                  'status':'PASS' if len(rows) == 4 and all(row.get('passed') for row in rows) else 'FAIL', 'stages':rows,
                  'scope':'Synthetic protocol diagnostic only; no private materials or model credentials stored.'}
        (output / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2))
        print('REPORT', output)


if __name__ == '__main__':
    raise SystemExit(main())
