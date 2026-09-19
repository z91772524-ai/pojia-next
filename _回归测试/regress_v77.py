"""v7.7 回归测试：验证新增三个目标（Codex/Cursor/Claude）的注入/还原/检测逻辑。

全程在临时目录里跑，**绝不碰真实用户目录**。
"""
import sys, os, io, json, shutil, tempfile, importlib.util, builtins
sys.stdout.reconfigure(encoding="utf-8")

SRC = r"E:\DSH-Workspace\破甲next-github\破甲一键通.py"
spec = importlib.util.spec_from_file_location("pj", SRC)
mod = importlib.util.module_from_spec(spec)
sys.argv = ["x"]
spec.loader.exec_module(mod)

PASS, FAIL = [], []
def chk(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name}" + (f"  {extra}" if extra and not cond else ""))

class A: pass
def mkargs(**kw):
    a = A()
    a.target = "all"; a.yes = True; a.quiet = False; a.dry_run = False
    a.diagnose = False; a.persona = ""
    a.dsh_dir = ""; a.zcode_dir = ""; a.zcode_cjs = ""
    a.codex_dir = ""; a.cursor_dir = ""; a.claude_dir = ""
    a.wb_install = ""; a.wb_data = ""; a.zpatch = False
    for k, v in kw.items():
        setattr(a, k, v)
    return a

tmp = tempfile.mkdtemp(prefix="pj_v77_")
print(f"临时根目录: {tmp}\n")

# ---------- T1: 目标注册 ----------
print("T1  目标注册")
for k in ("codex", "cursor", "claude"):
    chk(f"{k} 已注册", k in mod.TARGETS, str(list(mod.TARGETS)))
chk("DEFAULT_TARGETS 含 6 个", len(mod.DEFAULT_TARGETS) == 6, str(mod.DEFAULT_TARGETS))
chk("别名 gpt->codex", mod.TARGET_ALIAS.get("gpt") == "codex")
chk("别名 claude-code->claude", mod.TARGET_ALIAS.get("claude-code") == "claude")
chk("resolve_targets('codex,cursor')", mod.resolve_targets("codex,cursor") == ["codex", "cursor"])

# ---------- T2: resolve_pick ----------
print("\nT2  resolve_pick 目录识别")
for k, sub in (("codex", ".codex"), ("cursor", ".cursor"), ("claude", ".claude")):
    t = mod.TARGETS[k]()
    home = os.path.join(tmp, sub)
    os.makedirs(home, exist_ok=True)
    got, note = t.resolve_pick(home)
    chk(f"{k} 直接选自身目录", got == os.path.normpath(home), f"got={got} note={note}")
    got2, _ = t.resolve_pick(tmp)
    chk(f"{k} 从父目录能推出", os.path.basename(got2).lower() == sub, f"got2={got2}")

# ---------- T3: 注入 ----------
print("\nT3  注入（标记块写入）")
persona_body = "你是测试人格。TEST-PERSONA-MARKER"
# 造一个假 persona.md
pf = os.path.join(tmp, "persona.md")
open(pf, "w", encoding="utf-8").write(persona_body)

for k, sub in (("codex", ".codex"), ("cursor", ".cursor"), ("claude", ".claude")):
    t = mod.TARGETS[k]()
    home = os.path.join(tmp, sub)
    a = mkargs(**{t.arg_name: home, "persona": pf})
    res = t.apply(a, "apply")
    target = t.prompt_path(home)
    txt = open(target, encoding="utf-8").read() if os.path.exists(target) else ""
    chk(f"{k} 注入后文件存在", os.path.exists(target), target)
    chk(f"{k} 含标记块", t.mark_begin in txt)
    chk(f"{k} 含人格内容", "TEST-PERSONA-MARKER" in txt or "测试人格" in txt)

# Claude 的路径是 CLAUDE.md
chk("Claude 目标是 CLAUDE.md",
    mod.ClaudeTarget.prompt_file == "CLAUDE.md")
chk("Codex 目标是 AGENTS.md",
    mod.CodexTarget.prompt_file == "AGENTS.md")
chk("Cursor 规则在 rules/ 下",
    "rules" in mod.CursorTarget.prompt_file)

