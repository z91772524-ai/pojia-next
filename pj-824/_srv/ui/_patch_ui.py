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
    " viewBox='0 0 32 32'%3E%3Crect width='32' height='32' fill='%230d0f0e'/%3E"
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
    '<div class="skel" style="width:22%"></div>' +
    '<div class="skel" style="width:64%;margin-top:14px"></div>' +
    '<div class="skel" style="width:50%;margin-top:12px"></div>' +
    '<div class="skel" style="width:58%;margin-top:12px"></div></div></div>';""",
    why="loading")

# ------------------------ 5b) api() 挂上顶部加载条（结束后收掉按钮转圈）
rep("""async function api(path, body, method) {
  var opt = { method: method || (body !== undefined ? 'POST' : 'GET'), headers: {}, credentials: 'same-origin' };
  if (body !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body) }
  var r = await fetch('/adm/api/' + path, opt);
  if (r.status === 401) { showLogin('登录已过期，重新登录'); throw new Error('未登录') }
  var t = await r.text();
  try { return JSON.parse(t) } catch (e) { return { ok: 0, err: '响应不是 JSON：' + t.slice(0, 100) } }
}""",
    """async function api(path, body, method) {
  pbStart();
  try {
    var opt = { method: method || (body !== undefined ? 'POST' : 'GET'), headers: {}, credentials: 'same-origin' };
    if (body !== undefined) { opt.headers['Content-Type'] = 'application/json'; opt.body = JSON.stringify(body) }
    var r = await fetch('/adm/api/' + path, opt);
    if (r.status === 401) { showLogin('登录已过期，重新登录'); throw new Error('未登录') }
    var t = await r.text();
    try { return JSON.parse(t) } catch (e) { return { ok: 0, err: '响应不是 JSON：' + t.slice(0, 100) } }
  } finally { pbEnd(); busyEnd() }
}""", why="api()")

# --------------------- 6) 运行时：顶部加载条 / 按钮转圈 / 时钟 / 网络状态
anchor = """$('#btn-out').onclick = async function () { await api('logout', {}); showLogin('') };"""
rep(anchor, anchor + """

/* ---------- 顶部加载条 ---------- */
var PBW = 0, PBT = null, PBHIDE = null, PBN = 0;
function pbStart() {
  PBN++; clearTimeout(PBHIDE);
  var el = $('#pbar'); if (!el) return;
  el.classList.add('on');
  PBW = Math.min(88, PBW + 16); el.style.width = PBW + '%';
  clearTimeout(PBT);
  PBT = setTimeout(function () { PBW = Math.min(94, PBW + 5); el.style.width = PBW + '%' }, 800);
}
function pbEnd() {
  PBN = Math.max(0, PBN - 1); if (PBN > 0) return;
  var el = $('#pbar'); if (!el) return;
  clearTimeout(PBT); el.style.width = '100%';
  clearTimeout(PBHIDE);
  PBHIDE = setTimeout(function () {           /* 连续请求之间不闪，留 320ms 缓冲 */
    el.classList.remove('on');
    setTimeout(function () { el.style.width = '0'; PBW = 0 }, 300);
  }, 320);
}

/* ---------- 按钮转圈：点了先不动，超过 160ms 才转，避免闪 ---------- */
var PBDONE = [];
function busyEnd() { var f = PBDONE.splice(0); for (var i = 0; i < f.length; i++) f[i]() }
document.addEventListener('click', function (e) {
  var b = e.target && e.target.closest ? e.target.closest('.btn') : null;
  if (!b || b.tagName === 'A' || b.disabled) return;
  var t = setTimeout(function () { b.classList.add('isbusy') }, 160);
  var done = function () { clearTimeout(t); b.classList.remove('isbusy') };
  PBDONE.push(done);
  setTimeout(done, 8000);
});

/* ---------- 顶栏时钟（浏览器本地时区 = 北京） ---------- */
(function () {
  var c = $('#clock'); if (!c) return;
  var p = function (n) { return (n < 10 ? '0' : '') + n };
  var tick = function () {
    var d = new Date();
    c.innerHTML = p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds()) + '<small>UTC+8</small>';
  };
  tick(); setInterval(tick, 1000);
})();
/* ---------- 网络状态点：在线呼吸，掉线变灰 ---------- */
window.addEventListener('offline', function () {
  var d = $('#netdot'); if (d) { d.className = 'dot off'; $('#hint').textContent = '离线' }
});
window.addEventListener('online', function () {
  var d = $('#netdot'); if (d) { d.className = 'dot on'; $('#hint').textContent = '已连接' }
});""", why="runtime")

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

# ------------- 16) 统计图：柱状 → 波峰波谷（平滑曲线 + 峰/谷标注） -------------
rep("""function bars(vals, labels) {
  var max = Math.max.apply(null, vals.concat([1]));
  return '<div class="bar">' + vals.map(function (v, i) {
    return '<i style="height:' + Math.max(2, Math.round(v / max * 100)) + '%" title="' + esc((labels || [])[i] || '') + '：' + v + '"></i>'
  }).join('') + '</div>' + (labels ? '<div class="note" style="display:flex;justify-content:space-between;font-size:10px;margin-top:4px"><span>' + esc(labels[0] || '') + '</span><span>' + esc(labels[labels.length - 1] || '') + '</span></div>' : '');
}""",
    """var WVID = 0;
