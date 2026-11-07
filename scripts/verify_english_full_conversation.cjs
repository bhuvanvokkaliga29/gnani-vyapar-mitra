const path = require('path');
const { chromium } = require(path.resolve(__dirname, '../apps/web/node_modules/@playwright/test'));

async function runTest() {
  console.log('=== VERIFYING NATURAL ENGLISH CONVERSATION ===\n');
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

  console.log('1. Loading http://localhost:3000/voice-agent...');
  await page.goto('http://localhost:3000/voice-agent', { waitUntil: 'networkidle' });

  // Select English language pill
  console.log('2. Selecting English language mode...');
  await page.click('button:has-text("English")');
  await page.waitForTimeout(300);

  const inputSelector = 'input[placeholder*="Type question"]';

  const testTurns = [
    { q: 'Hello.', label: 'Greeting "Hello."' },
    { q: 'How are you?', label: 'Chit-chat "How are you?"' },
    { q: 'Thank you.', label: 'Pleasantry "Thank you."' },
    { q: 'I sent a WhatsApp message yesterday', label: 'Casual remark' },
    { q: 'What are my sales today?', label: 'Business Question (Daily Sales)' },
    { q: 'Which product is selling the most?', label: 'Follow-up (Top Seller)' },
    { q: 'How much stock is remaining in that product?', label: 'Contextual Stock Check' }
  ];

  for (let i = 0; i < testTurns.length; i++) {
    const turn = testTurns[i];
    console.log(`\n--- Turn ${i + 1}: ${turn.label} ---`);
    console.log(`User: "${turn.q}"`);

    const prevCardCount = await page.evaluate(() => 
      document.querySelectorAll('div[class*="bg-black border border-neutral-700"] p[class*="leading-snug"]').length
    );

    await page.fill(inputSelector, turn.q);
    await page.press(inputSelector, 'Enter');

    // Wait for the new assistant response card to be added
    try {
      await page.waitForFunction(
        (target) => document.querySelectorAll('div[class*="bg-black border border-neutral-700"] p[class*="leading-snug"]').length >= target,
        prevCardCount + 1,
        { timeout: 18000 }
      );
    } catch (e) {
      console.log('Timeout waiting for card count increment, continuing with current DOM state...');
    }
    await page.waitForTimeout(1000);

    const turnData = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('div[class*="bg-black border border-neutral-700"] p[class*="leading-snug"]'));
      const activeChip = Array.from(document.querySelectorAll('*')).find(el => el.textContent && el.textContent.includes('Active Context') && el.children.length === 0);
      const fallbackBtn = Array.from(document.querySelectorAll('button')).find(b => b.textContent && b.textContent.includes('Play Spoken Response'));
      return {
        spoken: cards.length > 0 ? cards[cards.length - 1].innerText : '',
        activeContext: activeChip ? activeChip.innerText : 'None',
        hasAutoplayBanner: !!fallbackBtn,
        scrollY: window.scrollY
      };
    });

    console.log(`Assistant Spoken: ${turnData.spoken}`);
    console.log(`Active Context: ${turnData.activeContext}`);
    console.log(`Autoplay Banner: ${turnData.hasAutoplayBanner ? 'FAIL (Requires manual click)' : 'PASS (Clean auto-play)'}`);
    console.log(`window.scrollY: ${turnData.scrollY} (Expected: 0)`);

    if (i < 4) {
      // Greetings and casual turns MUST NOT mention products
      const badMention = /shirt|linen|stock|units|42|pant|trouser/i.test(turnData.spoken);
      console.log(`Turn ${i + 1} Stale Context Leak: ${badMention ? 'FAIL (Mentions product)' : 'PASS (Clean social response)'}`);
    }
  }

  const finalCheck = await page.evaluate(() => ({
    scrollY: window.scrollY,
    docH: document.documentElement.scrollHeight,
    winH: window.innerHeight
  }));

  console.log('\nFinal Page Scroll Check:', finalCheck);
  console.log(`Window perfectly stationary: ${finalCheck.scrollY === 0 ? 'PASS' : 'FAIL'}`);

  await browser.close();
}

runTest().catch(e => {
  console.error('Test error:', e);
  process.exit(1);
});
