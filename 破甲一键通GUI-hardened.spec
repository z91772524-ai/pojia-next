# -*- mode: python ; coding: utf-8 -*-
# Cython 加固版 spec：入口=launcher.py，主逻辑在 pojia_gui.pyd（原生机器码），
# exe 里不再有可反编译的 GUI pyc。

a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[('cython_build/pojia_gui.pyd', '.')],
    datas=[('icon.ico', '.'), ('ca.pem', '.'), ('donate-qr.png', '.')],
    hiddenimports=['webview', 'webview.platforms.winforms', 'webview.platforms.edgechromium',
                   'clr_loader', 'clr_loader.ffi', 'pythonnet',
                   'argparse', 'base64', 'ctypes', 'datetime', 'glob', 'hashlib',
                   'hmac', 'importlib', 'json', 'platform', 're', 'secrets', 'shlex',
                   'shutil', 'ssl', 'string', 'subprocess', 'tkinter',
                   'tkinter.filedialog', 'tomllib', 'unicodedata',
                   'urllib.parse', 'urllib.request', 'webbrowser', 'winreg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['test', 'tests', 'pydoc_data', 'unittest', 'xmlrpc',
              'pdb', 'doctest', 'pydoc', 'lib2to3', 'cryptography'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='破甲一键通GUI',
    icon='icon.ico',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