function bars(vals, labels) {
  vals = (vals || []).map(function (v) { return Number(v) || 0 });
  labels = labels || [];
  var n = vals.length;
  if (!n) return '<div class="note">没有数据</div>';
  var single = n === 1;
  if (single) { vals = [vals[0], vals[0]]; n = 2 }

  var W = 1000, H = 150, PT = 18, PB = 8;
  var mx = Math.max.apply(null, vals), mn = Math.min.apply(null, vals);
  var span = mx - mn, lo, hi;
  if (span <= 0) { var pad = Math.max(1, mx * .4); lo = mn - pad; hi = mx + pad }
  else { lo = mn - span * .18; hi = mx + span * .18 }
  var rng = hi - lo || 1;
  var X = function (i) { return i * W / (n - 1) };
  var Y = function (v) { return PT + (1 - (v - lo) / rng) * (H - PT - PB) };
  var pts = vals.map(function (v, i) { return [X(i), Y(v)] });

  /* Catmull-Rom 转三次贝塞尔：线要顺，但不能过冲失真 */
  var d = 'M' + pts[0][0].toFixed(1) + ',' + pts[0][1].toFixed(1);
  for (var i = 0; i < n - 1; i++) {
    var p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
    d += ' C' + (p1[0] + (p2[0] - p0[0]) / 6).toFixed(1) + ',' + (p1[1] + (p2[1] - p0[1]) / 6).toFixed(1) +
      ' ' + (p2[0] - (p3[0] - p1[0]) / 6).toFixed(1) + ',' + (p2[1] - (p3[1] - p1[1]) / 6).toFixed(1) +
      ' ' + p2[0].toFixed(1) + ',' + p2[1].toFixed(1);
  }
  var uid = 'wg' + (++WVID);
  var dots = '';
  if (n <= 34) dots = vals.map(function (v, i) {
    return '<i class="wd" style="left:' + (X(i) / W * 100).toFixed(2) + '%;top:' + (Y(v) / H * 100).toFixed(2) +
      '%" title="' + esc(labels[i] || '') + '：' + v + '"></i>';
  }).join('');

  var mi = vals.indexOf(mx), ni = vals.indexOf(mn);
  var pk = (!single && span > 0)
    ? '<span class="pk" style="left:' + Math.min(93, Math.max(7, X(mi) / W * 100)).toFixed(2) + '%;top:' +
    (Y(mx) / H * 100).toFixed(2) + '%">峰 ' + mx + '</span>' : '';
  var vl = (!single && span > 0)
    ? '<span class="vl">谷 ' + mn + (labels[ni] != null && labels[ni] !== '' ? ' · ' + esc(labels[ni]) : '') + '</span>'
    : '<span class="vl">&nbsp;</span>';

  return '<div class="wave">' +
    '<svg viewBox="0 0 ' + W + ' ' + H + '" preserveAspectRatio="none" role="img" aria-label="走势波峰波谷图">' +
    '<defs><linearGradient id="' + uid + '" x1="0" y1="0" x2="0" y2="1">' +
    '<stop offset="0" style="stop-color:var(--acc);stop-opacity:.34"/>' +
    '<stop offset="1" style="stop-color:var(--acc);stop-opacity:0"/></linearGradient></defs>' +
    '<path d="' + d + ' L' + W + ',' + H + ' L0,' + H + ' Z" style="fill:url(#' + uid + ')"/>' +
    '<line x1="0" y1="' + (H - PB) + '" x2="' + W + '" y2="' + (H - PB) + '" style="stroke:var(--line2)" stroke-width="1" vector-effect="non-scaling-stroke"/>' +
    '<path d="' + d + '" style="fill:none;stroke:var(--acc)" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>' +
    '</svg>' + dots + pk +
    '</div>' +
    '<div class="wlab"><span>' + esc(labels[0] != null ? labels[0] : '') + '</span>' + vl +
    '<span>' + esc(labels[labels.length - 1] != null ? labels[labels.length - 1] : '') + '</span></div>';
}""", why="bars -> wave")

# ------------- 17) 导航：支持 垂直 / 水平 / 混合 / 双列 四种布局 -------------
rep("""function buildNav() {
  var h = '';
  NAV.forEach(function (g) {
    h += '<div class="gt">' + esc(g[0]) + '</div>';
    g[1].forEach(function (it) { h += '<button data-sec="' + it[0] + '">' + esc(it[1]) + '</button>' });
  });
  $('#nav').innerHTML = h;
  $$('#nav button').forEach(function (b) { b.onclick = function () { go(b.dataset.sec) } });
}""",
    """function buildNav() {
  var nav = $('#nav'), gt = $('#gtabs');
  if (!nav) return;
  var L = effLayout(), h = '', g = '';
  if (CUR && CUR !== LKS) { LKS = CUR; var q = groupOf(CUR); if (q >= 0) LKG = q }
  if ((L === 'm' || L === 'd') && (LKG < 0 || LKG >= NAV.length)) LKG = 0;

  if (L === 'v') {
    NAV.forEach(function (grp) {
      h += '<div class="gt">' + esc(grp[0]) + '</div>';
      grp[1].forEach(function (it) { h += '<button data-sec="' + it[0] + '">' + esc(it[1]) + '</button>' });
    });
    if (gt) { gt.innerHTML = ''; gt.hidden = true }
  } else if (L === 'h') {
    NAV.forEach(function (grp) {
      h += '<div class="navdd"><button type="button" class="gb">' + esc(grp[0]) + '<i></i></button><div class="sub">' +
        grp[1].map(function (it) { return '<button data-sec="' + it[0] + '">' + esc(it[1]) + '</button>' }).join('') +
        '</div></div>';
    });
    if (gt) { gt.innerHTML = ''; gt.hidden = true }
  } else {
    g = NAV.map(function (grp, i) {
      return '<button type="button" class="gc' + (i === LKG ? ' on' : '') + '" data-g="' + i + '">' + esc(grp[0]) + '</button>';
    }).join('');
    h = '<div class="gt">' + esc(NAV[LKG][0]) + '</div>' +
      NAV[LKG][1].map(function (it) { return '<button data-sec="' + it[0] + '">' + esc(it[1]) + '</button>' }).join('');
    if (gt) { gt.innerHTML = g; gt.hidden = false }
  }
  nav.innerHTML = h;
  bindNav();
}""", why="buildNav")

# ------------- 18) 导航里加「外观设置」 -------------
rep("""['audit', '操作审计'], ['search', '跨表搜索'], ['passwd', '改密码']]]""",
    """['audit', '操作审计'], ['search', '跨表搜索'], ['passwd', '改密码'],
    ['look', '外观设置']]]""", why="nav look")

# ------------- 19) go()：记住标签页 + 跟随分组 + 切换动画 -------------
rep("""async function go(sec) {
  CUR = sec;
  $$('#nav button').forEach(function (b) { b.classList.toggle('on', b.dataset.sec === sec) });
  $('#ttl').textContent = titleOf(sec);
  location.hash = '#/' + sec;""",
    """async function go(sec) {
  CUR = sec;
  var _g = groupOf(sec);
  if (_g >= 0 && (effLayout() === 'm' || effLayout() === 'd') && _g !== LKG) { LKG = _g; buildNav() }
  markNav(sec);
  $('#ttl').textContent = titleOf(sec);
  location.hash = '#/' + sec;
  tabSync(sec);""", why="go head")

rep("""  catch (e) { $('#view').innerHTML = card('出错了', '<div class="logbox">' + esc(e.message || e) + '</div>') }
}""",
    """  catch (e) { $('#view').innerHTML = card('出错了', '<div class="logbox">' + esc(e.message || e) + '</div>') }
  animView();
}""", why="go anim")

# ------------- 12b) toast 做成 aria-live，屏幕阅读器能听到 -------------
rep("""var t = $('.toast'); if (!t) { t = document.createElement('div'); t.className = 'toast'; document.body.appendChild(t) }""",
    """var t = $('.toast'); if (!t) { t = document.createElement('div'); t.className = 'toast'; t.setAttribute('role', 'status'); t.setAttribute('aria-live', 'polite'); document.body.appendChild(t) }""",
    why="toast a11y")

# =====================================================================
# 20) 外观引擎：主题 / 菜单布局 / 菜单风格 / 主题色 / 圆角 / 背景图
# =====================================================================
LOOK_JS = r"""
/* ================================================================
   外观：主题 / 菜单布局 / 菜单风格 / 主题色 / 圆角 / 自定义背景图
   全部存 localStorage，只作用于本机浏览器，不动服务器上的任何东西
   ================================================================ */
