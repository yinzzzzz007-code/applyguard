from __future__ import annotations

import logging
import json
import os
import runpy
import sys
import threading
from pathlib import Path

import webview


def main() -> None:
    from backend.services.runtime_logging import configure_text_streams
    configure_text_streams()
    if len(sys.argv) > 1 and Path(sys.argv[1]).name in {'agent_mcp.py', 'connect_harness.py'}:
        script = Path(sys.argv.pop(1)).name
        script_path = Path(__file__).resolve().parent / 'scripts' / script
        runpy.run_path(str(script_path), run_name='__main__')
        return
    logging.basicConfig(level=logging.INFO)
    home = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    if getattr(sys, 'frozen', False) and os.getenv('APPLYGUARD_DESKTOP_HOME'):
        home = Path(os.environ['APPLYGUARD_DESKTOP_HOME']).resolve()
    storage = home / 'ApplyGuard-data'
    storage.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('APPLYGUARD_LOCAL_DIR', str(storage))
    os.environ.setdefault('APPLYGUARD_SETTINGS_PATH', str(storage / '.env'))
    if '--check-backend' in sys.argv:
        from importlib import import_module

        results = {}
        for name in ('backend.app', 'backend.services.grounded_workflow', 'backend.services.harness_autostart', 'mcp', 'zleap.sag', 'lancedb', 'pyarrow', 'rapidocr_onnxruntime', 'onnxruntime', 'cv2'):
            try:
                import_module(name)
                results[name] = 'ok'
            except Exception as exc:
                results[name] = f'{type(exc).__name__}: {exc}'
        (storage / 'backend-check.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
        return
    if '--check-privacy' in sys.argv:
        from backend.services.privacy_ner import status
        from backend.services.outbound_privacy import PrivacySession
        result={'model':status()['state'],'synthetic_name_masked':False,'number_preserved':False}
        try:
            if result['model']=='available':
                original='张三参与测试，团队离线性能约提升20%。'
                protected=PrivacySession().protect(original)
                result['synthetic_name_masked']='张三' not in protected
                result['number_preserved']='约提升20%' in protected
        except Exception as exc:
            result['error_type']=type(exc).__name__
        (storage/'privacy-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        return
    from backend.app import _configure_runtime_temp, _load_dotenv, create_server
    from backend.services.job_refresh import start_scheduler

    _load_dotenv(storage / '.env')
    from logging.handlers import RotatingFileHandler
    class RedactedFormatter(logging.Formatter):
        def format(self, record):
            message = super().format(record)
            secret = os.getenv('APPLYGUARD_AI_API_KEY', '')
            return message.replace(secret, '[REDACTED]') if secret else message
    diagnostic_log = RotatingFileHandler(storage / 'desktop.log', maxBytes=1_000_000, backupCount=2, encoding='utf-8')
    diagnostic_log.setLevel(logging.WARNING)
    diagnostic_log.setFormatter(RedactedFormatter('%(asctime)s %(levelname)s %(message)s'))
    logging.getLogger().addHandler(diagnostic_log)
    if '--diagnostic-budget' in sys.argv:
        from decimal import Decimal
        position = sys.argv.index('--diagnostic-budget')
        ledger = Path(sys.argv[position + 1]).resolve()
        meter = runpy.run_path(str(Path(__file__).resolve().parent / 'scripts' / 'session_budget.py'))
        meter['install'](ledger, Decimal('20'))
    os.environ.setdefault('APPLYGUARD_GROUNDING_DIR', str(storage / 'grounding'))
    if '--check-model' in sys.argv:
        import asyncio
        from openai import AsyncOpenAI
        async def check_model():
            async with AsyncOpenAI(api_key=os.environ['APPLYGUARD_AI_API_KEY'],
                    base_url=os.getenv('APPLYGUARD_AI_BASE_URL','https://api.chatanywhere.tech/v1'),max_retries=0,timeout=30) as client:
                response = await client.embeddings.create(model='text-embedding-3-small',input=['ApplyGuard synthetic diagnostic'])
                return {'embedding_dimensions':len(response.data[0].embedding)}
        try:
            result = asyncio.run(check_model())
        except Exception as error:
            from backend.services.verification_audit import save_failure
            result = {'error_type':type(error).__name__,'diagnostic_id':save_failure('model-probe',error)}
        (storage/'model-check.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        return
    if '--check-storage' in sys.argv:
        import asyncio
        import tempfile
        import lancedb
        from backend.services.sag_storage import resolve_index_directory
        cache=resolve_index_directory(os.environ['APPLYGUARD_GROUNDING_DIR'])
        with tempfile.TemporaryDirectory(dir=cache.parent) as folder:
            table=lancedb.connect(folder).create_table('probe',data=[{'id':'storage-check','vector':[0.1,0.2]}])
            found=table.search([0.1,0.2]).limit(1).to_list()[0]['id']
            async def initialize_sag():
                from zleap.sag import DataEngine, EngineConfig
                from zleap.sag.config import EmbeddingConfig, LLMConfig
                config = EngineConfig(storage_mode='normal',data_dir=str(Path(folder) / 'sag'),
                    llm=LLMConfig(api_key='offline-storage-check',model='gemini-3.1-flash-lite-preview'),
                    embedding=EmbeddingConfig(api_key='offline-storage-check',model='text-embedding-3-small',schema_dimensions=1536))
                async with DataEngine(config):
                    pass
            try:
                asyncio.run(initialize_sag())
            except Exception:
                logging.exception('Frozen SAG storage initialization failed')
                raise
        (storage/'storage-check.json').write_text(json.dumps({'cache':str(cache),'native_index_query':found,'sag_engine_initialized':True},ensure_ascii=False,indent=2),encoding='utf-8')
        return
    os.environ.setdefault('APPLYGUARD_OCR_BACKEND', 'rapidocr')
    _configure_runtime_temp()
    server = create_server("127.0.0.1", int(os.getenv('APPLYGUARD_PORT','8766')))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    start_scheduler()
    port = server.server_address[1]
    webview.create_window("ApplyGuard · 申请护栏", f"http://127.0.0.1:{port}/", width=1440, height=900, min_size=(900, 600))
    try:
        webview.start(private_mode=False, storage_path=str(storage / 'webview'))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
