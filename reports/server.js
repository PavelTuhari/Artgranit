// RO: Serviciul de rapoarte al platformei Artgranit (localhost:5488).
//     Doua motoare:
//       1) jsReport  — POST /api/report  (Handlebars + chrome-pdf);
//       2) pdfme     — POST /pdfme/generate (template JSON + inputs,
//          pdf-lib — usor, fara Chromium; sabloanele se editeaza vizual
//          in Designer-ul pdfme din admin-ul de sabloane).
//     Flask alege motorul per formular (reports/templates/engines.json).
// EN: Artgranit reporting service (localhost:5488). Two engines: jsReport
//     (POST /api/report, Handlebars + chrome-pdf) and pdfme
//     (POST /pdfme/generate, JSON template + inputs, pdf-lib based — no
//     Chromium; templates are visually editable in the pdfme Designer).
//     Flask picks the engine per form (reports/templates/engines.json).
// Config: jsreport.config.json (port, chrome args, single worker — the
// production box has <1GB RAM).
const fs = require('fs');
const path = require('path');
const jsreport = require('jsreport')();

const FONT_PATH = path.join(__dirname, 'fonts', 'DejaVuSans.ttf');

jsreport.init().then(() => {
  // ── pdfme engine on the same HTTP server ──
  const { generate } = require('@pdfme/generator');
  const { text, table, line, rectangle, image, svg } = require('@pdfme/schemas');
  const plugins = { text, table, line, rectangle, image, svg };
  // RO: DejaVu Sans — diacritice RO + chirilice / EN: RO diacritics + Cyrillic
  const font = {
    DejaVuSans: { data: fs.readFileSync(FONT_PATH), fallback: true },
  };

  const app = jsreport.express.app;
  app.use(require('express').json({ limit: '5mb' }));

  app.post('/pdfme/generate', async (req, res) => {
    try {
      const { template, inputs } = req.body || {};
      if (!template || !inputs) {
        return res.status(400).json({ error: 'template and inputs are required' });
      }
      const pdf = await generate({ template, inputs, plugins, options: { font } });
      res.set('Content-Type', 'application/pdf');
      res.send(Buffer.from(pdf));
    } catch (e) {
      res.status(500).json({ error: String((e && e.message) || e) });
    }
  });

  console.log('jsreport + pdfme started on http://127.0.0.1:5488');
}).catch((e) => {
  console.error(e);
  process.exit(1);
});
