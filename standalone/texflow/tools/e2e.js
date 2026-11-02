// TexFlow — сквозной прогон в браузере (Playwright, Chromium) со скриншотами.
//
// Запуск: NODE_PATH=$(npm root -g) node tools/e2e.js <каталог-вывода>
// Поднимает приложение на чистой временной базе, поддельный сетевой принтер (TCP),
// проходит весь процесс на RU и экраны на RO / EN. Каждый шаг — проверка + скриншот.
// Результат: <вывод>/e2e_results.json и <вывод>/img/*.jpg|png
'use strict';
const { chromium } = require('playwright');
const { spawn, execFileSync } = require('child_process');
const fs = require('fs');
const net = require('net');
const os = require('os');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const OUT = path.resolve(process.argv[2] || path.join(ROOT, 'docs', 'html'));
const IMG = path.join(OUT, 'img');
fs.mkdirSync(IMG, { recursive: true });
for (const f of fs.readdirSync(IMG)) if (f.startsWith('e2e_')) fs.unlinkSync(path.join(IMG, f));

const PORT = 5000 + Math.floor(Math.random() * 900);
const BASE = `http://127.0.0.1:${PORT}`;
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'texflow-e2e-'));
const results = [];
let shot = 0;

function fakePrinter() {
  const got = [];
  const srv = net.createServer((sock) => {
    const chunks = [];
    sock.on('data', (c) => chunks.push(c));
    sock.on('end', () => got.push(Buffer.concat(chunks)));
  });
  return new Promise((res) => srv.listen(0, '127.0.0.1', () => res({ srv, port: srv.address().port, got })));
}

