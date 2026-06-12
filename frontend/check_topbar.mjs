import { chromium } from 'playwright';
const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
const page = await ctx.newPage();
await page.goto('http://localhost:3000/', { waitUntil: 'networkidle' });
const data = await page.evaluate(() => {
  const title = document.querySelector('header .font-redis-body');
  const img = document.querySelector('header img[alt="Redis"]');
  const r = title?.getBoundingClientRect();
  return {
    titleText: title?.textContent,
    titleWidth: r?.width,
    titleHeight: r?.height,
    wrapped: r ? r.height > 30 : null,
    imgSrc: img?.getAttribute('src'),
    imgRect: img?.getBoundingClientRect(),
    docTitle: document.title,
  };
});
await page.screenshot({ path: '/tmp/topbar_1280.png', clip: { x: 0, y: 0, width: 1280, height: 110 } });
console.log(JSON.stringify(data, null, 2));
await browser.close();
