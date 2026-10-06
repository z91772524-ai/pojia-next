# -*- coding: utf-8 -*-
"""v8.4 回归测试：DSH 版本号检测（本次增量的断言）。

对应 2026-10-07 提问：「能不能检测到 DeepSeek harness 的官方版本号？
                     你现在的应该还是 DeepSeek harness 的社区 exe 版本哦」

本次增量要证的三件事：
  ① 官方桌面版读的是 runtime.json:desktopVersion（真·产品版本），
     **不是**安装根那个 Electron 版本文件；
  ② 社区桌面版读的是 resources\\app\\package.json:version；
  ③ 新增只读命令 --dsh-version，且 --check 里也带版本号与来源。

全程只读；不写盘、不联网、不建目录。
"""
import importlib.util
import inspect
import os
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPT = os.path.join(ROOT, "破甲一键通.py")
PY = sys.executable

PASS, FAIL = [], []


def ck(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("   " + str(extra)) if extra and not cond else ""))


spec = importlib.util.spec_from_file_location("pojia", SCRIPT)
PJ = importlib.util.module_from_spec(spec)
spec.loader.exec_module(PJ)
src = open(SCRIPT, encoding="utf-8").read()

# ---------- A) 常量与函数存在 ----------
print("A  版本源常量与函数")
ck("DSH_OFFICIAL_VER_FILE 指向 runtime.json",
   PJ.DSH_OFFICIAL_VER_FILE == ("resources", "runtime", "primary-runtime", "runtime.json"),
   getattr(PJ, "DSH_OFFICIAL_VER_FILE", None))
ck("DSH_COMMUNITY_VER_FILE 指向 app\\package.json",
   PJ.DSH_COMMUNITY_VER_FILE == ("resources", "app", "package.json"),
   getattr(PJ, "DSH_COMMUNITY_VER_FILE", None))
ck("read_dsh_version 可调用", callable(getattr(PJ, "read_dsh_version", None)))
ck("DshTarget.version_for_path 存在",
   callable(getattr(getattr(PJ, "DshTarget", None), "version_for_path", None)))

# ---------- B) 官方分支必须读 desktopVersion（别拿 Electron 版本冒充） ----------
print("B  官方版本读法正确")
_rdv = inspect.getsource(PJ.read_dsh_version)
ck("官方分支含 desktopVersion 键", "desktopVersion" in _rdv)
ck("官方分支用 DSH_OFFICIAL_VER_FILE", "DSH_OFFICIAL_VER_FILE" in _rdv)
ck("社区分支用 DSH_COMMUNITY_VER_FILE", "DSH_COMMUNITY_VER_FILE" in _rdv)
ck("根 version 文件只作兜底且写明是 Electron 版本",
   "Electron 运行时版本" in _rdv)
ck("read_dsh_version 全程只读（无写入模式）",
   '", "w"' not in _rdv and "', 'w'" not in _rdv and '"w"' not in _rdv.replace('open(p, "r"', ""))

# ---------- C) 真机探测：两条源都能读出产品版本 ----------
print("C  真机版本探测")
kinds = PJ.DshTarget().scan_desktop_kinds()
cks_all_have = all(("version" in k and "version_src" in k) for k in kinds)
ck("每个探测结果都带 version / version_src 字段", cks_all_have,
   [sorted(k.keys()) for k in kinds][:3])
if len(kinds) >= 2:
    ck("扫描结果把官方桌面版排在前面", kinds[0]["kind"] == "official",
       [k["kind"] for k in kinds])
else:
    ck("扫描结果排序稳定（不足两个安装，跳过官方优先断言）", True)

off = [k for k in kinds if k["kind"] == "official"]
com = [k for k in kinds if k["kind"] == "community"]
if off:
    ck("官方桌面版读出非空版本号", bool(off[0]["version"]), off[0])
    ck("官方来源标注为 runtime.json:desktopVersion",
       off[0]["version_src"].startswith("runtime.json:desktopVersion"), off[0]["version_src"])
    _base = off[0]["base"] or off[0]["root"]
    ck("version_for_path 能把官方 base 对回版本号",
       PJ.DshTarget().version_for_path(_base) == " v" + off[0]["version"],
       PJ.DshTarget().version_for_path(_base))
else:
    ck("本机无官方桌面版，跳过官方读数断言（不算失败）", True)
    print("      （未发现官方桌面版安装）")
if com:
    ck("社区桌面版读出非空版本号", bool(com[0]["version"]), com[0])
    ck("社区来源标注为 package.json:*",
       com[0]["version_src"].startswith("package.json:"), com[0]["version_src"])
else:
    ck("本机无社区桌面版，跳过社区读数断言（不算失败）", True)

# ---------- D) 未知 kind 不猜、不填默认值 ----------
print("D  读不到就返回空，绝不猜")
ck("read_dsh_version(未知 kind) 返回空串", PJ.read_dsh_version(ROOT, "bogus") == ("", ""))
ck("read_dsh_version(不存在的目录) 返回空串",
   PJ.read_dsh_version(os.path.join(ROOT, "__nope__"), "official") == ("", ""))

# ---------- E) CLI 接口 ----------
print("E  --dsh-version 接口")
try:
    _a = PJ.build_parser().parse_args(["--dsh-version"])
    ck("argv 里 --dsh-version 被识别", getattr(_a, "dsh_version", False) is True)
except SystemExit:
    ck("argv 里 --dsh-version 被识别", False, "argparse 直接退出了")
ck("源码里有 --dsh-version 的 help 文案", "--dsh-version" in src)
ck("--check 路径会带出版本（rows 里引用了 version 字段）",
   '_k.get("version")' in src)

# ---------- F) 真跑一遍 --dsh-version ----------
print("F  --dsh-version 真跑")
r = subprocess.run([PY, SCRIPT, "--dsh-version"], capture_output=True, timeout=300)
out = (r.stdout or b"").decode("utf-8", "replace")
ck("退出码 0", r.returncode == 0, r.returncode)
ck("输出含「本机 DSH 桌面端版本」", "本机 DSH 桌面端版本" in out, out[-300:])
ck("输出含官方来源 runtime.json:desktopVersion",
   "runtime.json:desktopVersion" in out or not off, out[-300:])
ck("输出含「来源：」标注", "来源：" in out or not kinds, out[-300:])

# ---------- G) 版本号 ----------
print("G  版本")
ck('VERSION 是 8.4', PJ.VERSION == "8.4", PJ.VERSION)
ck("载荷内 version 与 VERSION 对齐", PJ._SEALED.get("version") == PJ.VERSION,
   PJ._SEALED.get("version"))
ck("封条自检通过", PJ._seal_verify_source() is True)

print("")
print("=" * 60)
print("结果: %d 项通过, %d 项失败" % (len(PASS), len(FAIL)))
for f in FAIL:
    print("  FAIL:", f)
sys.exit(1 if FAIL else 0)
