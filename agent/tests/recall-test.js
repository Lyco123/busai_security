const { chromium } = require('playwright');

async function runRecallTest() {
  const browser = await chromium.launch({
    headless: false,
    slowMo: 500,
  });
  const context = await browser.newContext();
  const page = await context.newPage();

  // 导航到测试页面
  await page.goto('https://busodemo.canocache.com/assistant');
  await page.waitForLoadState('networkidle');

  console.log('浏览器已打开，请手动进行测试...');
  console.log('测试完成后按 Ctrl+C 关闭浏览器');

  // 保持浏览器打开
  await new Promise(() => {});
}

runRecallTest().catch(console.error);
