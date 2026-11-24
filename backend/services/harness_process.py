"""Run one installed Harness process with a bounded lifetime."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import signal
import subprocess

SESSION_TIMEOUT_SECONDS = 240

@dataclass(frozen=True)
class HarnessResult:
    returncode: int | None
    timed_out: bool
    stdout: str = ''
    stderr: str = ''


def stop_harness(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == 'nt':
            subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, timeout=15, creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.TimeoutExpired):
        if process.poll() is None:
            process.kill()


def run_harness(command: list[str], *, env: dict[str, str], cwd: Path,
                timeout: int = SESSION_TIMEOUT_SECONDS, capture_output: bool = False) -> HarnessResult:
    if not 15 <= timeout <= 600:
        raise ValueError('Harness 会话时限须为 15–600 秒')
    process = subprocess.Popen(command, env=env, cwd=cwd,
                               stdout=subprocess.PIPE if capture_output else None,
                               stderr=subprocess.PIPE if capture_output else None,
                               text=True, encoding='utf-8', errors='replace',
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                               start_new_session=os.name != 'nt')
    try:
        stdout, stderr = process.communicate(timeout=timeout)
        return HarnessResult(process.returncode, False, stdout or '', stderr or '')
    except subprocess.TimeoutExpired:
        stop_harness(process)
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = '', 'Harness process cleanup did not finish.'
        return HarnessResult(None, True, stdout or '', stderr or '')
    except BaseException:
        stop_harness(process)
        raise
