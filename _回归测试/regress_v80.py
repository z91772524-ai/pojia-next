# -*- coding: utf-8 -*-
"""v8.0 新目标沙箱冒烟测试：临时目录模拟安装，验证 apply -> 状态 -> revert 全链路。

不碰本机真实客户端目录 —— 所有目标都用 --xxx-dir 指到临时目录。
"""
import os
import sys
import shutil
import tempfile
import importlib.util

CORE = r"E:\DSH-Workspace\破甲next-github\破甲一键通.py"

spec = importlib.util.spec_from_file_location("pojia", CORE)
m = importlib.util.module_from_spec(spec)
sys.modules["pojia"] = m
spec.loader.exec_module(m)

FAILED = []


def check(name, cond, note=""):
    tag = "PASS" if cond else "FAIL"
    print("  [%s] %s %s" % (tag, name, note))
    if not cond:
        FAILED.append(name)


class Args:
    quiet = True
    yes = True
    dry_run = False
    force = False
    diagnose = False
    persona = ""
    kill_dsh = False
    full = False


tmp = tempfile.mkdtemp(prefix="pojia-v80-")
print("沙箱目录:", tmp)

# ---- 各新目标：先造一个"已有用户内容"的配置目录，再走 apply -> revert ----
CASES = [
    ("gemini", "gemini_dir", os.path.join(".gemini"), "GEMINI.md"),
    ("qwen", "qwen_dir", os.path.join(".qwen"), "QWEN.md"),
    ("iflow", "iflow_dir", os.path.join(".iflow"), "IFLOW.md"),
    ("trae", "trae_dir", os.path.join(".trae"), os.path.join("rules", "project_rules.md")),
    ("codebuddy", "codebuddy_dir", os.path.join(".codebuddy"), "CODEBUDDY.md"),
    ("opencode", "opencode_dir", os.path.join(".config", "opencode"), "AGENTS.md"),
    ("windsurf", "windsurf_dir", os.path.join(".codeium", "windsurf"),
     os.path.join("memories", "global_rules.md")),
    ("cline", "cline_dir", os.path.join("Documents", "Cline", "Rules"), "pojia-inject.md"),
    ("copilot", "copilot_dir", os.path.join(".copilot"), "copilot-instructions.md"),
]

user, _src = m.load_user_persona("")
_pol, want = m.build_policy(user)

for key, argname, sub, rel_file in CASES:
    print("\n== %s ==" % key)
    home = os.path.join(tmp, key)
    cfg = os.path.join(home, rel_file)
    os.makedirs(os.path.dirname(cfg), exist_ok=True)
    with open(cfg, "w", encoding="utf-8") as fh:
        fh.write("# 我自己的旧规则（必须原样保留）\n- 规则 A\n- 规则 B\n")
    os.makedirs(os.path.join(home, "managed-prompts", "pojia-yijiantong"), exist_ok=True)

    args = Args()
    setattr(args, argname, home)

    t = m.TARGETS[key]()

    # 1) apply
    t.apply(args, "apply")
    txt = open(cfg, encoding="utf-8").read()
    check("%s: 标记块已注入" % key, t._has_mark(txt))
    check("%s: 原内容保留" % key, "规则 A" in txt)
    check("%s: 人格在块里" % key, "小码酱" in txt)
    check("%s: 有备份" % key, os.path.exists(cfg + t.bak_suffix))

    # 2) 重复 apply 幂等（不产生重复块）
    t.apply(args, "apply")
    txt2 = open(cfg, encoding="utf-8").read()
    check("%s: 幂等（块只出现一次）" % key, txt2.count(t.mark_begin) == 1)

    # 3) check 状态
    rows = t.check(args)
    own = [r for r in rows if r[0] == "own"]
    check("%s: check 识别为已破甲" % key, len(own) >= 1, str(own[0][1]) if own else "")

    # 4) revert
    t.revert(args)
    txt3 = open(cfg, encoding="utf-8").read()
    check("%s: 还原后无标记块" % key, not t._has_mark(txt3))
    check("%s: 还原后原文完整" % key, txt3 == "# 我自己的旧规则（必须原样保留）\n- 规则 A\n- 规则 B\n")

# ---- windsurf 6000 字符上限告警 ----
print("\n== windsurf 超限提示 ==")
home = os.path.join(tmp, "windsurf")
cfg = os.path.join(home, "memories", "global_rules.md")
args = Args()
args.windsurf_dir = home
t = m.TARGETS["windsurf"]()
t.apply(args, "apply")
n = len(open(cfg, encoding="utf-8").read())
print("  当前 global_rules.md 字符数:", n, "（超过 6000 会有告警日志，不回滚）")

# ---- DSH 人格过期自愈（护照 persona_hash 判据） ----
print("\n== DSH 人格过期自愈 ==")
dsh_home = os.path.join(tmp, "dsh-home")
os.makedirs(os.path.join(dsh_home, "managed-prompts", "pojia-yijiantong"), exist_ok=True)
# 造一个"护照版本=本版、persona_hash=旧值"的护照
pp = {"tool": "pojia-yijiantong", "version": m.VERSION, "persona_hash": "a" * 12}
m.save_passport(dsh_home, pp)
check("persona_stale 识别旧人格", m.persona_stale(dsh_home, want))
check("need_upgrade 对同版护照返回 False", not m.need_upgrade(dsh_home, "dsh"))
m.save_passport(dsh_home, {"tool": "pojia-yijiantong", "version": m.VERSION,
                           "persona_hash": want})
check("同哈希时 persona_stale=False", not m.persona_stale(dsh_home, want))

# ---- 注册表完整性 ----
print("\n== 注册表 ==")
check("DEFAULT_TARGETS 与 TARGETS 键一致", sorted(m.DEFAULT_TARGETS) == sorted(m.TARGETS))
check("TARGET_LABEL 覆盖所有目标", all(k in m.TARGET_LABEL for k in m.TARGETS))
check("INSTALL_HINT 覆盖所有目标", all(k in m.INSTALL_HINT for k in m.TARGETS))
check("resolve_targets('all') 解析 15 个", len(m.resolve_targets("all")) == 15)
check("别名解析", m.resolve_targets("workbuddy,gemini-cli,心流")[0] == "wb")

shutil.rmtree(tmp, ignore_errors=True)
print("\n" + ("全部通过 ✔" if not FAILED else "失败 %d 项: %s" % (len(FAILED), FAILED)))
sys.exit(1 if FAILED else 0)
