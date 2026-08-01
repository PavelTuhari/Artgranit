/* Biro26 — выгрузка любого грида в Excel (уровень ядра).
 *
 * RO: helper comun pentru TOATE grid-urile din back-office. Genereaza un fisier
 *     SpreadsheetML (se deschide nativ in Excel) direct in browser — fara
 *     biblioteci externe, fara CDN si fara cereri la server, deci merge pe
 *     orice pagina care are un <table>.
 * EN: shared exporter for EVERY back-office grid — builds a SpreadsheetML file
 *     client-side; no external libraries, no CDN, no server round-trip.
 *
 * Utilizare / использование:
 *   1) automat: <table data-export="nume-fisier"> — butonul se adauga singur;
 *   2) manual:  GridExport.toExcel(tableEl, 'nume-fisier');
 *   3) buton:   GridExport.addButton(containerEl, tableEl, 'nume-fisier').
 *
 * Se exporta EXACT ce se vede in grid (inclusiv filtrele aplicate), fara
 * randurile ascunse si fara coloanele marcate cu data-noexport.
 */
(function (w, d) {
  'use strict';

  function xmlEsc(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;')
      // RO: caracterele de control strica fisierul XML — le scoatem
      .replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, '');
  }

  // RO: text curat dintr-o celula: fara butoane/selectoare, cu valoarea lor
  function cellText(td) {
    var clone = td.cloneNode(true);
    clone.querySelectorAll('button, .det, script, style').forEach(function (el) {
      el.remove();
    });
    // selectoarele si input-urile intra cu valoarea aleasa, nu cu tot HTML-ul
    clone.querySelectorAll('select').forEach(function (sel) {
      var o = sel.options[sel.selectedIndex];
      sel.replaceWith(d.createTextNode(o ? o.textContent : ''));
    });
    clone.querySelectorAll('input').forEach(function (inp) {
      inp.replaceWith(d.createTextNode(
        inp.type === 'checkbox' ? (inp.checked ? 'da' : 'nu') : (inp.value || '')));
    });
    return clone.textContent.replace(/\s+/g, ' ').trim();
  }

  var NUM_RE = /^-?\d+([.,]\d+)?$/;

  function cellXml(text) {
    if (NUM_RE.test(text) && text.length < 16) {
      return '<Cell><Data ss:Type="Number">' +
             xmlEsc(text.replace(',', '.')) + '</Data></Cell>';
    }
    return '<Cell><Data ss:Type="String">' + xmlEsc(text) + '</Data></Cell>';
  }

  function visible(el) {
    return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  }

  function rowsOf(table) {
    var out = [];
    ['thead', 'tbody', 'tfoot'].forEach(function (part) {
      var sec = table.querySelector(part);
      if (!sec) return;
      Array.prototype.forEach.call(sec.rows, function (tr) {
        if (!visible(tr)) return;                       // randurile filtrate nu se exporta
        var cells = [];
        Array.prototype.forEach.call(tr.cells, function (td) {
          if (td.hasAttribute('data-noexport')) return;
          cells.push(cellText(td));
        });
        if (cells.length) out.push({head: part === 'thead', cells: cells});
      });
    });
    return out;
  }

  function toExcel(table, filename) {
    if (typeof table === 'string') table = d.querySelector(table);
    if (!table) return false;
    var rows = rowsOf(table);
    if (!rows.length) return false;

    var xml =
      '<?xml version="1.0" encoding="UTF-8"?>' +
      '<?mso-application progid="Excel.Sheet"?>' +
      '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"' +
      ' xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">' +
      '<Styles><Style ss:ID="h"><Font ss:Bold="1"/>' +
      '<Interior ss:Color="#F1F5F9" ss:Pattern="Solid"/></Style></Styles>' +
      '<Worksheet ss:Name="Date"><Table>' +
      rows.map(function (r) {
        return '<Row' + (r.head ? ' ss:StyleID="h"' : '') + '>' +
               r.cells.map(cellXml).join('') + '</Row>';
      }).join('') +
      '</Table></Worksheet></Workbook>';

    var name = (filename || 'export') + '_' +
      new Date().toISOString().slice(0, 10).replace(/-/g, '') + '.xls';
    var blob = new Blob([xml], {type: 'application/vnd.ms-excel'});
    var url = URL.createObjectURL(blob);
    var a = d.createElement('a');
    a.href = url; a.download = name;
    d.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 2000);
    return true;
  }

  function addButton(container, table, filename, label) {
    if (!container || !table) return null;
    var b = d.createElement('button');
    b.type = 'button';
    b.className = 'grid-export-btn';
    b.textContent = label || '⬇ Excel';
    b.title = 'Descarcă grid-ul în Excel · Скачать таблицу в Excel';
    b.onclick = function () {
      if (!toExcel(table, filename)) {
        b.textContent = 'Nimic de exportat';
        setTimeout(function () { b.textContent = label || '⬇ Excel'; }, 2000);
      }
    };
    container.appendChild(b);
    return b;
  }

  /* ── SORTARE + CAUTARE (nivel de CORE, ca la orice grid) ──────────────
   * RO: fiecare <table data-export> capata automat:
   *   - sortare la CLICK pe orice antet (asc / desc / fara), cu recunoasterea
   *     numerelor si a datelor dd.mm.yyyy — nu pe text brut;
   *   - o casuta de cautare care ascunde randurile ce nu se potrivesc
   *     (exportul in Excel ia doar randurile VIZIBILE, deci filtrul se aplica
   *     si la descarcare).
   * Grid-urile isi redeseneaza <tbody> prin innerHTML; un MutationObserver
   * reaplica sortarea si filtrul dupa fiecare redesenare.
   * EN: click-to-sort on any header + a search box, re-applied after the page
   *     re-renders the tbody. Excel export follows the visible rows.
   */
  var DMY = /^(\d{2})[.\/-](\d{2})[.\/-](\d{4})(.*)$/;

  function sortKey(txt) {
    var s = (txt || '').trim();
    var m = DMY.exec(s);
    if (m) return m[3] + m[2] + m[1] + m[4];           // dd.mm.yyyy -> yyyymmdd
    var n = s.replace(/\s/g, '').replace(',', '.');
    if (NUM_RE.test(n)) return parseFloat(n);
    return s.toLowerCase();
  }

  function applySort(t) {
    var st = t.__sort;
    var tb = t.tBodies[0];
    if (!st || st.dir === 0 || !tb) return;
    var rows = Array.prototype.slice.call(tb.rows);
    if (rows.length < 2) return;
    rows.sort(function (a, b) {
      var x = sortKey(a.cells[st.i] ? cellText(a.cells[st.i]) : '');
      var y = sortKey(b.cells[st.i] ? cellText(b.cells[st.i]) : '');
      if (typeof x === 'number' && typeof y === 'number') return (x - y) * st.dir;
      return String(x).localeCompare(String(y), 'ro', {numeric: true}) * st.dir;
    });
    t.__busy = true;
    rows.forEach(function (r) { tb.appendChild(r); });
    t.__busy = false;
  }

  function applyFilter(t) {
    var q = (t.__q || '').toLowerCase().trim();
    var tb = t.tBodies[0];
    if (!tb) return;
    t.__busy = true;
    Array.prototype.forEach.call(tb.rows, function (r) {
      r.style.display = (!q || r.textContent.toLowerCase().indexOf(q) !== -1) ? '' : 'none';
    });
    t.__busy = false;
  }

  function refresh(t) { applySort(t); applyFilter(t); }

  function wireSort(t) {
    var head = t.tHead && t.tHead.rows[0];
    if (!head) return;
    Array.prototype.forEach.call(head.cells, function (th, i) {
      if (th.hasAttribute('data-nosort')) return;
      th.style.cursor = 'pointer';
      th.title = 'Sortează după această coloană · Сортировать по столбцу';
      th.addEventListener('click', function () {
        var st = t.__sort || {i: -1, dir: 0};
        // RO: acelasi antet -> asc, desc, apoi inapoi la ordinea serverului
        t.__sort = (st.i === i)
          ? {i: i, dir: st.dir === 1 ? -1 : (st.dir === -1 ? 0 : 1)}
          : {i: i, dir: 1};
        Array.prototype.forEach.call(head.cells, function (h) {
          h.textContent = h.textContent.replace(/[ ]?[▲▼]$/, '');
        });
        if (t.__sort.dir) th.textContent += t.__sort.dir === 1 ? ' ▲' : ' ▼';
        refresh(t);
      });
    });
  }

  function addFilter(container, t) {
    var inp = d.createElement('input');
    inp.type = 'search';
    inp.className = 'grid-filter-inp';
    inp.placeholder = 'Caută în tabel · Поиск в таблице';
    inp.addEventListener('input', function () { t.__q = inp.value; applyFilter(t); });
    container.appendChild(inp);
    return inp;
  }

  function wireGrid(t, bar) {
    wireSort(t);
    // RO: casuta proprie doar daca pagina nu are deja una a ei
    if (bar && !bar.querySelector('input[type="search"]')) addFilter(bar, t);
    var tb = t.tBodies[0];
    if (tb && w.MutationObserver) {
      new MutationObserver(function () {
        if (t.__busy) return;
        refresh(t);
      }).observe(tb, {childList: true});
    }
  }

  // RO: auto-wiring — orice <table data-export="nume"> primeste butonul singur.
  //     Butonul se pune in [data-export-bar] daca exista, altfel inainte de tabel.
  function autowire() {
    d.querySelectorAll('table[data-export]').forEach(function (t) {
      if (t.__exportWired) return;
      t.__exportWired = true;
      var name = t.getAttribute('data-export') || 'export';
      // RO: bara se leaga DUPA NUME. Fara asta, pe o pagina cu doua grid-uri
      //     (master + detail) ambele si-ar pune butonul in aceeasi bara.
      // EN: bind the bar BY NAME — otherwise master+detail grids on one page
      //     both drop their button into the first bar found.
      var bar = d.querySelector('[data-export-bar="' + name + '"]');
      if (!bar) {
        bar = d.createElement('div');
        bar.style.margin = '0 0 8px';
        bar.style.display = 'flex';
        bar.style.gap = '8px';
        t.parentNode.insertBefore(bar, t);
      }
      addButton(bar, t, name);
      wireGrid(t, bar);
    });
  }

  if (!d.getElementById('grid-export-css')) {
    var st = d.createElement('style');
    st.id = 'grid-export-css';
    st.textContent = '.grid-export-btn{padding:7px 12px;border:1px solid #cbd5e1;' +
      'border-radius:8px;background:#fff;font-size:12.5px;cursor:pointer;color:#1e293b}' +
      '.grid-export-btn:hover{background:#f1f5f9}' +
      '.grid-filter-inp{padding:7px 12px;border:1px solid #cbd5e1;border-radius:8px;' +
      'background:#fff;font-size:12.5px;color:#1e293b;min-width:200px}';
    d.head.appendChild(st);
  }

  w.GridExport = {toExcel: toExcel, addButton: addButton, autowire: autowire};
  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', autowire);
  else autowire();
})(window, document);
