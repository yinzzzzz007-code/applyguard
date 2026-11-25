"""Conservative per-request reservation for a user-approved test session."""
from decimal import Decimal
import json
import logging
import threading
import time


def install(path, limit=Decimal('2')):
    import asyncio
    import httpx
    import urllib.request
    from urllib.parse import urlsplit
    from backend.services.model_client import ModelFailure

    lock = threading.Lock()
    urlopen = urllib.request.urlopen
    send_async = httpx.AsyncClient.send
    send_sync = httpx.Client.send

    def reserve(url, body):
        parsed = urlsplit(str(url))
        if parsed.hostname != 'api.chatanywhere.tech':
            raise ModelFailure('测试预算只允许指定模型网关', code='MODEL_BUDGET_LIMIT')
        try:
            data = json.loads(body or b'{}')
            model = data.get('model')
            if parsed.path == '/v1/chat/completions' and model == 'gemini-3.1-flash-lite-preview':
                maximum = int(data.get('max_tokens') or data.get('max_completion_tokens') or 0)
                if not 0 < maximum <= 16384:
                    raise ValueError('unknown output limit')
                cost = Decimal(len(body) + 4096) * Decimal('0.000002') + Decimal(maximum) * Decimal('0.000012')
            elif parsed.path == '/v1/embeddings' and model == 'text-embedding-3-small':
                cost = Decimal(len(body) + 4096) * Decimal('0.000002')
            else:
                raise ValueError('unapproved model or endpoint')
        except Exception:
            raise ModelFailure('模型请求无法计入本次预算', code='MODEL_BUDGET_LIMIT') from None
        with lock:
            ledger = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'reservations': []}
            previous = sum(Decimal(row['upper_bound_ca']) for row in ledger['reservations'])
            if previous + cost > limit:
                raise ModelFailure('本次测试的保守预算上限已达到', code='MODEL_BUDGET_LIMIT')
            ledger['reservations'].append({'model': model, 'path': parsed.path,
                'upper_bound_ca': str(cost), 'time': time.time()})
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_suffix('.tmp')
            temp.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding='utf-8')
            temp.replace(path)

    def bounded_open(request, *args, **kwargs):
        if isinstance(request, urllib.request.Request):
            reserve(request.full_url, request.data)
        return urlopen(request, *args, **kwargs)

    async def bounded_async(client, request, *args, **kwargs):
        try:
            await asyncio.to_thread(reserve, str(request.url), await request.aread())
        except Exception:
            logging.exception('Diagnostic budget rejected request to %s%s',request.url.host,request.url.path)
            raise
        return await send_async(client, request, *args, **kwargs)

    def bounded_sync(client, request, *args, **kwargs):
        reserve(str(request.url), request.read())
        return send_sync(client, request, *args, **kwargs)

    urllib.request.urlopen = bounded_open
    httpx.AsyncClient.send = bounded_async
    httpx.Client.send = bounded_sync
