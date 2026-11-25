"""Local model configuration without returning stored credentials to the UI."""
import os
import re
import tempfile
import threading
from pathlib import Path
from urllib.parse import urlsplit

_LOCK = threading.Lock()
_KEYS = ('APPLYGUARD_AI_BASE_URL', 'APPLYGUARD_AI_MODEL', 'APPLYGUARD_COMPLEX_AI_MODEL', 'APPLYGUARD_AI_API_KEY')


def current_settings():
    return {'base_url': os.getenv(_KEYS[0], ''), 'model': os.getenv(_KEYS[1], ''),
            'complex_model': os.getenv(_KEYS[2], ''), 'key_configured': bool(os.getenv(_KEYS[3], '').strip())}


def save_settings(body, root):
    values = [str(body.get(name, '')).strip() for name in ('base_url', 'model', 'complex_model', 'api_key')]
    if any(re.search(r'[\r\n\x00]', value) for value in values):
        raise ValueError('配置不能包含换行。')
    url = urlsplit(values[0])
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('请填写有效的 HTTPS 模型服务地址。')
    if not values[1]:
        raise ValueError('请填写模型名称。')
    if not values[3] and not os.getenv(_KEYS[3], '').strip():
        raise ValueError('请填写模型 API Key。')
    if any(value.startswith(('"', "'")) or value.endswith(('"', "'")) for value in values):
        raise ValueError('配置值两端请不要加引号。')
    path = Path(os.getenv('APPLYGUARD_SETTINGS_PATH') or (root / '.env'))
    with _LOCK:
        old = path.read_text(encoding='utf-8-sig').splitlines() if path.exists() else []
        updates = {key: value for key, value in zip(_KEYS, values) if value}
        updates['APPLYGUARD_GROUNDING_MODE'] = 'sag_atomic'
        lines = [line for line in old if line.partition('=')[0].strip() not in updates]
        lines.extend(f'{key}={value}' for key, value in updates.items())
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as temp:
            temp_path = Path(temp.name)
            temp.write('\n'.join(lines) + '\n')
        try:
            os.replace(temp_path, path)
        finally:
            temp_path.unlink(missing_ok=True)
        os.environ.update(updates)
    return current_settings()
