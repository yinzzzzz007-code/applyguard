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
    if len(sys.argv) > 1 and Path(sys.argv[1]).name in {'agent_mcp.py', 'connect_harness.py'}:
        script = Path(sys.argv.pop(1)).name
        script_path = Path(__file__).resolve().parent / 'scripts' / script
        runpy.run_path(str(script_path), run_name='__main__')
        return
    logging.basicConfig(level=logging.INFO)
    home = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    storage = home / 'ApplyGuard-data'
    storage.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('APPLYGUARD_LOCAL_DIR', str(storage))
    os.environ.setdefault('APPLYGUARD_GROUNDING_DIR', str(storage / 'grounding'))
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
    from backend.app import _configure_runtime_temp, _load_dotenv, create_server
    from backend.services.job_refresh import start_scheduler

    _load_dotenv(storage / '.env')
    os.environ.setdefault('APPLYGUARD_OCR_BACKEND', 'rapidocr')
    _configure_runtime_temp()
    server = create_server("127.0.0.1", 8766)
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
