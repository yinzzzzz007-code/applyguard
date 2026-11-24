"""Check local UI action boundaries without private files or model requests."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--build', action='store_true', help='Also compile the frontend')
args = parser.parse_args()
npm = 'npm.cmd' if sys.platform == 'win32' else 'npm'
commands = [
    (['node', 'scripts/button-inventory.mjs'], root / 'frontend'),
    ([sys.executable, '-m', 'unittest', 'tests.test_folder_picker', 'tests.test_agent_bridge', 'tests.test_harness_setup', 'tests.test_harness_process', 'tests.test_agent_mcp', 'tests.test_github_discovery', 'tests.test_official_jobs', 'tests.test_job_recommendation'], root),
    ([npm, 'run', 'smoke'], root / 'frontend'),
]
if args.build:
    commands.append(([npm, 'run', 'build'], root / 'frontend'))
report_dir = root / 'output' / 'test-reports' / (datetime.now().strftime('%Y%m%d_%H%M%S') + '_ui-actions')
report_dir.mkdir(parents=True, exist_ok=True)
results = []
for index, (command, cwd) in enumerate(commands):
    completed = subprocess.run(command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding='utf-8', errors='replace')
    (report_dir / f'{index + 1}.log').write_text(completed.stdout, encoding='utf-8')
    print(completed.stdout, end='')
    results.append({'command': command, 'cwd': str(cwd), 'exit_code': completed.returncode})
    if completed.returncode:
        break
success = len(results) == len(commands) and all(row['exit_code'] == 0 for row in results)
(report_dir / 'report.json').write_text(json.dumps({
    'time': datetime.now(timezone.utc).isoformat(), 'status': 'PASS' if success else 'FAIL',
    'scope': 'Local checks only; native dialogs and real model completion require separate observed evidence.',
    'commands': results,
}, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'UI_ACTION_CHECKS_{"PASSED" if success else "FAILED"}: {report_dir}')
sys.exit(0 if success else 1)
