from __future__ import annotations

import argparse
import json
import plistlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description="刷新 ApplyGuard 官方岗位源")
    parser.add_argument("--source", action="append")
    parser.add_argument("--force", action="store_true", help="忽略手动刷新冷却时间")
    parser.add_argument("--due", action="store_true", help="仅刷新已到计划时间的来源")
    parser.add_argument("--status", action="store_true", help="读取当前刷新状态")
    parser.add_argument("--print-launchd", action="store_true", help="输出可选 macOS LaunchAgent plist")
    args = parser.parse_args()
    if args.print_launchd:
        sys.stdout.buffer.write(plistlib.dumps({
            "Label": "local.applyguard.job-refresh",
            "ProgramArguments": [sys.executable, str(Path(__file__).resolve()), "--due"],
            "WorkingDirectory": str(ROOT),
            "StartInterval": 900,
            "RunAtLoad": True,
        }))
        return 0
    from backend.app import _configure_runtime_temp
    from backend.services import job_refresh

    _configure_runtime_temp()
    result = job_refresh.status() if args.status else job_refresh.start(
        args.source, force=args.force, due_only=args.due, background=False)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result["state"] in {"failed", "interrupted", "partial"})


if __name__ == "__main__":
    raise SystemExit(main())