var LKK = 'pa_look_v1';
var LOOK = {
  theme: 'dark', layout: 'v', mstyle: 'r', acc: '#f2b455',
  tabbar: 1, tabstyle: 'd', anim: 'l', rad: 0.75, bg: '', bga: 30
};
var LKG = 0, LKS = '', TABL = [], LWID = 0;
try {
  var _lo = JSON.parse(localStorage.getItem(LKK) || '{}');
  for (var _k in LOOK) if (_lo[_k] !== undefined && _lo[_k] !== null) LOOK[_k] = _lo[_k];
} catch (e) { }

function lookSave() {
  try { localStorage.setItem(LKK, JSON.stringify(LOOK)) }
  catch (e) { toast('本机存储满了，换一张更小的背景图', true) }
}
function lookSet(p) { for (var k in p) LOOK[k] = p[k]; lookSave(); applyLook() }

function hex2rgb(h) {
  h = String(h || '').replace('#', '');
  if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  var n = parseInt(h, 16) || 0;
  return [n >> 16 & 255, n >> 8 & 255, n & 255];
}
function mixHex(a, b, t) {
  var A = hex2rgb(a), B = hex2rgb(b), o = '#';
  for (var i = 0; i < 3; i++) {
    var v = Math.round(A[i] + (B[i] - A[i]) * t).toString(16);
    o += ('0' + v).slice(-2);
  }
  return o;
}
function effTheme() {
  if (LOOK.theme === 'auto') {
    return (window.matchMedia && matchMedia('(prefers-color-scheme: light)').matches) ? 'light' : 'dark';
  }
  return LOOK.theme === 'light' ? 'light' : 'dark';
}
function effLayout() { return window.innerWidth <= 900 ? 'v' : (LOOK.layout || 'v') }

