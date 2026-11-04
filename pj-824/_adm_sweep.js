const { chromium } = require('playwright');

const SECS = ['home', 'health', 'bot', 'role', 'model', 'social2', 'social1', 'slang', 'tokens',
  'sessions', 'wl', 'send', 'bridge', 'dash', 'db', 'data', 'board', 'ads', 'guiads', 'version',
  'notice', 'groups', 'income', 'unlim', 'words', 'settings', 'pirate', 'paycfg',
  'logs', 'backup', 'sql', 'notify', 'audit', 'search', 'passwd'];

(async () => {
  const b = await chromium.launch({ executablePath: 'C:/Users/19294/AppData/Local/ms-playwright/chromium-1223/chrome-win64/chrome.exe' });
  const pg = await b.newPage({ viewport: { width: 1440, height: 900 } });
  const errs = [];
  pg.on('console', m => { if (m.type() === 'error') errs.push('CONSOLE ' + m.text()) });
  pg.on('requestfailed', r => errs.push('REQFAIL ' + r.url()));
  pg.on('response', r => { if (r.status() >= 400) errs.push('HTTP ' + r.status() + ' ' + r.url()) });

  await pg.goto('http://85.189.41.16/adm/', { waitUntil: 'networkidle', timeout: 40000 });
  await pg.waitForSelector('#l-p', { state: 'visible' });
  await pg.fill('#l-p', '36925814A');
  await pg.click('#l-go');
  await pg.waitForFunction(() => document.getElementById('login').style.display === 'none', null, { timeout: 15000 });
  await pg.waitForTimeout(1500);

  const out = {};
  for (const s of SECS) {
    await pg.evaluate(sec => { location.hash = '#/' + sec }, s);
    await pg.waitForTimeout(180);
    await pg.evaluate(sec => window.go(sec), s).catch(() => {});
    await pg.waitForTimeout(1100);
    const r = await pg.evaluate(() => {
      const v = document.getElementById('view');
      const t = (v.innerText || '').replace(/\s+/g, ' ').trim();
      return { len: t.length, head: t.slice(0, 140), bad: /出错了|加载中…|未实现/.test(t) };
    });
    out[s] = r;
  }
  await pg.screenshot({ path: 'adm_health.png', fullPage: false });
  await pg.evaluate(() => window.go('sql')); await pg.waitForTimeout(1200);
  await pg.screenshot({ path: 'adm_sql.png' });
  await pg.evaluate(() => window.go('role')); await pg.waitForTimeout(1200);
  await pg.screenshot({ path: 'adm_role.png' });

  console.log(JSON.stringify({ out, errs: [...new Set(errs)] }, null, 1));
  await b.close();
})();
