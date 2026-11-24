from decimal import Decimal
import os, threading, time, json


def install(directory, limit_cny=15):
    if not 0 < limit_cny <= 15:
        raise ValueError('累计上限须在 0 至 15 元之间。')
    import asyncio
    import httpx
    import urllib.request
    from urllib.parse import urlsplit
    from backend.services.model_client import ModelFailure

    transport = urllib.request.urlopen
    async_send = httpx.AsyncClient.send
    sync_send = httpx.Client.send
    lock = threading.Lock()
    ledger_path = directory/'chatanywhere-budget.json'
    limit = Decimal(str(limit_cny))
    gateway = 'api.chatanywhere.tech'

    def used():
        query = urllib.request.Request('https://'+gateway+'/v1/query/balance', b'{}', {
            'Authorization':'Bearer '+os.environ['APPLYGUARD_AI_API_KEY'], 'Content-Type':'application/json'})
        with transport(query, timeout=12) as response:
            data = json.load(response)
        value = Decimal(str(data.get('data', data)['apiKeyUsed']))
        if not value.is_finite() or value < 0:
            raise ValueError('Invalid usage')
        return value

    def reserve(url, body):
        address = urlsplit(url)
        if address.hostname != gateway:
            return
        payload = json.loads(body or b'{}')
        model = payload.get('model')
        if model == 'gemini-3.1-flash-lite-preview' and address.path == '/v1/chat/completions':
            tokens = int(payload.get('max_tokens') or payload.get('max_completion_tokens') or 65536)
        elif model == 'text-embedding-3-small' and address.path == '/v1/embeddings':
            tokens = 0
        else:
            raise ModelFailure('Unbudgeted gateway request', retryable=False, code='MODEL_BUDGET_LIMIT')
        upper = Decimal(len(body)+4096)*Decimal('.000001') + Decimal(tokens)*Decimal('.000006')
        with lock:
            try:
                billed = used()
                records = json.loads(ledger_path.read_text('utf-8')) if ledger_path.exists() else {}
                now = time.time()
                recent = [entry for entry in records.get('holds',[]) if now-entry['at'] < 600]
                if billed+upper+sum(Decimal(entry['amount']) for entry in recent) > limit:
                    raise ModelFailure('Preview budget reached', retryable=False, code='MODEL_BUDGET_LIMIT')
                recent.append({'at':now, 'amount':str(upper)})
                tmp = ledger_path.with_suffix('.tmp')
                tmp.write_text(json.dumps({'billed_ca':str(billed),'holds':recent}), encoding='utf-8')
                tmp.replace(ledger_path)
            except ModelFailure:
                raise
            except Exception:
                raise ModelFailure('Usage unavailable', retryable=False, code='MODEL_BUDGET_UNAVAILABLE') from None

    def bounded_open(request, *args, **kwargs):
        if isinstance(request, urllib.request.Request):
            reserve(request.full_url, request.data)
        return transport(request,*args,**kwargs)

    async def bounded_async(client, request, *args, **kwargs):
        if request.url.host == gateway:
            await asyncio.to_thread(reserve, str(request.url), await request.aread())
        return await async_send(client,request,*args,**kwargs)

    def bounded_sync(client, request, *args, **kwargs):
        if request.url.host == gateway:
            reserve(str(request.url),request.read())
        return sync_send(client,request,*args,**kwargs)

    urllib.request.urlopen = bounded_open
    httpx.AsyncClient.send = bounded_async
    httpx.Client.send = bounded_sync
    return used