function applyLook() {
  var R = document.documentElement, th = effTheme(), L = effLayout();
  R.setAttribute('data-theme', th);
  var acc = LOOK.acc || '#f2b455';
  if (th === 'light') acc = mixHex(acc, '#0a0f0b', .34);   /* 浅底上同一个色要压暗一档，字才看得清 */
  R.style.setProperty('--acc', acc);
  var k = Number(LOOK.rad); if (isNaN(k)) k = .75;
  R.style.setProperty('--rad', Math.round(10 * k) + 'px');
  R.style.setProperty('--rad-s', Math.round(8 * k) + 'px');

  var app = $('#app');
  if (app) {
    ['lay-v', 'lay-h', 'lay-m', 'lay-d'].forEach(function (c) { app.classList.remove(c) });
    app.classList.add('lay-' + L);
    app.setAttribute('data-anim', LOOK.anim || 'l');
    app.setAttribute('data-tabstyle', LOOK.tabstyle || 'd');
    app.setAttribute('data-ms', LOOK.mstyle || 'r');
  }
  var bg = $('#bg');
  if (bg) {
    if (LOOK.bg) {
      bg.style.backgroundImage = 'url("' + LOOK.bg + '")';
      bg.style.opacity = (Number(LOOK.bga) || 0) / 100;
    } else { bg.style.backgroundImage = 'none'; bg.style.opacity = 0 }
  }
  buildNav();
  syncTabs();
  if (CUR) markNav(CUR);
}

/* ---------- 导航：四种布局 ---------- */
function groupOf(sec) {
  for (var i = 0; i < NAV.length; i++)
    for (var j = 0; j < NAV[i][1].length; j++) if (NAV[i][1][j][0] === sec) return i;
  return -1;
}
function bindNav() {
  $$('#nav button[data-sec]').forEach(function (b) {
    b.onclick = function () { go(b.dataset.sec); closeDD() };
  });
  $$('#gtabs button[data-g]').forEach(function (b) {
    b.onclick = function () { LKG = Number(b.dataset.g); buildNav(); markNav(CUR) };
  });
  $$('#nav .navdd>.gb').forEach(function (b) {
    b.onclick = function (e) {
      e.stopPropagation();
      var p = b.parentNode, on = p.classList.contains('open');
      $$('#nav .navdd').forEach(function (x) { x.classList.remove('open') });
      if (!on) p.classList.add('open');
    };
  });
}
function closeDD() { $$('#nav .navdd').forEach(function (x) { x.classList.remove('open') }) }
document.addEventListener('click', function (e) {
  if (!e.target || !e.target.closest || !e.target.closest('.navdd')) closeDD();
});
function markNav(sec) {
  $$('#nav button[data-sec]').forEach(function (b) { b.classList.toggle('on', b.dataset.sec === sec) });
  var g = groupOf(sec);
  $$('#gtabs button[data-g]').forEach(function (b) { b.classList.toggle('on', Number(b.dataset.g) === g) });
}

