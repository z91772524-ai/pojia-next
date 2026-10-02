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
ck("VERSION 是 8.x", PJ.VERSION.startswith("8."), PJ.VERSION)
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

# ---------- E) exe（frozen）支持 ----------
print("E  frozen/exe 支持")
ck("存在 FROZEN 开关", hasattr(PJ, "FROZEN"))
ck("随包源码副本名已定义", hasattr(PJ, "SEAL_SRC_NAME") and PJ.SEAL_SRC_NAME.endswith(".py"))
ck("非冻结时 HERE = 脚本目录",
   os.path.normcase(PJ.HERE) == os.path.normcase(ROOT), PJ.HERE)
ck("build_exe.py 存在且带 --add-data 逻辑",
   os.path.isfile(os.path.join(ROOT, "build_exe.py")) and
   "--add-data" in open(os.path.join(ROOT, "build_exe.py"), encoding="utf-8").read())
# _k1(None) 必须给可读原因，而不是 TypeError（那正是打包后一启动就崩的根因）
try:
    PJ._k1(None)
    ck("_k1(None) 抛异常", False, "居然没抛")
except ValueError as e:
    ck("_k1(None) 抛 ValueError 且信息可读", "源码层不可用" in str(e), str(e))
except Exception as e:
    ck("_k1(None) 抛 ValueError 且信息可读", False, "%s: %s" % (type(e).__name__, e))
# .gitignore 必须排除打包产物
_gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
ck(".gitignore 排除 _build/ 与 dist/", "_build/" in _gi and "dist/" in _gi)

# ---------- F) DSH 两种桌面端的识别与分派（v8.2） ----------
print("F  DSH 官方桌面版 / 社区桌面版 识别")
ck("新架构探测路径含多出来的 dsh\\ 一层",
   tuple(PJ.DSH_NEW_ARCH_BASE) == ("resources", "app.asar.unpacked", "dsh",
                                   "node_modules", "@deepseek-ai"),
   PJ.DSH_NEW_ARCH_BASE)
_D = PJ.DshTarget()
ck("classify: 官方桌面版路径",
   _D.classify_install(r"F:\x\DeepSeek Harness\resources\app.asar.unpacked\dsh\node_modules\@deepseek-ai")
   == "官方桌面版(新架构)")
ck("classify: 社区桌面版路径",
   _D.classify_install(r"C:\x\DSH Desktop\resources\app\node_modules\@deepseek-ai")
   == "社区桌面版(旧架构)")
_kinds = _D.scan_desktop_kinds()
ck("scan_desktop_kinds 返回列表", isinstance(_kinds, list), type(_kinds))
print("      本机扫到：%s" % ([(k["kind"], k["root"]) for k in _kinds] or "（无）"))
for k in _kinds:
    if k["kind"] == "official":
        # v8.2 的核心承诺：官方桌面版**一个目标都不碰**
        n = len(_D.collect_targets(k["base"]) if k["base"] else [])
        ck("官方桌面版可打点数 = 0（本工具不碰它）", n == 0, n)
# 本工具绝不写 $DSH_HOME\AGENTS.md —— 用行为断言：跑完只读命令后那个文件必须字节不变
import hashlib as _hl
_home = PJ.DshTarget().dsh_home()
_agents = os.path.join(_home, "AGENTS.md")
if os.path.isfile(_agents):
    _before = _hl.sha256(open(_agents, "rb").read()).hexdigest()
    # ⚠ 必须带 --target dsh：不带的话每条命令都会把 6 个目标全扫一遍，
    #   实测这一组断言会从 ~10 秒涨到 5 分钟（本测试自己踩过）。
    for _c in (["--check", "--target", "dsh"], ["--status", "--target", "dsh"],
               ["--dry-run", "--target", "dsh", "--yes"]):
        subprocess.run([PY, SCRIPT] + _c, capture_output=True, cwd=ROOT, timeout=300)
    _after = _hl.sha256(open(_agents, "rb").read()).hexdigest()
    ck("跑完只读/预演后 $DSH_HOME\\AGENTS.md 逐字节未变", _before == _after,
       "%s -> %s" % (_before[:12], _after[:12]))
else:
    ck("$DSH_HOME\\AGENTS.md 不存在，跳过不变性断言", True)

print("")
print("=" * 62)
print("结果: %d 项通过, %d 项失败" % (len(PASS), len(FAIL)))
if FAIL:
    for f in FAIL:
        print("  FAIL:", f)
print("=" * 62)
sys.exit(1 if FAIL else 0)