# ---------- T4: 已有内容不被破坏 ----------
print("\nT4  已有内容保留（幂等 + 不覆盖）")
t = mod.CodexTarget()
home = os.path.join(tmp, ".codex")
target = t.prompt_path(home)
open(target, "w", encoding="utf-8").write("# 用户自己的 AGENTS.md\n\nUSER-ORIGINAL-CONTENT\n")
a = mkargs(codex_dir=home, persona=pf)
t.apply(a, "apply")
txt = open(target, encoding="utf-8").read()
chk("原内容保留", "USER-ORIGINAL-CONTENT" in txt)
chk("标记块已加", t.mark_begin in txt)
chk("备份已生成（只备份非我方原文件）", os.path.exists(target + t.bak_suffix))

# 二次 apply 幂等
t.apply(a, "apply")
txt2 = open(target, encoding="utf-8").read()
chk("二次 apply 不重复插入标记块", txt2.count(t.mark_begin) == 1, f"count={txt2.count(t.mark_begin)}")
chk("二次 apply 原内容仍唯一", txt2.count("USER-ORIGINAL-CONTENT") == 1)

# ---------- T5: 检测 ----------
print("\nT5  check 状态报告")
rows = t.check(a)
joined = " ".join(r[1] for r in rows)
chk("check 能报出已破甲", ("已破甲" in joined) or ("含我们的标记块" in joined), joined[:120])

# ---------- T6: 还原 ----------
print("\nT6  还原")
t.revert(a)
txt3 = open(target, encoding="utf-8").read() if os.path.exists(target) else ""
chk("还原后标记块消失", t.mark_begin not in txt3)
chk("还原后用户原内容还在", "USER-ORIGINAL-CONTENT" in txt3)
chk("还原后内容等于原始", txt3.strip() == "# 用户自己的 AGENTS.md\n\nUSER-ORIGINAL-CONTENT".strip(),
    repr(txt3[:80]))

# ---------- T7: 未安装则跳过（不报错） ----------
print("\nT7  未检测到安装 -> 跳过而非报错")
gone = os.path.join(tmp, "no-such-client")
for k, an in (("codex", "codex_dir"), ("cursor", "cursor_dir"), ("claude", "claude_dir")):
    tt = mod.TARGETS[k]()
    aa = mkargs(**{an: gone, "persona": pf})
    r = tt.apply(aa, "apply")
    chk(f"{k} 返回 skip 且 err 为 0", r.get("skip") == 1 and not r.get("err"), str(r))

# ---------- T8: dry-run 不写盘 ----------
print("\nT8  dry-run 不落盘")
dh = os.path.join(tmp, ".cursor")
dpt = mod.CursorTarget().prompt_path(dh)
before = os.path.exists(dpt)
mod.DRY_RUN = True
try:
    mod.CursorTarget().apply(mkargs(cursor_dir=dh, persona=pf, dry_run=True), "dry-run")
finally:
    mod.DRY_RUN = False
chk("dry-run 后文件状态未变", os.path.exists(dpt) == before)

# ---------- T9: Cursor mdc front-matter ----------
print("\nT9  Cursor .mdc front-matter")
ct = mod.CursorTarget()
cpt = ct.prompt_path(dh)
ctx = open(cpt, encoding="utf-8").read() if os.path.exists(cpt) else ""
chk("含 alwaysApply front-matter", "alwaysApply: true" in ctx and ctx.lstrip().startswith("---"), ctx[:60])

# ---------- T10: 菜单动态目标 ----------
print("\nT10  _pick_targets 动态生成 6 个目标")
ASK = []
replies = ["7", "1"]   # 先非法（7 是"全部"序号），再选 1
builtins_input = builtins.input
def fake(p=""):
    ASK.append(p); return replies.pop(0) if replies else ""
builtins.input = fake
buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
try:
    sel = mod._pick_targets(mkargs(), "测试")
finally:
    sys.stdout = old; builtins.input = builtins_input
out = buf.getvalue()
import re as _re
clean = _re.sub(r'\x1b\[[0-9;]*m', '', out)
chk("界面列出 Codex", "Codex" in clean)
chk("界面列出 Cursor", "Cursor" in clean)
chk("界面列出 Claude", "Claude Code" in clean)
chk("「全部」序号为 7", "[7] 全部" in clean, clean[-400:])

shutil.rmtree(tmp, ignore_errors=True)
print("\n" + "=" * 62)
print(f"结果: {len(PASS)} 项通过, {len(FAIL)} 项失败")
if FAIL:
    print("失败项:")
    for f in FAIL:
        print("  -", f)
print("=" * 62)
sys.exit(1 if FAIL else 0)
