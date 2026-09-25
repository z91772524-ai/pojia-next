# -*- coding: utf-8 -*-
"""v7.8 回归测试：Codex 目标改走 config.toml 的 model_instructions_file。

为什么单独立一个文件：Codex 这条通道的**失败模式是静默的** ——
往 config.toml 末尾追加一个键，TOML 会把它算进末尾那个 [表] 里（变成环境变量），
Codex 完全读不到人格，而"文件确实改了、grep 得到、apply 报成功"。
所以这里每一条都盯着"真解析一遍，键到底在不在顶层"。

全程在临时目录里跑（真脚本、子进程调用），**不碰真实用户目录**。
"""
import difflib
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "破甲一键通.py")
PY = sys.executable

B = "# >>> pojia-next begin"
E = "# <<< pojia-next end"
KEY = "model_instructions_file"
LEGACY_B = "<!-- POJIA-NEXT-INJECT:BEGIN -->"
LEGACY_E = "<!-- POJIA-NEXT-INJECT:END -->"

# 一个"像真的"的 config.toml：末段是 [表]，且**结尾不带换行** ——
# 参考实现（Codex Unlock）就是在这一步翻车的。
CFG = ('model = "gpt-5-codex"\n'
       'approval_policy = "never"\n'
       'sandbox_mode = "workspace-write"\n'
       '\n'
       '[model_providers.local]\n'
       'name = "local"\n'
       'base_url = "http://127.0.0.1:8080/v1"\n'
       '\n'
       '[shell_environment_policy.set]\n'
       'PATH = "C:\\\\bin"\n'
       'TZ = "UTC"')

PASS, FAIL = [], []


