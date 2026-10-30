# -*- coding: utf-8 -*-
"""把新 UI（石墨/钠灯）注入 admin2.html。

源文件永远是 `_pristine.html`（原始 8.28 版面的干净副本），
输出 `admin2.html` —— 所以重复跑是幂等的，不会叠加补丁。
"""
import re, sys

SRC = "_pristine.html"
OUT = "admin2.html"

s = open(SRC, encoding="utf-8").read()
css = open("_ui.css", encoding="utf-8").read()
shell = open("_ui_shell.html", encoding="utf-8").read()


def rep(old, new, n=1, why=""):
    global s
    assert old in s, "未找到片段：%s" % (why or old[:40])
    s = s.replace(old, new, n)


# ---------------------------------------------------------------- 1) 样式层
i = s.index("<style>") + len("<style>")
j = s.index("</style>")
s = s[:i] + "\n" + css + s[j:]

# ---------------------------------------------------------------- 2) 骨架
a = s.index("<body>") + len("<body>")
b = s.index("<script>")
s = s[:a] + "\n\n" + shell + "\n\n" + s[b:]

# ---------------------------------------------------------------- 3) favicon
s = re.sub(
    r'<link rel="icon" href="data:image/svg\+xml,[^"]*">',
    "<link rel=\"icon\" href=\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg'"
    " viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%230c0e0d'/%3E"
    "%3Crect x='11' y='11' width='10' height='10' fill='%23f5b544'"
    " transform='rotate(45 16 16)'/%3E%3C/svg%3E\">",
    s, count=1)

# ------------------------------------------------- 4) kpi()：标签在上、数字在下
rep("""function kpi(n, l, cls) { return '<div class="kpi ' + (cls || '') + '"><div class="n">' + esc(n) + '</div><div class="l">' + esc(l) + '</div></div>' }""",
    """function kpi(n, l, cls) { return '<div class="kpi ' + (cls || '') + '"><div class="l">' + esc(l) + '</div><div class="n">' + esc(n) + '</div></div>' }""",
    why="kpi()")

# ---------------------------------------------------------------- 5) 骨架屏
rep("""  $('#view').innerHTML = '<div class="note" style="padding:20px">加载中…</div>';""",
    """  $('#view').innerHTML = '<div class="card"><div class="bd">' +
    '<div class="skel" style="width:26%"></div>' +
    '<div class="skel" style="width:74%;margin-top:12px"></div>' +
    '<div class="skel" style="width:58%;margin-top:10px"></div>' +
    '<div class="skel" style="width:66%;margin-top:10px"></div></div></div>';""",
    why="loading")

# --------------------------------------------------- 6) 顶栏时钟 + 网络状态点
anchor = """$('#btn-out').onclick = async function () { await api('logout', {}); showLogin('') };"""
rep(anchor, anchor + """

/* 顶栏时钟（浏览器本地时区 = 北京） */
(function () {
  var c = $('#clock'); if (!c) return;
  var p = function (n) { return (n < 10 ? '0' : '') + n };
  var tick = function () {
    var d = new Date();
    c.innerHTML = p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds()) + '<small>UTC+8</small>';
  };
  tick(); setInterval(tick, 1000);
})();
/* 网络状态点：在线呼吸，掉线变灰 */
window.addEventListener('offline', function () {
  var d = $('#netdot'); if (d) { d.className = 'dot off'; $('#hint').textContent = '离线' }
});
window.addEventListener('online', function () {
  var d = $('#netdot'); if (d) { d.className = 'dot on'; $('#hint').textContent = '已连接' }
});""", why="clock")

# ------------------------------------------- 7) 通知面板：只留一个主按钮
rep("""'<button class="btn p" id="nt-tg">发测试 Telegram</button>""",
    """'<button class="btn" id="nt-tg">发测试 Telegram</button>""", why="nt-tg")

# ------------------------------------------- 8) 广告位保存按钮：它是独立主操作
rep("""'<button class="btn p s" id="ad-save">保存广告位设置</button>""",
    """'<button class="btn p" id="ad-save">保存广告位设置</button>""", why="ad-save")