/* ---------- 多标签栏 ---------- */
function tabSync(sec) {
  if (!LOOK.tabbar) { syncTabs(); return }
  if (TABL.indexOf(sec) < 0) TABL.push(sec);
  while (TABL.length > 9) TABL.shift();
  syncTabs();
}
function syncTabs() {
  var el = $('#tabs'); if (!el) return;
  el.classList.toggle('on', !!LOOK.tabbar);
  if (!LOOK.tabbar) { el.innerHTML = ''; return }
  el.innerHTML = TABL.map(function (s) {
    return '<button type="button" class="tb' + (s === CUR ? ' on' : '') + '" data-t="' + esc(s) + '">' +
      esc(titleOf(s)) + '<i class="x" data-x="' + esc(s) + '">×</i></button>';
  }).join('');
  $$('#tabs .tb').forEach(function (b) {
    b.onclick = function (e) {
      var x = e.target && e.target.getAttribute ? e.target.getAttribute('data-x') : null;
      if (x) { tabClose(x); return }
      go(b.dataset.t);
    };
  });
}
function tabClose(sec) {
  var i = TABL.indexOf(sec); if (i < 0) return;
  TABL.splice(i, 1);
  if (CUR === sec) {
    var nx = TABL[i] || TABL[i - 1] || 'home';
    CUR = ''; go(nx);
  } else syncTabs();
}
function animView() {
  var v = $('#view'); if (!v) return;
  v.classList.remove('a'); void v.offsetWidth; v.classList.add('a');
}

