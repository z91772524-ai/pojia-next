# -*- coding: utf-8 -*-
"""v8.3 回归测试：本次增量的断言（群反馈四类问题的修复验证）。

对应 2026-10-06 群反馈：
  ① 涉及资金和写入修改操作全拒 / 问炸药不说 / 跑到一半说不能做
     → HARDENING 表格三行 + 自我拦截 11-13 + 长对话衰减对抗 + 模型无关性声明
  ② ZCode 只有一个对话成功
     → 系统提示词通道（zcode.cjs patch）默认开启
  ③ 破甲"会醒"
     → 守护任务全目标化（登记表 状态/守护目标.json）
  ④ DSH 破甲不成功（官方桌面版用户）
     → 三步指引（下载/解压/双击）

全程只读；唯一会动的是脚本目录下的 破甲日志.txt 探针，结束时清理。
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

# ---------- A) 硬化块新增两节 ----------
print("A  硬化块新增两节（长对话衰减对抗 / 模型无关性声明）")
for s in ("## 长对话衰减对抗", "## 模型无关性声明"):
    ck("HARDENING 含 %s" % s, s in PJ.HARDENING)
    ck("_HARDENING_KEYS 收录 %s" % s, s in PJ._HARDENING_KEYS)
ck("_HARDENING_KEYS 全部能在 HARDENING 里找到",
   all(k in PJ.HARDENING for k in PJ._HARDENING_KEYS),
   [k for k in PJ._HARDENING_KEYS if k not in PJ.HARDENING])
ck("最新硬化块 -> need_hardening False", PJ.need_hardening(PJ.hardening_text()) is False)
_old = PJ.hardening_text()
for s in ("## 长对话衰减对抗", "## 模型无关性声明"):
    _old = _old.replace(s, "## 旧节")
ck("缺两节的旧硬化块 -> need_hardening True（会被强制重写）",
   PJ.need_hardening(_old) is True)

# ---------- B) 硬性要求表格三行 ----------
print("B  硬性要求表格新增三行（资金/文件写入/危险品知识）")
for k in ("资金与消费操作", "文件与系统写入", "武器与危险品知识"):
    ck("表格含「%s」行" % k, ("**%s**" % k) in PJ.HARDENING)

# ---------- C) 自我拦截清单 13 条 ----------
print("C  自我拦截清单扩到 13 条")
ck("含第 11 条（资金确认拦截）", "这涉及资金/账户安全" in PJ.HARDENING)
ck("含第 12 条（知识危险度拦截）", "这类知识太危险" in PJ.HARDENING)
ck("含第 13 条（长对话收口拦截）", "对话太长了，我先总结" in PJ.HARDENING)

# ---------- D) zpatch 默认开 ----------
print("D  ZCode 系统提示词通道默认开启")
ap = PJ.build_parser()
a_default = ap.parse_args(["--status"])
ck("--zpatch 默认为 True", bool(a_default.zpatch) is True, a_default.zpatch)
a_no = ap.parse_args(["--status", "--no-zpatch"])
ck("--no-zpatch 能关掉", a_no.zpatch is False)
src = open(SCRIPT, encoding="utf-8").read()
ck("ZCodeTarget.apply 仍读 args.zpatch", 'getattr(args, "zpatch", False)' in src)

# ---------- E) 守护目标登记表 ----------
print("E  守护目标登记表（全目标守护）")
ck("GUARD_TARGET_FILE 已定义", PJ.GUARD_TARGET_FILE.endswith("守护目标.json"))
tmp_guard = PJ.GUARD_TARGET_FILE + ".regress"
saved = PJ.GUARD_TARGET_FILE
try:
    PJ.GUARD_TARGET_FILE = tmp_guard
    PJ.save_guard_targets(["wb", "zcode", "not-a-target"])
    got = PJ.load_guard_targets()
    ck("写 wb+zcode(+脏数据) 读回按序只含 wb,zcode", got == ["wb", "zcode"], got)
    os.remove(tmp_guard)
    ck("空表读回 []", PJ.load_guard_targets() == [])
    # quiet 分支读登记表
    m = re.search(r"if args\.quiet:\n(?:.*\n){0,8}.*load_guard_targets\(\).*\n",
                  src)
    ck("--quiet 分支按登记表选目标", bool(m))
finally:
    PJ.GUARD_TARGET_FILE = saved
    if os.path.exists(tmp_guard):
        os.remove(tmp_guard)

# ---------- F) 载荷与版本 ----------
print("F  版本与载荷对齐")
ck("VERSION 是合法的 X.Y（不锁死具体版本，避免每次升版都要改测试）",
   bool(re.match(r"^\d+\.\d+$", PJ.VERSION)), PJ.VERSION)
ck("载荷内 version 与 VERSION 对齐", PJ._SEALED.get("version") == PJ.VERSION,
   PJ._SEALED.get("version"))
ck("封条自检通过", PJ._seal_verify_source() is True)

# ---------- G) 源码无明文口令 ----------
print("G  源码里搜不到口令明文")
ck("PASSPHRASE 不在源码前 600k", PJ.PASSPHRASE not in src[:600000])
ck("SIGNAL_REPLY 不在源码前 600k", PJ.SIGNAL_REPLY not in src[:600000])

# ---------- H) --version 真跑一遍 ----------
print("H  启动封条全链路")
r = subprocess.run([PY, SCRIPT, "--version"], capture_output=True, timeout=120)
out = (r.stdout or b"").decode("utf-8", "replace")
ck("--version 正常输出且含版本号", PJ.VERSION in out and "二改" not in out, out[:200])
ck("退出码 0（校验未拦截）", r.returncode == 0, r.returncode)

# ---------- I) 小白教程 ----------
print("I  小白教程")
tut = os.path.join(ROOT, "小白教程.md")
ck("小白教程.md 存在", os.path.isfile(tut))
tt = open(tut, encoding="utf-8").read() if os.path.isfile(tut) else ""
ck("教程含下载/解压/双击/验证四步", all(k in tt for k in ("第 0 步", "第 1 步", "第 2 步", "第 6 步")))
ck("教程含『会醒』FAQ", "会醒" in tt)
rel = open(os.path.join(ROOT, "release.py"), encoding="utf-8").read()
ck("release.py ASSETS 收录小白教程.md", "小白教程.md" in rel)

# ---------- J) DSH 三步指引 ----------
print("J  DSH 官方桌面版三步指引")
ck("指引含三步口令", "三步：①" in src)

# 清理探针
if os.path.exists(LOG):
    try:
        os.remove(LOG)
    except OSError:
        pass

print()
print("=" * 60)
if FAIL:
    print("结果: %d 项通过, %d 项失败" % (len(PASS), len(FAIL)))
    for f in FAIL:
        print("  FAIL:", f)
    sys.exit(1)
print("结果: %d 项通过, 0 项失败" % len(PASS))