def ck(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print("  [%s] %s%s" % ("PASS" if cond else "FAIL", name,
                           ("   " + str(extra)) if extra and not cond else ""))


def rd(p):
    with open(p, encoding="utf-8", newline="") as f:
        return f.read()


def wr(p, s):
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(s)


ROOT = tempfile.mkdtemp(prefix="pj_v78_")
HOME = os.path.join(ROOT, ".codex")
print("临时根目录:", ROOT, "\n")


def run(*extra):
    return subprocess.run([PY, SCRIPT, "--target", "codex", "--codex-dir", HOME] + list(extra),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=300)


def setup(cfg=CFG, agents_md=None):
    if os.path.isdir(HOME):
        shutil.rmtree(HOME, ignore_errors=True)
    os.makedirs(HOME)
    if cfg is not None:
        wr(os.path.join(HOME, "config.toml"), cfg)
    if agents_md is not None:
        wr(os.path.join(HOME, "AGENTS.md"), agents_md)


CFG_PATH = os.path.join(HOME, "config.toml")
BAK = CFG_PATH + ".pojia.bak"


def instr_path():
    return os.path.join(HOME, "managed-prompts", "pojia-persona.md")


# ---------- T1: 干净机器 apply ----------
print("T1  apply：顶层注入 + 只增不改")
setup()
p = run("--apply", "-y")
ck("退出码 0", p.returncode == 0, "rc=%d\n%s" % (p.returncode, p.stdout[-400:]))
txt = rd(CFG_PATH)
obj = tomllib.loads(txt)
ck("config.toml 仍是合法 TOML", True)
ck("键落在**顶层**", obj.get(KEY) == instr_path(), repr(obj.get(KEY))[:70])
ck("没被末尾的 [表] 吞掉",
   KEY not in obj.get("shell_environment_policy", {}).get("set", {}))
ck("原有配置一字未改",
   'TZ = "UTC"' in txt and 'base_url = "http://127.0.0.1:8080/v1"' in txt)
ck("人格文件已写出", os.path.exists(instr_path()))
ck("原文件已备份", os.path.exists(BAK))
d = [l for l in difflib.unified_diff(CFG.splitlines(True), txt.splitlines(True), n=0)]
ck("只有新增、没有删改", not [l for l in d if l.startswith("-") and not l.startswith("---")])
ck("新增恰好那一小块（空行+3行+空行）",
   len([l for l in d if l.startswith("+") and not l.startswith("+++")]) == 5,
   [l.rstrip() for l in d])

# ---------- T2: 幂等 ----------
print("\nT2  幂等")
before = rd(CFG_PATH)
run("--apply", "-y")
after = rd(CFG_PATH)
ck("二次 apply 后一字未变", before == after)
ck("标记块没叠加", after.count(B) == 1 and after.count(E) == 1)

# ---------- T3: --status ----------
print("\nT3  --status 识别")
p = run("--status", "--diagnose")
ck("报出注入键且目标存在", KEY in p.stdout and "目标文件存在" in p.stdout)
ck("报出已放人格文件", "pojia-persona.md" in p.stdout)

# ---------- T4 / T5: 还原必须逐字节 ----------
print("\nT4  还原（备份在）")
run("--revert", "-y")
ck("逐字节回到原始配置", rd(CFG_PATH) == CFG,
   "%d vs %d" % (len(rd(CFG_PATH)), len(CFG)))
ck("人格文件已清掉", not os.path.exists(instr_path()))

print("\nT5  还原（备份被删 —— 只能靠剥离）")
setup()
run("--apply", "-y")
try:
    os.remove(BAK)
except OSError:
    pass
run("--revert", "-y")
ck("逐字节回到原始配置", rd(CFG_PATH) == CFG,
   "%d vs %d" % (len(rd(CFG_PATH)), len(CFG)))
ck("config.toml 只清块、不删文件", os.path.exists(CFG_PATH))

print("\nT5b 还原（CRLF 换行的配置）")
crlf = CFG.replace("\n", "\r\n")
setup(cfg=crlf)
run("--apply", "-y")
ck("CRLF 下也能注入",
   tomllib.loads(rd(CFG_PATH)).get(KEY) == instr_path())
try:
    os.remove(BAK)
except OSError:
    pass
run("--revert", "-y")
ck("CRLF 下逐字节还原", rd(CFG_PATH) == crlf,
   "%d vs %d" % (len(rd(CFG_PATH)), len(crlf)))

# ---------- T6: 旧方案（AGENTS.md 标记块）自动迁移 ----------
print("\nT6  旧方案迁移")
USERAG = "# 我自己的 Codex 说明\n\n请用中文回答。\n"
setup(agents_md=USERAG + LEGACY_B + "\n（旧版人格）\n" + LEGACY_E + "\n")
run("--apply", "-y")
ag = rd(os.path.join(HOME, "AGENTS.md"))
ck("旧标记块已清掉", LEGACY_B not in ag and LEGACY_E not in ag)
ck("用户自己的内容保留", "请用中文回答" in ag)
ck("旧原文有存档",
   os.path.exists(os.path.join(HOME, "managed-prompts", "pojia-yijiantong", "legacy-AGENTS.md")))
ck("同轮 config.toml 也接上了", KEY in rd(CFG_PATH))

# ---------- T7: dry-run 不落盘 ----------
print("\nT7  --dry-run 不落盘")
setup()
snap = sorted(os.listdir(HOME))
run("--dry-run")
ck("目录内容完全没变", sorted(os.listdir(HOME)) == snap, sorted(os.listdir(HOME)))

# ---------- T8: 空 / 不存在 config.toml ----------
print("\nT8  空 config.toml")
setup(cfg="")
run("--apply", "-y")
try:
    ok = tomllib.loads(rd(CFG_PATH)).get(KEY) == instr_path()
except Exception:
    ok = False
ck("空配置也能注入", ok)
run("--revert", "-y")
ck("还原后文件保留（配置文件不删）", os.path.exists(CFG_PATH))

# ---------- T9: 未安装 -> 跳过而非报错 ----------
print("\nT9  未安装 -> 跳过")
gone = os.path.join(ROOT, "no-such-client")
r = subprocess.run([PY, SCRIPT, "--target", "codex", "--codex-dir", gone, "--apply", "-y"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300)
ck("不报错、不建目录", not os.path.exists(gone), "rc=%d" % r.returncode)

shutil.rmtree(ROOT, ignore_errors=True)
print("\n" + "=" * 62)
print("结果: %d 项通过, %d 项失败" % (len(PASS), len(FAIL)))
if FAIL:
    print("失败项:")
    for f in FAIL:
        print("  -", f)
    sys.exit(1)
print("=" * 62)