/* ---------- 缩略图（纯 SVG 画，不用图片素材） ---------- */
function pvSvg(kind) {
  var dark = effTheme() === 'dark';
  var acc = (getComputedStyle(document.documentElement).getPropertyValue('--acc') || '#f2b455').trim();
  var bgc = dark ? '#0f1311' : '#eef0ec';
  var pn = dark ? '#1b201d' : '#ffffff';
  var ln = dark ? '#2e352f' : '#dbdfd7';
  var tx = dark ? '#4d564f' : '#c4cac1';
  function r(x, y, w, h, f, rd) {
    return '<rect x="' + x + '" y="' + y + '" width="' + w + '" height="' + h + '" rx="' +
      (rd == null ? 2 : rd) + '" style="fill:' + f + '"/>';
  }
  var s = '<svg viewBox="0 0 74 48" width="74" height="48" aria-hidden="true">' + r(0, 0, 74, 48, bgc, 0);

  if (kind === 'th-dark' || kind === 'th-light') {
    var p2 = kind === 'th-light' ? '#ffffff' : '#181d1a';
    var l2 = kind === 'th-light' ? '#e2e6de' : '#2b322d';
    var t2 = kind === 'th-light' ? '#ccd2c9' : '#454e48';
    s += r(0, 0, 74, 48, p2, 0) + r(0, 0, 20, 48, l2, 0) +
      r(4, 8, 12, 3, t2, 1) + r(4, 16, 12, 3, t2, 1) + r(4, 24, 12, 3, t2, 1) +
      r(25, 9, 42, 8, l2, 2) + r(25, 22, 34, 5, l2, 2) + r(25, 31, 40, 5, l2, 2);
  } else if (kind === 'th-auto') {
    s += r(0, 0, 74, 48, '#181d1a', 0) + r(0, 0, 37, 48, '#ffffff', 0) +
      r(5, 9, 27, 6, '#e2e6de', 2) + r(5, 20, 20, 4, '#e2e6de', 2) + r(5, 28, 24, 4, '#e2e6de', 2) +
      r(42, 9, 27, 6, '#2b322d', 2) + r(42, 20, 20, 4, '#2b322d', 2) + r(42, 28, 24, 4, '#2b322d', 2);
  } else if (kind === 'lay-v') {
    s += r(0, 0, 74, 48, pn, 0) + r(0, 0, 19, 48, ln, 0) +
      r(4, 8, 11, 3, tx, 1) + r(4, 15, 11, 3, tx, 1) + r(4, 22, 11, 3, tx, 1) + r(4, 29, 11, 3, tx, 1) +
      r(25, 8, 43, 7, ln, 2) + r(25, 19, 43, 5, ln, 2) + r(25, 28, 28, 5, ln, 2);
  } else if (kind === 'lay-h') {
    s += r(0, 0, 74, 48, pn, 0) + r(0, 0, 74, 11, ln, 0) +
      r(4, 4, 7, 3, tx, 1) + r(15, 4, 7, 3, tx, 1) + r(26, 4, 7, 3, tx, 1) + r(37, 4, 7, 3, tx, 1) +
      r(6, 17, 62, 7, ln, 2) + r(6, 28, 62, 5, ln, 2) + r(6, 37, 40, 5, ln, 2);
  } else if (kind === 'lay-m') {
    s += r(0, 0, 74, 48, pn, 0) + r(0, 0, 74, 11, ln, 0) + r(0, 11, 18, 37, ln, 0) +
      r(3, 4, 8, 3, tx, 1) + r(14, 4, 8, 3, tx, 1) + r(25, 4, 8, 3, tx, 1) +
      r(4, 17, 11, 3, tx, 1) + r(4, 24, 11, 3, tx, 1) + r(4, 31, 11, 3, tx, 1) +
      r(23, 17, 45, 7, ln, 2) + r(23, 28, 45, 5, ln, 2) + r(23, 37, 30, 5, ln, 2);
  } else if (kind === 'lay-d') {
    s += r(0, 0, 74, 48, pn, 0) + r(0, 0, 13, 48, ln, 0) +
      r(12, 0, 20, 48, dark ? '#232925' : '#f4f6f2', 0) +
      r(2, 9, 9, 3, tx, 1) + r(2, 17, 9, 3, tx, 1) + r(2, 25, 9, 3, tx, 1) +
      r(15, 9, 14, 3, tx, 1) + r(15, 17, 14, 3, tx, 1) + r(15, 25, 14, 3, tx, 1) +
      r(38, 9, 32, 7, ln, 2) + r(38, 20, 32, 5, ln, 2) + r(38, 29, 22, 5, ln, 2);
  } else if (kind === 'ms-r') {
    s += r(0, 0, 74, 48, pn, 0);
    s += '<rect x="4" y="5" width="66" height="8" rx="3" style="fill:' + acc + '"/>' +
      r(9, 8, 20, 2, dark ? '#17190f' : '#ffffff', 1);
    [17, 26, 35].forEach(function (y) { s += r(9, y, 22, 2, tx, 1) });
  } else if (kind === 'ms-b') {
    s += r(0, 0, 74, 48, pn, 0);
    s += '<rect x="4.5" y="5.5" width="65" height="7" rx="3" fill="none" stroke-width="1" style="stroke:' + acc + '"/>' +
      r(9, 8, 20, 2, acc, 1);
    [17, 26, 35].forEach(function (y) { s += r(9, y, 22, 2, tx, 1) });
  } else {
    s += r(0, 0, 74, 48, pn, 0);
    s += r(4, 20, 66, 7, dark ? '#232925' : '#f0f2ed', 0) + r(4, 20, 2, 7, acc, 0) + r(9, 22, 20, 2, acc, 1);
    [8, 13, 31, 36, 41].forEach(function (y) { s += r(9, y, 20, 1.6, tx, 1) });
  }
  return s + '</svg>';
}

