"""Wrap the frozen backend in a portable Windows launcher with compatible local caching."""
import argparse
import hashlib
from pathlib import Path
import os
import subprocess

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--payload', type=Path, default=root / 'dist/ApplyGuard-Windows.exe')
parser.add_argument('--output', type=Path, default=root / 'dist/ApplyGuard.exe')
args = parser.parse_args()
payload = args.payload.resolve()
digest = hashlib.file_digest(payload.open('rb'), 'sha256').hexdigest()
build = root / 'build/desktop-launcher'
build.mkdir(parents=True, exist_ok=True)
source = build / 'Launcher.cs'
source.write_text((root / 'desktop/Launcher.cs').read_text('utf-8').replace('__PAYLOAD_HASH__', digest), encoding='utf-8-sig')
compiler = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
subprocess.run([str(compiler), '/nologo', '/target:winexe', '/platform:x64', '/optimize+',
    '/reference:System.Windows.Forms.dll', '/reference:System.Drawing.dll',
    '/win32icon:' + str(root / 'applyguard.ico'), '/out:' + str(args.output.resolve()),
    '/resource:' + str(payload) + ',ApplyGuard.payload', str(source)], check=True)
print('Built', args.output, 'with payload SHA256', digest)
