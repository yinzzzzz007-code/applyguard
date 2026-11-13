"""Local Harness discovery and a shared retrieval-only profile generator."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

from backend.services.model_client import DEFAULT_TEXT_MODEL

ROOT = Path(__file__).resolve().parents[2]
DISABLED_PLUGINS = (
    'tool-plugin-manager', 'tool-working-directory', 'tool-bash', 'tool-pwsh',
    'tool-jobs', 'tool-fs', 'tool-fs-search', 'tool-skill', 'tool-subagent-control',
    'tool-subagent-list-agents', 'tool-subagent', 'tool-subagent-fork', 'tool-workflow',
    'tool-todo', 'tool-goal', 'tool-web', 'agent-instructions', 'skill-filesystem',
    'session-title-llm', 'session-telemetry-otel', 'remote-access', 'plugin-manager',
    'typert-gateway',
)
ENVIRONMENT_NAMES = ('APPLYGUARD_AGENT_URL', 'APPLYGUARD_AGENT_ID', 'APPLYGUARD_AGENT_TOKEN')


def find_harness() -> str | None:
    override = os.getenv('APPLYGUARD_HARNESS_COMMAND', '').strip()
    if override:
        resolved = shutil.which(override) or (override if Path(override).is_file() else None)
        return str(Path(resolved).resolve()) if resolved else None
    found = shutil.which('dsh')
    if found:
        return str(Path(found).resolve())
    candidates = [Path.home() / 'AppData/Local/Programs/DeepSeek Harness/resources/runtime/cli/bin/dsh.cmd']
    if os.getenv('LOCALAPPDATA'):
        candidates.append(Path(os.environ['LOCALAPPDATA']) / 'Programs/DeepSeek Harness/resources/runtime/cli/bin/dsh.cmd')
    return next((str(path.resolve()) for path in candidates if path.is_file()), None)


def setup_info() -> dict:
    return {
        'python': sys.executable,
        'connector_path': str(ROOT / 'scripts/agent_mcp.py'),
        'launcher_path': str(ROOT / 'scripts/connect_harness.py'),
        'requirements_path': str(ROOT / 'requirements-agent.txt'),
        'mcp_installed': importlib.util.find_spec('mcp') is not None,
        'connector_exists': (ROOT / 'scripts/agent_mcp.py').is_file(),
        'harness_command': find_harness(),
        'model': os.getenv('APPLYGUARD_AI_MODEL', DEFAULT_TEXT_MODEL),
        'base_url': os.getenv('APPLYGUARD_AI_BASE_URL', 'https://api.chatanywhere.tech/v1'),
    }


def mcp_entry() -> dict:
    return {'id': 'applyguard-mcp', 'name': '@deepseek-ai/dsh-mcp-client', 'config': {
        'serverName': 'applyguard', 'transport': 'stdio', 'command': sys.executable,
        'args': [str(ROOT / 'scripts/agent_mcp.py')],
        'env': {name: f'__ENV_{name}__' for name in ENVIRONMENT_NAMES},
        'failOnStartupError': True,
    }}


def render_patch(entries: list[dict]) -> str:
    text = json.dumps(entries, ensure_ascii=False, indent=2)
    for name in ENVIRONMENT_NAMES:
        text = text.replace(json.dumps(f'__ENV_{name}__'), '!!js process.env.' + name)
    return text + '\n'


def retrieval_patch(model: str, base_url: str) -> str:
    if not model.strip() or not base_url.startswith('https://'):
        raise ValueError('云端检索需要有效模型名与 HTTPS API 地址')
    entries = [{'id': name, 'disabled': True} for name in DISABLED_PLUGINS]
    entries += [
        {'id': 'agent-default-model', 'config': {'provider': 'applyguard', 'model': model}},
        {'id': 'llm-pi-ai', 'config': {'providers': {'applyguard': {
            'apiKeyEnv': 'APPLYGUARD_HARNESS_MODEL_KEY', 'api': 'openai-completions',
            'baseURL': base_url, 'models': [{'id': model, 'contextWindow': 128000,
                                          'maxTokens': 3000, 'input': ['text']}],
        }}}},
        {'insert': [mcp_entry()]},
    ]
    return render_patch(entries)
