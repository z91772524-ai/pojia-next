# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['破甲GUI.py'],
    pathex=[],
    binaries=[],
    # v8.6 云下发版：核心不再打包 —— exe 是空壳，核心源码只存服务器，
    # 输群号 → 云握手 → 内存加载，永不落盘。
    # 协议 v3（纯标准库）：TLS1.3+CA 链校验（ca.pem）+ HMAC + 二进制帧。
    # cryptography 仍排除（卡巴斯基 A/B 实测）；
    # ⚠ cffi/pycparser 必须保留 —— clr_loader.ffi 顶层 import cffi，
    #   排掉它 webview 的 .NET 加载链直接断，exe 会退回浏览器模式。
    datas=[('icon.ico', '.'), ('ca.pem', '.')],
    hiddenimports=['webview', 'webview.platforms.winforms', 'webview.platforms.edgechromium',
                   'clr_loader', 'clr_loader.ffi', 'pythonnet',
                   'argparse', 'base64', 'ctypes', 'datetime', 'glob', 'hashlib',
                   'hmac', 'importlib', 'json', 'platform', 're', 'secrets', 'shlex',
                   'shutil', 'ssl', 'string', 'subprocess', 'tomllib', 'unicodedata',
                   'urllib.parse', 'urllib.request', 'webbrowser', 'winreg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # v8.5：砍掉用不到的大块标准库 —— 缩小体积、加快单文件自解压启动
    excludes=['tkinter', 'test', 'tests', 'pydoc_data', 'unittest', 'xmlrpc',
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