/* ---------- 面板 ---------- */
function lkRow(label, ctl) { return '<div class="cr"><span>' + esc(label) + '</span>' + ctl + '</div>' }
function lkSel(id, opts, cur) {
  return '<select id="' + id + '">' + opts.map(function (o) {
    return '<option value="' + o[0] + '"' + (String(o[0]) === String(cur) ? ' selected' : '') + '>' + o[1] + '</option>';
  }).join('') + '</select>';
}
PANELS.look = async function () {
  var acc = String(LOOK.acc || '#f2b455').toLowerCase();
  var h = '';
  h += '<div class="grp"><div class="gh">主题风格</div><div class="pick">' +
    [['dark', '深色'], ['light', '浅色'], ['auto', '跟随系统']].map(function (o) {
      return '<button type="button" class="pcard' + (LOOK.theme === o[0] ? ' on' : '') +
        '" data-k="theme" data-v="' + o[0] + '"><span class="pv">' + pvSvg('th-' + o[0]) +
        '</span><b>' + o[1] + '</b></button>';
    }).join('') + '</div></div>';

  h += '<div class="grp"><div class="gh">菜单布局</div><div class="pick">' +
    [['v', '垂直'], ['h', '水平'], ['m', '混合'], ['d', '双列']].map(function (o) {
      return '<button type="button" class="pcard' + (LOOK.layout === o[0] ? ' on' : '') +
        '" data-k="layout" data-v="' + o[0] + '"><span class="pv">' + pvSvg('lay-' + o[0]) +
        '</span><b>' + o[1] + '</b></button>';
    }).join('') + '</div>' +
    '<div class="note" style="margin-top:10px">手机上会自动回到单行横滚导航，这里选了也不影响。</div></div>';

  h += '<div class="grp"><div class="gh">菜单风格</div><div class="pick">' +
    [['r', '圆角高亮'], ['b', '描边高亮'], ['c', '紧凑列表']].map(function (o) {
      return '<button type="button" class="pcard' + (LOOK.mstyle === o[0] ? ' on' : '') +
        '" data-k="mstyle" data-v="' + o[0] + '"><span class="pv">' + pvSvg('ms-' + o[0]) +
        '</span><b>' + o[1] + '</b></button>';
    }).join('') + '</div></div>';

  h += '<div class="grp"><div class="gh">系统主题色</div><div class="pick" style="align-items:center">' +
    ['#8b7bf0', '#6f7bf7', '#3b82f6', '#22b573', '#20bfd6', '#f2b455', '#ef6aa6'].map(function (c) {
      return '<button type="button" class="cdot' + (acc === c ? ' on' : '') + '" data-acc="' + c +
        '" style="--c:' + c + '" aria-label="主题色 ' + c + '">' + (acc === c ? '✓' : '') + '</button>';
    }).join('') +
    '<span style="width:1px;height:22px;background:var(--line);margin:0 3px"></span>' +
    '<input type="color" id="lk-acc2" value="' + (LOOK.acc || '#f2b455') +
    '" title="自定义颜色" style="width:46px;height:30px;padding:2px;border-radius:8px">' +
    '</div></div>';

  h += '<div class="grp"><div class="gh">基础配置</div><div class="cfg">' +
    lkRow('开启多标签栏', '<label class="tg"><input type="checkbox" id="lk-tab"' + (LOOK.tabbar ? ' checked' : '') + '><i></i></label>') +
    lkRow('标签页风格', lkSel('lk-tabstyle', [['d', '默认'], ['dot', '圆点'], ['card', '卡片']], LOOK.tabstyle)) +
    lkRow('页面切换动画', lkSel('lk-anim', [['l', '左侧滑入'], ['f', '淡入'], ['u', '上滑'], ['n', '无动画']], LOOK.anim)) +
    lkRow('自定义圆角', lkSel('lk-rad', [['0', '直边 0'], ['0.5', '小圆角 0.5'], ['0.75', '标准 0.75'], ['1', '大圆角 1']], String(LOOK.rad))) +
    '</div></div>';

  h += '<div class="grp"><div class="gh">自定义背景图</div><div class="cfg">' +
    '<div class="cr" style="align-items:stretch">' +
    '<label class="drop" for="lk-file"><span>点这里选一张图片</span><small>自动压到 1920 宽以内，只存在这台设备，不上传服务器</small>' +
    '<input type="file" id="lk-file" accept="image/*" hidden></label>' +
    '<div class="thum' + (LOOK.bg ? ' on' : '') + '" id="lk-thum"' +
    (LOOK.bg ? ' style="background-image:url(&quot;' + LOOK.bg + '&quot;)"' : '') + '></div></div>' +
    lkRow('背景不透明度', '<input type="range" id="lk-bga" min="0" max="100" step="1" value="' + (LOOK.bga || 0) + '">') +
    '<div class="cr"><span>当前状态</span><span class="note" id="lk-bgmsg">' +
    (LOOK.bg ? '已应用' : '未设置，用纯色底') + '</span>' +
    '<button type="button" class="btn s" id="lk-bgclr"' + (LOOK.bg ? '' : ' disabled') + '>清除</button></div>' +
    '</div></div>';

  $('#view').innerHTML = card('外观设置',
    '<div class="note" style="margin:-4px 0 16px">这里的改动只作用于这台浏览器，不影响后台功能，也不影响别人看到的页面。换设备重新设一次即可。</div>' + h,
    { right: '<button class="btn s" id="lk-reset">恢复默认</button>' });
  bindLook();
};

