# -*- coding: utf-8 -*-
"""冒烟测试：确认 破甲一键通GUI.exe 弹出的是原生 WinForms 窗口（非浏览器）"""
import ctypes
import ctypes.wintypes as wt
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

user32 = ctypes.windll.user32
TITLE = u"破甲一键通 v8.5"

def find_window():
    hwnd = user32.FindWindowW(None, TITLE)
    if not hwnd:
        return None, None
    # 取窗口类名
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    # 判断是否可见
    visible = bool(user32.IsWindowVisible(hwnd))
    # 取进程 PID
    pid = wt.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return buf.value, (visible, pid.value)

import time
hit = None
for i in range(30):
    cls, info = find_window()
    if cls:
        hit = (cls, info)
        break
    time.sleep(1)

if hit:
    cls, (visible, pid) = hit
    print("WINDOW_FOUND")
    print("CLASS=" + cls)
    print("VISIBLE=" + str(visible))
    print("PID=" + str(pid))
    is_winforms = cls.startswith("WindowsForms10.Window")
    print("NATIVE=" + ("YES (WinForms 原生窗口)" if is_winforms else "NO"))
else:
    print("WINDOW_NOT_FOUND_30S")