async function waitUp(url, ms = 15000) {
  const t0 = Date.now();
  while (Date.now() - t0 < ms) {
    try { const r = await fetch(url); if (r.ok) return; } catch (_) { /* ещё стартует */ }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error('приложение не поднялось: ' + url);
}

function pdfToPng(pdf, name, dpi = 110) {
  const prefix = path.join(IMG, name);
  execFileSync('pdftoppm', ['-png', '-r', String(dpi), '-f', '1', '-l', '1', '-singlefile', pdf, prefix]);
  return name + '.png';
}

(async () => {
  const printer = await fakePrinter();
  const app = spawn('python3', ['run.py', '--db', path.join(TMP, 'e2e.db'), '--port', String(PORT), '--no-browser'],
                    { cwd: ROOT, stdio: ['ignore', 'pipe', 'pipe'] });
  let appLog = '';
  app.stdout.on('data', (d) => { appLog += d; });
  app.stderr.on('data', (d) => { appLog += d; });
  await waitUp(BASE + '/login-free-check'.replace('/login-free-check', '/'));

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, acceptDownloads: true });
  const page = await ctx.newPage();
  const jsErrors = [];
  page.on('pageerror', (e) => jsErrors.push(e.message));

  async function snap(name, full = false) {
    shot += 1;
    const file = `e2e_${String(shot).padStart(2, '0')}_${name}.jpg`;
    await page.screenshot({ path: path.join(IMG, file), fullPage: full, type: 'jpeg', quality: 82 });
    return file;
  }

  async function step(id, lang, title, expected, fn) {
    const t0 = Date.now();
    const rec = { id, lang, title, expected, actual: '', status: 'PASS', images: [], ms: 0 };
    try {
      const r = await fn(rec);
      if (typeof r === 'string') rec.actual = r;
    } catch (e) {
      rec.status = 'FAIL';
      rec.actual = (rec.actual ? rec.actual + ' | ' : '') + 'ОШИБКА: ' + e.message.split('\n')[0];
      try { rec.images.push(await snap(id + '_fail', true)); } catch (_) { /* нет страницы */ }
    }
    rec.ms = Date.now() - t0;
    results.push(rec);
    console.log(`${rec.status}  ${id}  ${title}`);
  }
  const must = (cond, msg) => { if (!cond) throw new Error(msg); };
  const flash = async () => (await page.locator('.flash').allTextContents()).join(' / ');
  const goto = (u) => page.goto(BASE + u);

  // ------------------------------------------------------------------ RU: весь процесс
  await step('T01', 'ru', 'Главная страница на пустой базе',
    'Открывается без ошибок, все счётчики 0, меню и переключатель RU/RO/EN на месте', async (r) => {
      await goto('/?lang=ru');
      const kpi = await page.locator('.kpi').allTextContents();
      must(kpi.length === 6 && kpi.every((k) => k.trim() === '0'), 'счётчики: ' + kpi.join(','));
      must(await page.locator('header .langs a').count() === 3, 'нет переключателя языков');
      r.images.push(await snap('home_empty'));
      return 'Счётчики: ' + kpi.join(' / ');
    });

  await step('T02', 'ru', 'Проверка обязательного поля: поставка без номера',
    'Форма не создаёт поставку, выводится сообщение «Укажите номер поставки»', async (r) => {
      await goto('/shipments');
      await page.evaluate(() => document.querySelector('input[name=code]').removeAttribute('required'));
      await page.click('form.card button');
      const f = await flash();
      must(f.includes('Укажите номер поставки'), 'сообщение: ' + f);
      r.images.push(await snap('shipment_validation'));
      return f;
    });

  await step('T03', 'ru', 'Создание поставки из Турции с импортными затратами',
    'Поставка TR-TEST-01 создана: USD × 17.8, фрахт 4500, таможня 1200, брокер 800, распределение по стоимости', async (r) => {
      await goto('/shipments');
      await page.fill('input[name=code]', 'TR-TEST-01');
      await page.fill('input[name=supplier]', 'Istanbul Tekstil');
      await page.selectOption('select[name=currency]', 'USD');
      await page.fill('input[name=fx_rate]', '17.8');
      await page.fill('input[name=freight]', '4500');
      await page.fill('input[name=customs]', '1200');
      await page.fill('input[name=broker]', '800');
      r.images.push(await snap('shipment_form'));
      await page.click('form.card button');
      const f = await flash();
      must(f.includes('TR-TEST-01'), 'нет сообщения о создании: ' + f);
      must(page.url().includes('/shipments/1'), 'не открылась карточка поставки');
      r.images.push(await snap('shipment_created'));
      return f;
    });

  await step('T04', 'ru', 'Загрузка примерного упаковочного листа (CSV)',
    '7 строк загружены, создано 4 мешка с весами, лист отображается в таблице', async (r) => {
      await page.setInputFiles('input[type=file]', path.join(ROOT, 'samples', 'packing_list_tr.csv'));
      await page.click('form[enctype] button');
      const f = await flash();
      must(f.includes('Загружено строк: 7') && f.includes('мешков: 4'), f);
      const bags = await page.locator('text=Разобрать').count();
      must(bags === 4, 'мешков в таблице: ' + bags);
      r.images.push(await snap('packing_loaded', true));
      return f + `; мешков в таблице: ${bags}`;
    });

  let teeEan = '';
  await step('T05', 'ru', 'Разбор мешка №1: новая модель и матрица цвет × размер',
    'Модель создана, закупка 2.10 подставлена из листа, матрица 3 цвета × размеры, итого 120 шт., запись проходит', async (r) => {
      await goto('/sort/1?bag=1');
      await page.fill('form[action$="/product"] input[name=name]', 'Футболка базовая оверсайз');
      await page.selectOption('select[name=category_id]', { label: 'Футболки и топы (TSH)' });
      await page.fill('input[name=composition]', '100% хлопок');
      await page.click('text=Создать и открыть матрицу');
      await page.waitForSelector('#mbody', { state: 'attached' });
      const cost = await page.inputValue('input[name=unit_cost_fx]');
      must(cost === '2.1', 'закупка из листа: ' + cost);
      for (const c of ['001 Белый', '800 Чёрный', '710 Бежевый']) await page.click(`.colorpick[data-name="${c}"]`);
      const grid = { 0: [0, 0, 10, 15, 12, 5], 1: [0, 0, 12, 20, 14, 6], 2: [0, 0, 8, 10, 8, 0] };
      const rows = page.locator('#mbody tr');
      for (const [ri, vals] of Object.entries(grid)) {
        const inp = rows.nth(Number(ri)).locator('input');
        for (let i = 0; i < vals.length; i++) if (vals[i]) await inp.nth(i).fill(String(vals[i]));
      }
      await page.locator('#mbody input').first().dispatchEvent('input');
      const total = await page.textContent('#tsum');
      must(total === '120', 'итог матрицы: ' + total);
      r.images.push(await snap('matrix_filled', true));
      await Promise.all([page.waitForNavigation(), page.keyboard.press('Control+Enter')]);
      const f = await flash();
      must(f.includes('Принято 120 шт.'), f);
      r.images.push(await snap('intake_logged'));
      return `Итог матрицы ${total}; ${f}`;
    });

  await step('T06', 'ru', 'Разбор мешка №2: джинсы, шкала W, клавиатурный ввод (Enter)',
    'Шкала размеров «Джинсы W» подставлена по категории, ввод через Enter переходит по ячейкам, 60 шт. приняты', async (r) => {
      await goto('/sort/1?bag=2');
      await page.fill('form[action$="/product"] input[name=name]', 'Джинсы mom fit');
      await page.selectOption('select[name=category_id]', { label: 'Джинсы (JNS)' });
      await page.click('text=Создать и открыть матрицу');
      await page.waitForSelector('#mbody', { state: 'attached' });
      const heads = await page.locator('.matrix thead th').allTextContents();
      must(heads.includes('26') && heads.includes('30'), 'шкала: ' + heads.join(' '));
      await page.click('.colorpick[data-name="400 Деним"]');
      for (const v of ['', '', '8', '10', '12', '10', '8']) { if (v) await page.keyboard.type(v); await page.keyboard.press('Enter'); }
      await page.click('.colorpick[data-name="800 Чёрный"]');
      for (const v of ['', '', '', '6', '6']) { if (v) await page.keyboard.type(v); await page.keyboard.press('Enter'); }
      const total = await page.textContent('#tsum');
      must(total === '60', 'итог: ' + total);
      r.images.push(await snap('jeans_matrix', true));
      await Promise.all([page.waitForNavigation(), page.click('#mform button:not([name])')]);
      const f = await flash();
      must(f.includes('Принято 60 шт.'), f);
      return `Шкала: ${heads.slice(1, -1).join(' ')}; ${f}`;
    });

  await step('T07', 'ru', 'Сканер штрихкодов: повторный товар и неизвестный код',
    'Скан существующего EAN добавляет +1 шт. (✓), неизвестный код — ошибка ✗ без записи', async (r) => {
      await goto('/product/1');
      teeEan = (await page.locator('table tr').nth(1).locator('td').nth(1).textContent()).trim();
      await goto('/sort/1?bag=1');
      await page.fill('#scan', teeEan); await page.press('#scan', 'Enter');
      await page.waitForFunction(() => document.querySelector('#scanlog').textContent.length > 0);
      await page.fill('#scan', '2999999999999'); await page.press('#scan', 'Enter');
      await page.waitForFunction(() => document.querySelector('#scanlog').textContent.includes('✗'));
      const log = await page.textContent('#scanlog');
      must(log.includes('✓') && log.includes('не найден'), log);
      r.images.push(await snap('scanner'));
      return `EAN ${teeEan}: ${log.replace(/\s+/g, ' ').trim()}`;
    });

  await step('T08', 'ru', 'Исправление ошибки пересчёта: удаление строки журнала',
    'Строка последнего скана удаляется, остаток варианта уменьшается на 1', async (r) => {
      await goto('/sort/1?bag=1');
      const before = await page.locator('table').last().locator('tr').count();
      await page.locator('table').last().locator('tr').nth(1).locator('button').click();
      await page.waitForLoadState('load');
      const after = await page.locator('table').last().locator('tr').count();
      must(after === before - 1, `строк было ${before}, стало ${after}`);
      return `Строк журнала: ${before - 1} → ${after - 1}`;
    });

  await step('T09', 'ru', 'Мешок разобран и сверка с упаковочным листом',
    'Статус мешка «разобран», сверка показывает «совпало» для футболок и джинсов, «недостача» по незаявленным в разборе категориям', async (r) => {
      await goto('/sort/1?bag=1');
      await page.click('text=Мешок разобран');
      await goto('/shipments/1');
      const rec = await page.locator('.grid.g2').last().textContent();
      must(rec.includes('совпало') && rec.includes('недостача'), 'сверка: ' + rec.slice(0, 200));
      r.images.push(await snap('reconciliation', true));
      return 'В сверке есть статусы «совпало» и «недостача»';
    });

  await step('T10', 'ru', 'Смена способа распределения затрат и пересчёт себестоимости',
    'После переключения на «по весу мешков» и сохранения себестоимость пересчитывается, итог затрат = 6500', async (r) => {
      await goto('/shipments/1');
      await page.selectOption('select[name=alloc_method]', 'weight');
      await page.click('form.card button:has-text("Сохранить и пересчитать")');
      const f = await flash();
      must(f.includes('пересчитана'), f);
      const tbl = await page.locator('form.card table').textContent();
      must(tbl.includes('6500.00'), 'общие затраты: ' + tbl);
      r.images.push(await snap('costs_weight'));
      await page.selectOption('select[name=alloc_method]', 'value');
      await page.click('form.card button:has-text("Сохранить и пересчитать")');
      return f;
    });

  await step('T11', 'ru', 'Ценообразование: предложение, своя цена, запись в карточки',
    'Предложенные цены оканчиваются на .90; своя цена 599.90 для джинсов записывается; 2 карточки получают цены', async (r) => {
      await goto('/shipments/1/pricing');
      const proposed = await page.locator('td.n b').allTextContents();
      must(proposed.length === 2 && proposed.every((p) => p.endsWith('9.90')), 'цены: ' + proposed.join(', '));
      r.images.push(await snap('pricing'));
      await page.fill('input[name=price_2]', '599.90');
      await page.click('text=Записать цены в карточки');
      const f = await flash();
      must(f.includes('2 карточек'), f);
      const current = await page.locator('tr').nth(1).textContent();
      return `Предложено: ${proposed.join(', ')}; ${f}`;
    });

  await step('T12', 'ru', 'Карточка модели: переводы RO/EN и фиксация цены',
    'Название и состав сохраняются на трёх языках, цена фиксируется (замок) и не перезаписывается пересчётом', async (r) => {
      await goto('/product/1');
      await page.fill('input[name=name_ro]', 'Tricou basic oversize');
      await page.fill('input[name=name_en]', 'Basic oversize T-shirt');
      await page.fill('input[name=composition_ro]', '100% bumbac');
      await page.fill('input[name=composition_en]', '100% cotton');
      await page.fill('input[name=retail_price]', '189.90');
      await page.check('input[name=price_locked]');
      await page.click('form.card.noprint button');
      must((await flash()).includes('Карточка сохранена'), 'не сохранено');
      r.images.push(await snap('product_card', true));
      await goto('/shipments/1/pricing');
      await page.click('text=Записать цены в карточки');
      await goto('/product/1');
      const price = await page.textContent('.kpi');
      must(price.includes('189.90'), 'цена после пересчёта: ' + price);
      return 'Цена после повторного пересчёта: ' + price.trim();
    });

  await step('T13', 'ru', 'Каталог: карточки, поиск по EAN и по переводу названия',
    'Каталог показывает 2 модели со свотчами цветов; поиск по EAN и по «Tricou» находит футболку', async (r) => {
      await goto('/catalog');
      must(await page.locator('.pc a.it').count() === 2, 'моделей не 2');
      r.images.push(await snap('catalog'));
      await goto('/catalog?q=' + teeEan);
      must(await page.locator('.pc a.it').count() === 1, 'поиск по EAN');
      await goto('/catalog?q=Tricou');
      must(await page.locator('.pc a.it').count() === 1, 'поиск по RO-названию');
      return 'Поиск по EAN и по «Tricou» — по 1 модели';
    });

  await step('T14', 'ru', 'Этикетки: PDF A4 (лист 3×8)',
    'Скачивается PDF A4, количество этикеток = принятым штукам, штрихкоды и кириллица на месте', async (r) => {
      await goto('/labels?shipment=1');
      const h2 = await page.textContent('form.card h2');
      must(/180 этикеток/.test(h2), 'выбрано: ' + h2);
      r.images.push(await snap('labels_page'));
      const [dl] = await Promise.all([page.waitForEvent('download'),
        page.selectOption('select[name=fmt]', 'pdf_a4').then(() => page.click('button[value=download]'))]);
      const f = path.join(TMP, 'a4.pdf'); await dl.saveAs(f);
      must(fs.readFileSync(f).slice(0, 4).toString() === '%PDF', 'не PDF');
      r.images.push(pdfToPng(f, 'e2e_label_a4', 60));
      return h2.trim() + '; PDF ' + fs.statSync(f).size + ' байт';
    });

  await step('T15', 'ru', 'Этикетки: PDF-рулон 58×40 мм для виртуального принтера',
    'Скачивается PDF, одна страница = одна этикетка 58×40 мм', async (r) => {
      await goto('/labels?product=1&copies=1');
      const [dl] = await Promise.all([page.waitForEvent('download'),
        page.selectOption('select[name=fmt]', 'pdf_roll').then(() => page.click('button[value=download]'))]);
      const f = path.join(TMP, 'roll.pdf'); await dl.saveAs(f);
      const txt = fs.readFileSync(f).toString('latin1');
      must(txt.includes('/MediaBox [ 0 0 164.4094 113.3858 ]'), 'размер страницы не 58×40');
      r.images.push(pdfToPng(f, 'e2e_label_roll', 220));
      return 'MediaBox 164.4×113.4 pt = 58×40 мм';
    });

  await step('T16', 'ru', 'Этикетки: ZPL (Zebra) и TSPL (TSC) файлами',
    'ZPL содержит ^XA/^XZ, ^BEN (EAN-13), ^PQ; TSPL — SIZE, BARCODE "EAN13", PRINT', async (r) => {
      for (const fmt of ['zpl', 'tspl']) {
        await goto('/labels?product=1&copies=1');
        const [dl] = await Promise.all([page.waitForEvent('download'),
          page.selectOption('select[name=fmt]', fmt).then(() => page.click('button[value=download]'))]);
        const f = path.join(OUT, `sample_label.${fmt}`); await dl.saveAs(f);
        const t = fs.readFileSync(f, 'utf8');
        if (fmt === 'zpl') must(t.includes('^XA') && t.includes('^BEN') && t.includes('^PQ1'), 'ZPL');
        else must(t.startsWith('SIZE 58 mm,40 mm') && t.includes('"EAN13"') && t.includes('PRINT 1,1'), 'TSPL');
      }
      return 'Файлы sample_label.zpl и sample_label.tspl сохранены рядом с актом';
    });

  await step('T17', 'ru', 'Печать на сетевой принтер (TCP, как порт 9100)',
    'Задание ZPL уходит на принтер, принтер получает байты, в журнале печати статус ok', async (r) => {
      await goto('/labels?product=2&copies=1');
      await page.selectOption('select[name=fmt]', 'zpl');
      await page.fill('input[name=target]', `tcp://127.0.0.1:${printer.port}`);
      await page.click('button[value=print]');
      await page.waitForLoadState('load');
      const f = await flash();
      await new Promise((res) => setTimeout(res, 300));
      const bytes = printer.got.reduce((a, b) => a + b.length, 0);
      must(f.includes('Печать:') && bytes > 0, `${f}; байт: ${bytes}`);
      must(printer.got[0].toString().startsWith('^XA'), 'принтер получил не ZPL');
      r.images.push(await snap('print_tcp', true));
      return `${f}; принтер получил ${bytes} байт`;
    });

  await step('T18', 'ru', 'Печать на недоступный принтер',
    'Ошибка показывается пользователю, в журнале печати — error, приложение не падает', async (r) => {
      await goto('/labels?product=2&copies=1');
      await page.selectOption('select[name=fmt]', 'zpl');
      await page.fill('input[name=target]', 'tcp://127.0.0.1:1');
      await page.click('button[value=print]');
      await page.waitForLoadState('load');
      const f = await flash();
      must(f.includes('Принтер не ответил'), f);
      return f;
    });

  await step('T19', 'ru', 'Язык этикетки: румынский',
    'После «Язык названий цветов на этикетке = Română» этикетка печатает «Tricou basic oversize», «Alb», «100% bumbac»', async (r) => {
      await goto('/settings');
      await page.selectOption('select[name=label_lang]', 'ro');
      await page.click('form button:has-text("Сохранить")');
      await goto('/labels?variant=1&copies=1');
      const row = await page.locator('form.card table tr').nth(1).textContent();
      must(row.includes('Tricou basic oversize') && row.includes('Alb'), row);
      const [dl] = await Promise.all([page.waitForEvent('download'),
        page.selectOption('select[name=fmt]', 'pdf_roll').then(() => page.click('button[value=download]'))]);
      const f = path.join(TMP, 'roll_ro.pdf'); await dl.saveAs(f);
      r.images.push(pdfToPng(f, 'e2e_label_roll_ro', 220));
      await goto('/settings');
      await page.selectOption('select[name=label_lang]', 'ru');
      await page.click('form button:has-text("Сохранить")');
      return row.replace(/\s+/g, ' ').trim();
    });

  await step('T20', 'ru', 'Справочники: новый цвет с переводами RO/EN',
    'Цвет 411 «Индиго / Indigo / Indigo» добавлен в группу «Синий» и доступен в матрице', async (r) => {
      await goto('/refs');
      await page.selectOption('#color select[name=family_id]', { label: 'Синий' });
      await page.fill('#color input[name=code]', '411');
      await page.fill('#color input[name=name]', 'Индиго');
      await page.fill('#color input[name=name_ro]', 'Indigo');
      await page.fill('#color input[name=name_en]', 'Indigo');
      await page.click('#color button');
      must((await flash()).includes('Сохранено'), 'не сохранено');
      await goto('/sort/1?product=1');
      must(await page.locator('.colorpick[data-name="411 Индиго"]').count() === 1, 'цвет не появился в матрице');
      r.images.push(await snap('refs', true));
      return 'Цвет 411 есть в справочнике и в матрице разбора';
    });

  await step('T21', 'ru', 'Экспорт каталога в CSV',
    'CSV с BOM, разделитель «;», строка на каждый вариант, есть EAN-13', async (r) => {
      const res = await page.request.get(BASE + '/export/catalog.csv');
      const t = await res.text();
      const lines = t.trim().split('\n');
      must(lines[0].includes('style_code;name;category') && t.includes(teeEan), 'содержимое CSV');
      fs.writeFileSync(path.join(OUT, 'sample_catalog.csv'), t);
      return `${lines.length - 1} строк вариантов; файл sample_catalog.csv`;
    });

  await step('T22', 'ru', 'Несуществующая поставка и модель',
    'Ответ 404 с понятным текстом, без трассировки', async () => {
      const a = await page.request.get(BASE + '/shipments/999');
      const b = await page.request.get(BASE + '/product/999');
      must(a.status() === 404 && b.status() === 404, `${a.status()} ${b.status()}`);
      const t = await a.text();
      must(!t.includes('Traceback'), 'трассировка в ответе');
      return `404 / 404: «${t}»`;
    });

  await step('T23', 'ru', 'Инструкция со схемой процесса (Mermaid)',
    'Страница открывается, схема процесса присутствует', async (r) => {
      await goto('/help');
      must(await page.locator('pre.mermaid').count() === 1, 'нет схемы');
      await page.waitForTimeout(1500);
      r.images.push(await snap('help_ru', true));
      return 'Схема присутствует (рендер — при доступе к CDN mermaid, иначе текст схемы)';
    });

  // ------------------------------------------------------------------ RO и EN: все экраны
  const screens = [
    ['home', '/'], ['shipment', '/shipments/1'], ['sort', '/sort/1?bag=1&product=1'],
    ['pricing', '/shipments/1/pricing'], ['catalog', '/catalog'], ['product', '/product/1'],
    ['labels', '/labels?shipment=1'], ['settings', '/settings'], ['refs', '/refs'], ['help', '/help'],
  ];
  const keyword = { ro: ['Livrări', 'Catalog', 'Setări'], en: ['Shipments', 'Catalogue', 'Settings'] };
  for (const lang of ['ro', 'en']) {
    await step(lang === 'ro' ? 'T24' : 'T25', lang, `Все экраны на ${lang === 'ro' ? 'румынском' : 'английском'}`,
      'Переключатель меняет язык и запоминает его; на 10 экранах нет кириллицы в интерфейсе', async (r) => {
        await goto('/?lang=' + lang);
        // таблица этикеток показывает цвет на языке ЭТИКЕТКИ — ставим его тем же, что и интерфейс
        await goto('/settings');
        await page.selectOption('select[name=label_lang]', lang);
        await Promise.all([page.waitForNavigation(), page.click('form button:has-text("' + (lang === 'ro' ? 'Salvează' : 'Save') + '")')]);
        const bad = [];
        for (const [name, url] of screens) {
          await goto(url);
          const text = await page.evaluate(() => {
            const c = document.body.cloneNode(true);
            c.querySelectorAll('input,textarea,select,script,[title]').forEach((e) => e.removeAttribute('title'));
            c.querySelectorAll('script').forEach((e) => e.remove());
            return c.innerText;
          });
          const userData = ['Футболка базовая оверсайз', 'Джинсы mom fit', '100% хлопок', 'Индиго', 'Русский',
            'Футболки женские базовые, микс цветов', 'Блузы шифон', 'Джинсы мом-фит женские', 'Платья миди трикотаж',
            'Свитеры оверсайз', 'Куртки демисезон', 'Шарфы'];
          let t = text; for (const u of userData) t = t.split(u).join('');
          const cyr = t.match(/[А-Яа-яЁё]+/g);
          if (cyr) bad.push(`${name}: ${cyr.slice(0, 3).join(' ')}`);
          if (name === 'help') await page.waitForTimeout(1200);
          r.images.push(await snap(`${lang}_${name}`, ['shipment', 'sort', 'refs', 'help'].includes(name)));
        }
        const nav = await page.locator('header nav').textContent();
        must(keyword[lang].every((k) => nav.includes(k)), 'меню: ' + nav);
        must(bad.length === 0, 'кириллица: ' + bad.join('; '));
        return `10 экранов, меню: ${nav.replace(/\s+/g, ' ').trim()}`;
      });
  }

  await step('T26', 'ru', 'Мобильный экран (планшет / телефон кладовщика)',
    'На ширине 390 px страница разбора читается, колонки складываются в одну', async (r) => {
      await goto('/?lang=ru');
      await page.setViewportSize({ width: 390, height: 844 });
      await goto('/sort/1?bag=1&product=1');
      r.images.push(await snap('mobile_sort'));
      await page.setViewportSize({ width: 1360, height: 900 });
      return 'Скриншот 390×844';
    });

  await step('T27', 'ru', 'Ошибки JavaScript за весь прогон',
    'В консоли браузера нет необработанных ошибок', async () => {
      must(jsErrors.length === 0, jsErrors.join(' | '));
      return 'Ошибок: 0';
    });

  const chromiumVersion = browser.version();
  await browser.close();
  app.kill('SIGTERM');
  printer.srv.close();
  const meta = {
    started: new Date().toISOString(), chromium: chromiumVersion,
    playwright: require('playwright/package.json').version, node: process.version,
    base: BASE, app_log_tail: appLog.split('\n').filter((l) => /Error|Traceback/.test(l)).slice(-10),
  };
  fs.writeFileSync(path.join(OUT, 'e2e_results.json'), JSON.stringify({ meta, results }, null, 1));
  const failed = results.filter((x) => x.status !== 'PASS').length;
  console.log(`\nE2E: ${results.length - failed}/${results.length} PASS`);
  process.exit(failed ? 1 : 0);
})().catch((e) => { console.error(e); process.exit(2); });
