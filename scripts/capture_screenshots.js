const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const REPO_ROOT = '/Users/chetanajatpur/Desktop/clauseguard';
const SCREENSHOTS_DIR = path.join(REPO_ROOT, 'docs', 'screenshots');

async function main() {
  console.log('Launching browser with Arc executable...');
  const browser = await chromium.launch({
    executablePath: '/Applications/Arc.app/Contents/MacOS/Arc',
    headless: true,
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
  });
  const page = await context.newPage();

  console.log('Navigating to http://localhost:3000/#cockpit...');
  await page.goto('http://localhost:3000/#cockpit', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  // Helper to click sensitivity preset button
  async function selectPreset(presetKey) {
    const textLabel = presetKey === 'strict' ? 'Strict (3)' : presetKey === 'balanced' ? 'Balanced (8)' : 'Thorough (12)';
    const btn = page.locator(`button:has-text("${textLabel}")`).first();
    if (await btn.count() > 0) {
      await btn.click();
      await page.waitForTimeout(600);
    }
  }

  // 1. DOC-01 from saved list
  console.log('Looking for saved DOC-01...');
  const doc01Card = page.locator('.dd-doc-card:has-text("DOC-01")').first();
  if (await doc01Card.count() > 0) {
    await doc01Card.click();
    await page.waitForTimeout(1000);

    for (const preset of ['strict', 'balanced', 'thorough']) {
      await selectPreset(preset);
      const shotPath = path.join(SCREENSHOTS_DIR, `doc01_saved_${preset}.png`);
      await page.screenshot({ path: shotPath });
      console.log(`Saved screenshot: ${shotPath}`);
    }
  } else {
    console.warn('DOC-01 not found in documents list! Uploading first...');
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.locator('.dd-drop-box').click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(path.join(REPO_ROOT, 'clauseguard-testkit', 'contracts', 'DOC-01_freelance_agreement.pdf'));
    await page.waitForTimeout(3000);

    for (const preset of ['strict', 'balanced', 'thorough']) {
      await selectPreset(preset);
      const shotPath = path.join(SCREENSHOTS_DIR, `doc01_saved_${preset}.png`);
      await page.screenshot({ path: shotPath });
      console.log(`Saved screenshot: ${shotPath}`);
    }
  }

  // 2. Upload / Select DOC-08
  console.log('Checking for DOC-08 in documents list...');
  let doc08Card = page.locator('.dd-doc-card:has-text("DOC-08")').first();
  if (await doc08Card.count() === 0) {
    console.log('Uploading DOC-08 via drop box file input...');
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.locator('.dd-drop-box').click();
    const fileChooser = await fileChooserPromise;
    await fileChooser.setFiles(path.join(REPO_ROOT, 'clauseguard-testkit', 'contracts', 'DOC-08_partnership_compound.txt'));
    await page.waitForTimeout(3000);
    doc08Card = page.locator('.dd-doc-card:has-text("DOC-08")').first();
  } else {
    await doc08Card.click();
    await page.waitForTimeout(1000);
  }

  if (await doc08Card.count() > 0) {
    for (const preset of ['strict', 'balanced', 'thorough']) {
      await selectPreset(preset);
      const shotPath = path.join(SCREENSHOTS_DIR, `doc08_${preset}.png`);
      await page.screenshot({ path: shotPath });
      console.log(`Saved screenshot: ${shotPath}`);
    }
  } else {
    console.warn('DOC-08 not found or upload failed!');
  }

  await browser.close();
  console.log('All screenshots completed successfully!');
}

main().catch((err) => {
  console.error('Screenshot script error:', err);
  process.exit(1);
});
