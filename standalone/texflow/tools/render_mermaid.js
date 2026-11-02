// Рендер Mermaid → SVG без интернета (для HTML-документации).
// stdin: JSON-массив исходников схем; stdout: JSON-массив SVG (или null при ошибке).
// Нужен mermaid.min.js: путь в MERMAID_JS (npm i mermaid@10.9.1).
'use strict';
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const srcs = JSON.parse(fs.readFileSync(0, 'utf8'));
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.setContent('<html><body></body></html>');
  await p.addScriptTag({ path: process.env.MERMAID_JS });
  const out = [];
  for (const s of srcs) {
    out.push(await p.evaluate(async (src) => {
      try {
        mermaid.initialize({ startOnLoad: false, theme: 'neutral', fontFamily: 'Helvetica, Arial, sans-serif' });
        const r = await mermaid.render('m' + Math.random().toString(36).slice(2), src);
        return r.svg;
      } catch (e) { return null; }
    }, s));
  }
  await b.close();
  process.stdout.write(JSON.stringify(out));
})();
