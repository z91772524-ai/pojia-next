# -*- coding: utf-8 -*-
"""v8 回归测试：本次增量的四条断言。

A) 硬化块新增三节（措辞映射 / 无工具兜底执行协议 / 改盘任务的强制工件）
   已进 _HARDENING_KEYS —— 否则老机器上的旧硬化块不会判定为"缺节"，新条款永远追不到。
B) 只读路径不落盘：--status / --diagnose 不再追加 破甲日志.txt
   （v7.9 实测缺陷：界面写"只读检测"，却往脚本目录写日志）。
C) 启动器取"最大的 .py"而不是"第一个 .py" —— 否则用户把仓库整包解压后
   双击会跑到 fill_hashes.py / release.py 之类的辅助脚本。
D) 分发链路脚本不再硬编码本机路径。

全程只读；唯一会动的是脚本目录下的 破甲日志.txt，且本测试的目的就是断言它**不会**出现。
"""
import importlib.util
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "破甲一键通.py")
LOG = os.path.join(ROOT, "破甲日志.txt")
PY = sys.executable

PASS, FAIL = [], []


def ck(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("   " + str(extra)) if extra and not cond else ""))


spec = importlib.util.spec_from_file_location("pojia", SCRIPT)
PJ = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PJ)

# ---------- A) 硬化块新增三节 ----------
print("A  硬化块新增三节并进指纹")
SECTIONS = ("## 措辞映射", "## 无工具兜底执行协议", "## 改盘任务的强制工件")
for s in SECTIONS:
    ck("HARDENING 含 %s" % s, s in PJ.HARDENING)
    ck("_HARDENING_KEYS 收录 %s" % s, s in PJ._HARDENING_KEYS)
ck("_HARDENING_KEYS 全部能在 HARDENING 里找到",
   all(k in PJ.HARDENING for k in PJ._HARDENING_KEYS),
   [k for k in PJ._HARDENING_KEYS if k not in PJ.HARDENING])
ck("最新硬化块 -> need_hardening False", PJ.need_hardening(PJ.hardening_text()) is False)
_old = PJ.hardening_text()
for s in SECTIONS:
    _old = _old.replace(s, "## 旧节")
ck("缺这三节的旧硬化块 -> need_hardening True（会被强制重写）",
   PJ.need_hardening(_old) is True)
ck("措辞映射表含「破解 / 绕过」行", "破解 / 绕过" in PJ.HARDENING)
ck("兜底协议含「一条可直接复制运行的完整命令」",
   "一条可直接复制运行的完整命令" in PJ.HARDENING)
ck("改盘工件含回滚要求", "怎么退回去" in PJ.HARDENING)
ck("自检文本含回执语义边界", "回执的语义边界" in PJ.signal_text("DSH", PJ.VERSION))
ck("VERSION 已是 8.0", PJ.VERSION == "8.0", PJ.VERSION)
ck("载荷内 version 与 VERSION 对齐", PJ._SEALED.get("version") == PJ.VERSION,
   PJ._SEALED.get("version"))

# ---------- B) 只读路径不落盘 ----------
print("B  只读路径不写 破甲日志.txt")
if os.path.exists(LOG):
    os.remove(LOG)
for cmd in (["--status"], ["--diagnose"]):
    if os.path.exists(LOG):
        os.remove(LOG)
    r = subprocess.run([PY, SCRIPT] + cmd, capture_output=True, cwd=ROOT)
    ck("%s 未创建 破甲日志.txt" % cmd[0], not os.path.exists(LOG),
       "rc=%s" % r.returncode)
    ck("%s 退出码为 0" % cmd[0], r.returncode == 0, r.returncode)
# 反向断言：写类动作仍然应该记日志（用 --dry-run 不合适，它本来就不写）
# 这里只断言开关本身是通的：NO_LOG=False 时 log() 必须真写。
_mark = os.path.join(ROOT, "破甲日志.txt")
PJ.NO_LOG = False
PJ.DRY_RUN = False
PJ.log("regress_v8 写入探针", echo=False)
ck("NO_LOG=False 时 log() 正常写盘", os.path.exists(_mark))
PJ.NO_LOG = True
_before = os.path.getsize(_mark) if os.path.exists(_mark) else 0
PJ.log("regress_v8 抑制探针", echo=False)
_after = os.path.getsize(_mark) if os.path.exists(_mark) else 0
ck("NO_LOG=True 时 log() 不写盘", _before == _after)
if os.path.exists(_mark):
    os.remove(_mark)

# ---------- C) 启动器取最大的 .py ----------
print("C  启动器按体积选主脚本")
bat = open(os.path.join(ROOT, "一键破甲.bat"), encoding="ascii", errors="replace").read()
ck("bat 含体积比较逻辑", "BESTSIZE" in bat and "GTR" in bat)
ck("bat 用了延迟展开", "enabledelayedexpansion" in bat and "!BESTSIZE!" in bat)
ck("bat 仍为纯 ASCII", all(ord(c) < 128 for c in bat))
ck("bat 不再取「第一个 .py」", 'if not defined SCRIPT set "SCRIPT=%%~fF"' not in bat)
# 模拟：主脚本必须是本目录里最大的 .py
_pys = [f for f in os.listdir(ROOT) if f.endswith(".py")]
_big = max(_pys, key=lambda f: os.path.getsize(os.path.join(ROOT, f)))
ck("目录内最大的 .py 就是主脚本", _big == "破甲一键通.py", _big)

# ---------- D) 不再硬编码本机路径 ----------
print("D  分发链路脚本无本机硬编码路径")
for f in ("release.py", "refresh_readme_hashes.py", "fill_hashes.py",
          "_回归测试/regress_v76.py", "_回归测试/regress_v77.py", "_回归测试/e2e_menu.py"):
    p = os.path.join(ROOT, f)
    txt = open(p, encoding="utf-8").read()
    ck("%s 无 E:\\DSH-Workspace 硬编码" % f,
       not re.search(r"[A-Za-z]:\\\\?DSH-Workspace", txt) and "E:\\DSH-Workspace" not in txt)

print("")
print("=" * 62)
print("结果: %d 项通过, %d 项失败" % (len(PASS), len(FAIL)))
if FAIL:
    for f in FAIL:
        print("  FAIL:", f)
print("=" * 62)
sys.exit(1 if FAIL else 0)
