"""Launch one installed Harness retrieval session without storing credentials."""
from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path
import sys
import tempfile
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.services.harness_setup import setup_info, retrieval_patch
from backend.services.harness_process import run_harness, SESSION_TIMEOUT_SECONDS

from backend.services.harness_autostart import TASK


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('连接器地址不允许重定向')


def connector_request(url: str, identifier: str, token: str, action: str, arguments: dict | None = None) -> dict:
    parsed = urlsplit(url)
    if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'localhost'}
            or parsed.username or parsed.password or parsed.path not in {'', '/'}
            or parsed.query or parsed.fragment):
        raise ValueError('ApplyGuard 地址必须为本机回环 HTTP 地址')
    request = Request(url.rstrip('/') + '/api/v1/agent/call',
                      json.dumps({'id': identifier, 'action': action, 'arguments': arguments or {}}).encode(),
                      {'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    try:
        with build_opener(ProxyHandler({}), NoRedirect).open(request, timeout=15) as response:
            info = json.load(response)
    except HTTPError:
        raise ValueError('连接令牌已过期、撤销或不匹配。请回页面重新授权并复制新的命令和令牌。') from None
    return info


def prepare(url: str, identifier: str, token: str) -> dict:
    info = connector_request(url, identifier, token, 'prepare')
    if info.get('disclosure') != 'cloud_allowed':
        raise ValueError('本次授权禁止材料外发；请使用手动 MCP 配置连接已隔离的本地模型，不能启动云端 Gemini。')
    return info


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--id', required=True)
    parser.add_argument('--harness', help='安装在其他位置时指定 dsh 的完整路径')
    parser.add_argument('--model')
    parser.add_argument('--base-url')
    parser.add_argument('--timeout', type=int, default=SESSION_TIMEOUT_SECONDS, help='会话总时限，15–600 秒')
    args = parser.parse_args()
    if not 15 <= args.timeout <= 600:
        parser.error('--timeout must be between 15 and 600 seconds')
    info = setup_info()
    command = args.harness or info['harness_command']
    if not command:
        raise ValueError('未找到 DeepSeek Harness。请安装桌面版或 dsh CLI；自定义安装可用 --harness 指定完整路径。')
    if not info['mcp_installed']:
        raise ValueError('当前 Python 缺少 MCP。请先执行页面“安装 ApplyGuard 连接依赖”的命令。')
    token = os.getenv('APPLYGUARD_AGENT_TOKEN') or getpass.getpass('ApplyGuard 临时连接令牌（隐藏输入）: ').strip()
    prepare(args.url, args.id, token)
    key = os.getenv('APPLYGUARD_AI_API_KEY') or getpass.getpass('模型 API Key（隐藏输入，仅用于本次 Harness）: ').strip()
    if not key:
        raise ValueError('未提供模型 API Key')
    model = args.model or info['model']
    base_url = args.base_url or info['base_url']
    patch = retrieval_patch(model, base_url)
    print(f'启动独立 Harness 检索会话，模型 {model}。请保持 ApplyGuard 页面和后端开启。', flush=True)
    print('只有 Harness 调用 get_task 后页面才显示已配对；授权到期或撤销后工具失效。', flush=True)
    runtime = ROOT / 'output' / 'harness-runtime'
    runtime.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='session-', dir=runtime) as folder:
        directory = Path(folder)
        patch_path = directory / 'retrieval.patch.yml'
        patch_path.write_text(patch, encoding='utf-8')
        env = {**os.environ, 'DSH_HOME': str(directory / 'profile'),
               'APPLYGUARD_AGENT_URL': args.url, 'APPLYGUARD_AGENT_ID': args.id,
               'APPLYGUARD_AGENT_TOKEN': token, 'APPLYGUARD_HARNESS_MODEL_KEY': key}
        env.setdefault('NODE_USE_SYSTEM_CA', '1')
        connector_request(args.url, args.id, token, 'run', {'state':'started'})
        outcome = 'failed'
        try:
            result = run_harness([command, '--profile', 'headless', '--patch', str(patch_path), TASK],
                                 env=env, cwd=directory, timeout=args.timeout)
            outcome = 'timed_out' if result.timed_out else 'finished' if result.returncode == 0 else 'failed'
        finally:
            try:
                connector_request(args.url, args.id, token, 'run', {'state':outcome})
            except (ValueError, OSError):
                print('无法更新页面会话状态；请回页面刷新或重新授权。', file=sys.stderr)
        if result.timed_out:
            print(f'检索会话超过 {args.timeout} 秒，已停止。已有候选仍可核对；请检查终端错误和模型服务后重试。', file=sys.stderr)
            return 124
    print('检索会话结束。请回页面核对候选证据；不再使用时撤销连接。', flush=True)
    return result.returncode


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as exc:
        print(f'连接未完成：{exc}', file=sys.stderr)
        raise SystemExit(1)
