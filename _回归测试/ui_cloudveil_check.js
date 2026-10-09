// 验证云验证浮层 UI：wait_group 输入框可见 + 错误分支
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1120, height: 800 } });
  await page.goto('http://127.0.0.1:8317/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2500); // cloudBoot + 首次 cloudPoll

  const r1 = await page.evaluate(() => {
    const form = document.querySelector('#cbox-form');
    const input = document.querySelector('#cloudgroup');
    const stat = document.querySelector('#cloudstat');
    const veil = document.querySelector('#cloudveil');
    return {
      veilShown: veil.classList.contains('show'),
      formDisplay: form ? form.style.display : 'NO FORM',
      inputVisible: input ? (input.offsetParent !== null) : false,
      stat: stat ? stat.textContent : 'NO STAT',
    };
  });
  console.log('[wait_group]', JSON.stringify(r1));

  // 输入错群号 → 点验证 → 错误分支（输入框应保持可见可改）
  await page.fill('#cloudgroup', '111222333');
  await page.click('#b-cloudgo');
  await page.waitForTimeout(3500); // 提交 + 服务器 403 + 轮询回显
  const r2 = await page.evaluate(() => ({
    formDisplay: document.querySelector('#cbox-form').style.display,
    inputVisible: document.querySelector('#cloudgroup').offsetParent !== null,
    stat: document.querySelector('#cloudstat').textContent,
    errClass: document.querySelector('#cloudstat').className,
  }));
  console.log('[error:GROUP]', JSON.stringify(r2));

  await browser.close();
  const ok1 = r1.veilShown && r1.formDisplay === 'flex' && r1.inputVisible;
  const ok2 = r2.formDisplay === 'flex' && r2.inputVisible
    && r2.stat.includes('群号不对') && !r2.stat.includes('1121243020');
  console.log(ok1 ? 'PASS wait_group 输入框可见' : 'FAIL wait_group');
  console.log(ok2 ? 'PASS 错误分支文案正确且不泄露群号' : 'FAIL error 分支: ' + r2.stat);
  process.exit(ok1 && ok2 ? 0 : 1);
})().catch(e => { console.error('ERR', e.message); process.exit(2); });
