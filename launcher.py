# -*- coding: utf-8 -*-
"""launcher.py —— Cython 加固版入口：源码编译为 pojia_gui.pyd（机器码），
拆包只能拿到 1MB 的原生 dll，反编译器无法还原 Python 源码。"""
import sys

import pojia_gui

if __name__ == "__main__":
    sys.exit(pojia_gui.main())
