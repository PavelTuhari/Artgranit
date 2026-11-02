// HTML → PDF: презентация (слайды 1280×720) и акт тестирования (A4). Chromium через Playwright.
'use strict';
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const out = path.resolve(process.argv[2] || 'docs/html');
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto('file://' + path.join(out, 'presentation.html'));
  await p.pdf({ path: path.join(out, 'presentation.pdf'), width: '1280px', height: '720px', printBackground: true });
  await p.goto('file://' + path.join(out, 'test_act.html'));
  await p.evaluate(() => document.querySelectorAll('details').forEach((d) => { d.open = true; }));
  await p.pdf({ path: path.join(out, 'test_act.pdf'), format: 'A4', printBackground: true,
                margin: { top: '12mm', bottom: '12mm', left: '10mm', right: '10mm' } });
  await b.close();
  console.log('PDF: presentation.pdf, test_act.pdf');
})();
