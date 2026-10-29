"""Run a local check and retain its dated output even when the command fails."""
import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ZONE = timezone(timedelta(hours=8), 'Asia/Shanghai')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--label', required=True)
    parser.add_argument('--cwd', default=str(ROOT))
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command:
        parser.error('A command is required after --')
    cwd = Path(args.cwd).resolve()
    started = datetime.now(ZONE)
    label = ''.join(c if c.isalnum() or c in '-_' else '_' for c in args.label)
    directory = ROOT/'output/test-reports'/(started.strftime('%Y%m%d_%H%M%S_%f')+'_'+label)
    directory.mkdir(parents=True, exist_ok=False)
    paths = []
    for name in ('src', 'scripts', 'backend', 'tests'):
        if (cwd/name).exists():
            paths.extend(p for p in (cwd/name).rglob('*') if p.is_file())
    paths.extend(p for p in (cwd/'package.json', cwd/'package-lock.json') if p.exists())
    manifest = {str(p.relative_to(cwd)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    with (directory/'test.log').open('w', encoding='utf-8') as log:
        try:
            completed = subprocess.run(command, cwd=cwd, stdout=log, stderr=subprocess.STDOUT, timeout=180)
            code = completed.returncode
        except (OSError, subprocess.TimeoutExpired) as exc:
            log.write('\nRunner error: '+str(exc)+'\n')
            code = -1
    finished = datetime.now(ZONE)
    report = {'started_at': started.isoformat(), 'finished_at': finished.isoformat(),
        'timezone': 'Asia/Shanghai', 'label': label, 'cwd': str(cwd), 'command': command,
        'status': 'PASS' if code == 0 else 'FAIL', 'exit_code': code,
        'elapsed_seconds': (finished-started).total_seconds(), 'platform': platform.platform(),
        'source_sha256': manifest, 'note': 'Counts and limitations must be read from test.log; a build is not an end-to-end test.'}
    (directory/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    (directory/'report.md').write_text(
        f"# 检查报告：{label}\n\n- 日期时间：{started.isoformat()} — {finished.isoformat()}（北京时间）\n"
        f"- 范围：{cwd}\n- 命令：`{' '.join(command)}`\n- 结果：{report['status']}，退出码 {code}\n"
        f"- 耗时：{report['elapsed_seconds']:.3f}秒\n- 输出见 test.log；源文件 SHA256 见 report.json。\n"
        '- 限制：构建通过不等于浏览器交互通过；用例数量以日志为准。\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='source_sha256'}, ensure_ascii=False))
    print('REPORT '+str(directory))
    return 0 if code == 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