# ------------------------------------------- 9) 概览：KPI 文案不再自我重复
rep("""kpi(nk.online ? '在线' : '离线', 'QQ 大肥鱼 ' + (nk.name || ''), nk.online ? 'g' : 'r')""",
    """kpi(nk.online ? '在线' : '离线', 'QQ 机器人（' + (nk.name || '-') + '）', nk.online ? 'g' : 'r')""",
    why="home napcat kpi")

rep("""kpi(st.logins_today || 0, '今日登录次数', 'b') +
    kpi(st.devices_today || 0, '今日活跃设备', 'b') +""",
    """kpi(st.logins_today || 0, '今日登录次数') +
    kpi(st.devices_today || 0, '今日活跃设备') +""",
    why="home counts")

# ------------------------- 10) 健康检查：磁盘只显示占用率，证书日期去掉 GMT
rep("""  var sy = h.sys || {};
  html += card('主机', '<div class="grid">' +""",
    """  var sy = h.sys || {};
  var dk = h.disk || {};
  var dp = parseFloat(dk.pct) || 0;
  html += card('主机', '<div class="grid">' +""", why="disk vars")

rep("""    kpi((h.disk || {}).text || '-', '磁盘') +""",
    """    kpi(dk.pct || '-', '磁盘（' + (dk.total || '?') + ' 中可用 ' + (dk.avail || '?') + '）', dp >= 85 ? 'w' : '') +""",
    why="disk kpi")

rep("""  var c = h.cert || {};
  if (c.not_after) html += card('证书', '<div class="row"><span class="tag ' + (c.days > 14 ? 'ok' : 'warn') + '">到期 ' + esc(c.not_after) + '</span><span class="note">剩余 ' + esc(c.days) + ' 天</span></div>');""",
    """  var c = h.cert || {};
  var cna = c.not_after || '';
  try {
    var cd = new Date(cna);
    if (!isNaN(cd.getTime())) cna = cd.getFullYear() + '-' + ('0' + (cd.getMonth() + 1)).slice(-2) + '-' + ('0' + cd.getDate()).slice(-2);
  } catch (e) { }
  if (c.not_after) html += card('证书', '<div class="row"><span class="tag ' + (c.days > 14 ? 'ok' : 'warn') + '">到期 ' + esc(cna) + '</span><span class="note">剩余 ' + esc(c.days) + ' 天</span></div>');""",
    why="cert")

# ------------- 11) 数据仓库：趋势可能是 {日期: 次数} 字典，两种形状都认
rep("""      var p = c.split(':'), arr = (d[p[0]] || []);""",
    """      var p = c.split(':'), arr = (d[p[0]] || []);
      if (!Array.isArray(arr)) arr = Object.keys(arr).sort().map(function (k) { return { d: k, n: arr[k] } });""",
    why="db daily shape")

# ------------- 12) 看板：文案里「蓝色」是旧配色的残留
rep("""蓝色为登录次数，同日设备数见下钻：数据仓库 → 趋势。""",
    """琥珀色为登录次数，同日设备数见下钻：数据仓库 → 趋势。""",
    why="dash copy")

# ------------- 13) 看板 KPI：普通计数不再占用强调色
rep("""kpi(s.logins_today, '今日登录次数', 'b') + kpi(s.devices_today, '今日活跃设备', 'b') +""",
    """kpi(s.logins_today, '今日登录次数') + kpi(s.devices_today, '今日活跃设备') +""",
    why="dash kpi")

# ------------- 15) 指标格子数能整除时用定列数，最后一行不留空格
rep("""  var s = r.stats || {};
  var html = '<div class="grid" style="margin-bottom:14px">' +""",
    """  var s = r.stats || {};
  var html = '<div class="grid c4" style="margin-bottom:14px">' +""",
    why="dash grid")

rep("""  var html = '<div class="grid" style="margin-bottom:14px">' +
    kpi(r.codes, '激活码') + kpi(r.codes_bound, '已绑定', 'g') +""",
    """  var html = '<div class="grid c3" style="margin-bottom:14px">' +
    kpi(r.codes, '激活码') + kpi(r.codes_bound, '已绑定', 'g') +""",
    why="db grid")

open(OUT, "w", encoding="utf-8").write(s)
print("patched ->", OUT, "size =", len(s))
