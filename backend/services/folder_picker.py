"""Native folder selection jobs; selection does not grant file access."""
from __future__ import annotations
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import time

_LOCK = threading.RLock()
_JOB: dict | None = None
_PICKER = '''
import json
from tkinter import Tk, filedialog
root = Tk()
root.withdraw()
root.attributes('-topmost', True)
root.update_idletasks()
try:
    path = filedialog.askdirectory(title='选择允许 ApplyGuard 查找材料的文件夹', mustexist=True, parent=root)
    print(json.dumps({'path': path or None, 'cancelled': not bool(path)}), flush=True)
finally:
    root.destroy()
'''
_WINDOWS_PICKER = r'''
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
Add-Type -AssemblyName System.Windows.Forms
$dialog = New-Object System.Windows.Forms.FolderBrowserDialog
$dialog.Description = '选择允许 ApplyGuard 查找材料的文件夹'
$dialog.ShowNewFolderButton = $false
try {
    $result = $dialog.ShowDialog()
    $selected = $result -eq [System.Windows.Forms.DialogResult]::OK
    @{ path = if ($selected) { $dialog.SelectedPath } else { $null }; cancelled = -not $selected } | ConvertTo-Json -Compress
} finally {
    $dialog.Dispose()
}
'''

def _stop(process):
    if process.poll() is not None:
        return
    if os.name == 'nt':
        subprocess.run(['taskkill.exe', '/PID', str(process.pid), '/T', '/F'], capture_output=True, timeout=10,
                       creationflags=subprocess.CREATE_NO_WINDOW)
    else:
        process.kill()
    try:
        process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()

def _selection(raw: str) -> dict:
    data = json.loads(raw)
    if data.get('cancelled'):
        return {'state': 'cancelled'}
    selected = data.get('path')
    if not isinstance(selected, str) or not Path(selected).is_absolute():
        raise ValueError('请选择本机文件夹。')
    path = Path(selected).resolve(strict=True)
    if not path.is_dir() or path == Path(path.anchor):
        raise ValueError('请选择具体文件夹，不允许整盘授权。')
    return {'state': 'selected', 'path': str(path)}

def _poll(job: dict) -> dict:
    if job.get('result'):
        return job['result']
    process = job['process']
    if process.poll() is None:
        if time.monotonic() - job['started'] < 150:
            return {'state': 'pending'}
        _stop(process)
        job['result'] = {'state': 'error', 'message': '选择窗口已超时，请重新选择。'}
        return job['result']
    try:
        stdout, _ = process.communicate(timeout=2)
        if process.returncode:
            raise ValueError('无法打开本机选择窗口，可重新选择或使用手动输入。')
        job['result'] = _selection(stdout.strip().lstrip('\ufeff'))
    except (ValueError, OSError, TypeError, AttributeError, subprocess.TimeoutExpired) as exc:
        job['result'] = {'state': 'error', 'message': str(exc) if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError) else '未能读取选择结果，请重试。'}
    return job['result']

def start_folder_picker() -> dict:
    global _JOB
    with _LOCK:
        if _JOB and _poll(_JOB)['state'] == 'pending':
            raise ValueError('已有文件夹选择窗口，请先完成或取消该窗口。')
        startup = None
        if os.name == 'nt':
            startup = subprocess.STARTUPINFO()
            startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startup.wShowWindow = 1
        try:
            command = [sys.executable, '-u', '-c', _PICKER]
            if os.name == 'nt' and getattr(sys, 'frozen', False):
                command = ['powershell.exe', '-NoProfile', '-STA', '-Command', _WINDOWS_PICKER]
            process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', startupinfo=startup,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        except OSError as exc:
            raise ValueError('无法打开本机选择窗口，可使用手动输入。') from exc
        _JOB = {'id': secrets.token_hex(16), 'process': process, 'started': time.monotonic()}
        return {'picker_id': _JOB['id'], 'state': 'pending'}

def folder_picker_status(identifier: str) -> dict:
    with _LOCK:
        if not _JOB or _JOB['id'] != identifier:
            raise ValueError('选择窗口已结束，请重新选择。')
        return _poll(_JOB)

def cancel_folder_picker(identifier: str) -> dict:
    with _LOCK:
        if not _JOB or _JOB['id'] != identifier:
            return {'state': 'cancelled'}
        if not _JOB.get('result'):
            _stop(_JOB['process'])
            _JOB['result'] = {'state': 'cancelled'}
        return _JOB['result']
