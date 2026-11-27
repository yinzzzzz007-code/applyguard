# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata
from pathlib import Path

datas = [(str(path), 'data') for path in Path('data').glob('*.json')]
datas += [('frontend/dist', 'frontend/dist'), ('frontend/public', 'frontend/public'), ('third_party', 'third_party'), ('contracts', 'contracts'), ('demo', 'demo'), ('.env.example', '.')]
datas += [('scripts/agent_mcp.py', 'scripts'), ('scripts/connect_harness.py', 'scripts'), ('requirements-agent.txt', '.'), ('THIRD_PARTY_NOTICES.md', '.')]
datas += [('scripts/session_budget.py', 'scripts')]
privacy_model = Path('data/local/models/privacy-ner')
privacy_files = ('config.json', 'tokenizer.json', 'LICENSE', 'onnx/model_quantized.onnx')
if all((privacy_model / name).is_file() for name in privacy_files):
    datas += [(str(privacy_model / name), str(Path('data/local/models/privacy-ner') / Path(name).parent))
              for name in privacy_files]
binaries = []
hiddenimports = []
tmp_ret = collect_all('webview')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
for package in ('zleap.sag', 'lancedb', 'pyarrow', 'tiktoken', 'tokenizers', 'rapidocr_onnxruntime', 'onnxruntime', 'cv2', 'shapely', 'pyclipper'):
    package_data, package_binaries, package_imports = collect_all(package)
    datas += package_data
    binaries += package_binaries
    hiddenimports += package_imports
hiddenimports += collect_submodules('mcp', filter=lambda name: not name.startswith('mcp.cli'))
hiddenimports += collect_submodules('aiosqlite')
datas += copy_metadata('mcp')


a = Analysis(
    ['desktop_main.py'],
    pathex=['.', '../desktop-build-tools'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['torch', 'tensorflow', 'paddle', 'paddleocr'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='ApplyGuard-Windows',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon='applyguard.ico',
    runtime_tmpdir='.',
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