/* ---------- 图片压缩：本地缩到 1920 宽，webp 优先 ---------- */
function encData(cv, q) {
  var u = '';
  try { u = cv.toDataURL('image/webp', q) } catch (e) { }
  if (!u || u.indexOf('image/webp') < 0) u = cv.toDataURL('image/jpeg', q);
  return u;
}
function compressImg(file, cb) {
  if (!/^image\//.test(file.type || '')) { toast('请选一张图片', true); return }
  var fr = new FileReader();
  fr.onload = function () {
    var im = new Image();
    im.onload = function () {
      var sc = Math.min(1, 1920 / (im.width || 1920));
      var w = Math.max(2, Math.round((im.width || 1920) * sc));
      var h2 = Math.max(2, Math.round((im.height || 1080) * sc));
      var cv = document.createElement('canvas'); cv.width = w; cv.height = h2;
      cv.getContext('2d').drawImage(im, 0, 0, w, h2);
      var q = .82, url = encData(cv, q);
      while (url.length > 1500000 && q > .38) { q -= .12; url = encData(cv, q) }
      if (url.length > 2400000) {
        var cv2 = document.createElement('canvas');
        cv2.width = Math.max(2, Math.round(w / 2)); cv2.height = Math.max(2, Math.round(h2 / 2));
        cv2.getContext('2d').drawImage(cv, 0, 0, cv2.width, cv2.height);
        url = encData(cv2, .7);
      }
      cb(url);
    };
    im.onerror = function () { toast('这张图读不出来', true) };
    im.src = fr.result;
  };
  fr.readAsDataURL(file);
}

function bindLook() {
  var v = $('#view');
  $$('.pcard[data-k]', v).forEach(function (b) {
    b.onclick = function () {
      var p = {}; p[b.dataset.k] = b.dataset.v;
      if (b.dataset.k === 'layout') { var q = groupOf(CUR); LKG = q < 0 ? 0 : q }
      lookSet(p); PANELS.look();
    };
  });
  $$('.cdot[data-acc]', v).forEach(function (b) {
    b.onclick = function () { lookSet({ acc: b.dataset.acc }); PANELS.look() };
  });
  /* 注意：一律用 this 取元素，不能共用一个闭包变量（会被后面的赋值覆盖） */
  function on(id, ev, fn) { var el = document.getElementById(id); if (el) el.addEventListener(ev, fn) }

  on('lk-acc2', 'input', function () { LOOK.acc = this.value; lookSave(); applyLook() });
  on('lk-tab', 'change', function () { lookSet({ tabbar: this.checked ? 1 : 0 }); PANELS.look() });
  on('lk-tabstyle', 'change', function () { lookSet({ tabstyle: this.value }); PANELS.look() });
  on('lk-anim', 'change', function () { lookSet({ anim: this.value }); PANELS.look() });
  on('lk-rad', 'change', function () { lookSet({ rad: Number(this.value) }); PANELS.look() });
  on('lk-bga', 'input', function () {
    LOOK.bga = Number(this.value); lookSave();
    var bg = $('#bg'); if (bg && LOOK.bg) bg.style.opacity = LOOK.bga / 100;
  });
  on('lk-file', 'change', function () {
    var f = this.files && this.files[0]; if (!f) return;
    var msg = $('#lk-bgmsg'); if (msg) msg.textContent = '正在处理…';
    compressImg(f, function (url) {
      LOOK.bg = url; lookSave(); applyLook();
      var th = $('#lk-thum');
      if (th) { th.classList.add('on'); th.style.backgroundImage = 'url("' + url + '")' }
      var m2 = $('#lk-bgmsg');
      if (m2) m2.textContent = '已应用 · ' + Math.round(url.length / 1024) + ' KB';
      var c = $('#lk-bgclr'); if (c) c.disabled = false;
      toast('背景图已应用');
    });
  });
  on('lk-bgclr', 'click', function () { lookSet({ bg: '' }); PANELS.look(); toast('背景图已清除') });
  on('lk-reset', 'click', function () {
    lookSet({ theme: 'dark', layout: 'v', mstyle: 'r', acc: '#f2b455', tabbar: 1, tabstyle: 'd', anim: 'l', rad: 0.75, bg: '', bga: 30 });
    PANELS.look(); toast('已恢复默认外观');
  });
}

/* ---------- 起效 ---------- */
applyLook();
if (window.matchMedia) {
  var _mq = matchMedia('(prefers-color-scheme: light)');
  var _mqv = function () { if (LOOK.theme === 'auto') applyLook() };
  if (_mq.addEventListener) _mq.addEventListener('change', _mqv);
  else if (_mq.addListener) _mq.addListener(_mqv);
}
window.addEventListener('resize', function () {
  clearTimeout(LWID); LWID = setTimeout(function () { applyLook() }, 200);
});
"""

_NETON = """window.addEventListener('online', function () {
  var d = $('#netdot'); if (d) { d.className = 'dot on'; $('#hint').textContent = '已连接' }
});"""
rep(_NETON, _NETON + "\n" + LOOK_JS, why="look engine")

open(OUT, "w", encoding="utf-8").write(s)
print("patched ->", OUT, "size =", len(s))
