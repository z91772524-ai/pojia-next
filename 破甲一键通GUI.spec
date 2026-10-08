# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['破甲GUI.py'],
    pathex=[],
    binaries=[],
    datas=[('破甲一键通.py', '.'), ('icon.ico', '.')],
    hiddenimports=['webview', 'webview.platforms.winforms', 'webview.platforms.edgechromium', 'argparse', 'base64', 'ctypes', 'datetime', 'glob', 'hashlib', 'importlib', 'json', 'platform', 're', 'shlex', 'shutil', 'string', 'subprocess', 'tomllib', 'unicodedata', 'urllib.parse', 'webbrowser', 'winreg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # v8.5：砍掉用不到的大块标准库 —— 缩小体积、加快单文件自解压启动
    excludes=['tkinter', 'test', 'tests', 'pydoc_data', 'unittest', 'xmlrpc',
              'pdb', 'doctest', 'pydoc', 'lib2to3'],
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
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
