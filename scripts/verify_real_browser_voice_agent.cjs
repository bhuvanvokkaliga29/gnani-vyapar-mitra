const path = require('path');
const { chromium } = require(path.resolve(__dirname, '../apps/web/node_modules/@playwright/test'));

async function runBrowserTests() {
  console.log('=== REAL-TIME VOICE-TO-VOICE ACCEPTANCE TEST ===\n');
  const browser = await chromium.launch({
    channel: 'msedge',
    headless: true,
    args: [
      '--autoplay-policy=no-user-gesture-required',
      '--use-fake-ui-for-media-stream',
      '--use-fake-device-for-media-stream'
    ]
  });

  const context = await browser.newContext({
    permissions: ['microphone'],
    viewport: { width: 1280, height: 800 }
  });

  const page = await context.newPage();

  const consoleLogs = [];
  page.on('console', msg => consoleLogs.push(msg.text()));

  console.log('1. Loading http://localhost:3000/voice-agent...');
  await page.goto('http://localhost:3000/voice-agent', { waitUntil: 'networkidle' });

  // 1. Initial Outer Layout Check
  const initialLayout = await page.evaluate(() => ({
    scrollY: window.scrollY,
    winH: window.innerHeight,
    docH: document.documentElement.scrollHeight
  }));
  console.log('Initial Layout:', initialLayout);
  console.log(`Document scrollable: ${initialLayout.docH > initialLayout.winH ? 'FAIL' : 'PASS (Strictly 100dvh)'}`);

  const inputSelector = 'input[placeholder*="Type question"]';

  // Test 1: User says "Hello."
  console.log('\n--- Test 1: User says "Hello." (Greeting Verification) ---');
  await page.fill(inputSelector, 'Hello.');
  await page.press(inputSelector, 'Enter');

  // Wait for assistant response to appear
  await page.waitForSelector('text=Gnani Timbre Audio', { timeout: 15000 });
  await page.waitForTimeout(1000);

  const turn1Data = await page.evaluate(() => {
    const banners = Array.from(document.querySelectorAll('button')).map(b => b.innerText);
    const spokenEl = document.querySelector('p[class*="text-white font-semibold"]');
    const activeChip = document.querySelector('div[class*="Active Context"]');
    return {
      spokenText: spokenEl ? spokenEl.innerText : '',
      hasFallbackBanner: banners.some(b => b.includes('Play Spoken Response')),
      activeContextChip: activeChip ? activeChip.innerText : 'None',
      scrollY: window.scrollY
    };
  });

  console.log('Turn 1 Spoken Greeting:', turn1Data.spokenText);
  console.log('Turn 1 Fallback Banner Displayed:', turn1Data.hasFallbackBanner ? 'FAIL (Requires click)' : 'PASS (Auto-played/Clean)');
  console.log('Turn 1 Active Context Chip:', turn1Data.activeContextChip);
  console.log('Turn 1 window.scrollY:', turn1Data.scrollY);

  // Check that "shirt" or "linen" is NOT mentioned in the greeting!
  const mentionsShirt = /shirt|linen|stock|units|42|pant/i.test(turn1Data.spokenText);
  console.log(`Greeting mentions product/stock: ${mentionsShirt ? 'FAIL (Stale context bug)' : 'PASS (Clean greeting!)'}`);

  // Test 2: User asks "What are my sales today?"
  console.log('\n--- Test 2: User asks "What are my sales today?" ---');
  await page.fill(inputSelector, 'What are my sales today?');
  await page.press(inputSelector, 'Enter');
  await page.waitForTimeout(5000);

  const turn2Data = await page.evaluate(() => {
    const allSpoken = Array.from(document.querySelectorAll('p[class*="text-white font-semibold"]')).map(el => el.innerText);
    return {
      latestSpoken: allSpoken[allSpoken.length - 1],
      scrollY: window.scrollY
    };
  });
  console.log('Turn 2 Spoken Sales:', turn2Data.latestSpoken);
  console.log('Turn 2 window.scrollY:', turn2Data.scrollY);

  // Test 3: Follow-up "Which product is selling the most?"
  console.log('\n--- Test 3: Follow-up "Which product is selling the most?" ---');
  await page.fill(inputSelector, 'Which product is selling the most?');
  await page.press(inputSelector, 'Enter');
  await page.waitForTimeout(5000);

  const turn3Data = await page.evaluate(() => {
    const allSpoken = Array.from(document.querySelectorAll('p[class*="text-white font-semibold"]')).map(el => el.innerText);
    return {
      latestSpoken: allSpoken[allSpoken.length - 1],
      scrollY: window.scrollY
    };
  });
  console.log('Turn 3 Spoken Top Product:', turn3Data.latestSpoken);

  // Test 4: Follow-up "How much stock is remaining in that product?"
  console.log('\n--- Test 4: Follow-up "How much stock is remaining in that product?" ---');
  await page.fill(inputSelector, 'How much stock is remaining in that product?');
  await page.press(inputSelector, 'Enter');
  await page.waitForTimeout(5000);

  const turn4Data = await page.evaluate(() => {
    const allSpoken = Array.from(document.querySelectorAll('p[class*="text-white font-semibold"]')).map(el => el.innerText);
    return {
      latestSpoken: allSpoken[allSpoken.length - 1],
      scrollY: window.scrollY
    };
  });
  console.log('Turn 4 Spoken Stock:', turn4Data.latestSpoken);
  console.log('Turn 4 window.scrollY:', turn4Data.scrollY);

  // Final check: Outer page must remain completely stationary at scrollY == 0
  const finalLayout = await page.evaluate(() => ({
    scrollY: window.scrollY,
    winH: window.innerHeight,
    docH: document.documentElement.scrollHeight
  }));
  console.log('\nFinal Layout Check:', finalLayout);
  console.log(`Overall Outer Window Stationary: ${finalLayout.scrollY === 0 ? 'PASS (Zero window drift)' : 'FAIL'}`);

  await browser.close();
}

runBrowserTests().catch(err => {
  console.error('Browser acceptance test failed:', err);
  process.exit(1);
});
