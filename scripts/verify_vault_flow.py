"""Run focused vault import checks without reading private resumes or using a model."""
import argparse
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--build', action='store_true')
args = parser.parse_args()
commands = [([sys.executable, '-m', 'unittest', 'tests.test_resume_draft_vault', 'tests.test_resume_abnormal', 'tests.test_workflow_draft'], root),
            (['node', '--experimental-strip-types', '--test', 'scripts/import-review.test.mjs'], root / 'frontend')]
if args.build:
    commands.append((['npm.cmd' if sys.platform == 'win32' else 'npm', 'run', 'build'], root / 'frontend'))
for command, cwd in commands:
    result = subprocess.run(command, cwd=cwd)
    if result.returncode:
        sys.exit(result.returncode)
print('VAULT_FLOW_CHECKS_PASSED')
