// RO: Sidecar de rapoarte LITE — doar motorul pdfme (pdf-lib, fara
//     Chromium/jsReport). Pentru servere mici (<1GB RAM care ruleaza si
//     altceva, ex. WordPress pe officeplus.md). Acelasi contract HTTP ca
//     serviciul complet: POST /pdfme/generate {template, inputs} -> PDF.
//     POST /api/report (motorul jsReport) raspunde 503 cu mesaj clar —
//     pe astfel de servere engines.json trebuie setat pe "pdfme".
// EN: LITE reporting sidecar — the pdfme engine only (pdf-lib based, no
//     Chromium/jsReport). For small boxes. Same HTTP contract as the full
//     service: POST /pdfme/generate {template, inputs} -> PDF. The
//     jsReport endpoint answers 503 with a clear message — set
//     engines.json to "pdfme" on such boxes.
const fs = require('fs');
const path = require('path');
const express = require('express');
const { generate } = require('@pdfme/generator');
const { text, table, line, rectangle, image, svg } = require('@pdfme/schemas');

const PORT = 5488;
const FONT_PATH = path.join(__dirname, '..', 'fonts', 'DejaVuSans.ttf');
const plugins = { text, table, line, rectangle, image, svg };
const font = { DejaVuSans: { data: fs.readFileSync(FONT_PATH), fallback: true } };

const app = express();
app.use(express.json({ limit: '5mb' }));

app.get('/', (_req, res) => res.send('pdfme-lite OK'));

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

app.post('/api/report', (_req, res) => {
  res.status(503).json({ error:
    'jsReport engine is not available on this lite server — ' +
    'set reports/templates/engines.json to "pdfme"' });
});

app.listen(PORT, '127.0.0.1', () => {
  console.log(`pdfme-lite started on http://127.0.0.1:${PORT}`);
});
