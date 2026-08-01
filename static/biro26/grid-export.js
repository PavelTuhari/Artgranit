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

  // RO: auto-wiring — orice <table data-export="nume"> primeste butonul singur.
  //     Butonul se pune in [data-export-bar] daca exista, altfel inainte de tabel.
  function autowire() {
    d.querySelectorAll('table[data-export]').forEach(function (t) {
      if (t.__exportWired) return;
      t.__exportWired = true;
      var name = t.getAttribute('data-export') || 'export';
      var bar = d.querySelector('[data-export-bar="' + name + '"]') ||
                d.querySelector('[data-export-bar]');
      if (bar) { addButton(bar, t, name); return; }
      var holder = d.createElement('div');
      holder.style.margin = '0 0 8px';
      t.parentNode.insertBefore(holder, t);
      addButton(holder, t, name);
    });
  }

  if (!d.getElementById('grid-export-css')) {
    var st = d.createElement('style');
    st.id = 'grid-export-css';
    st.textContent = '.grid-export-btn{padding:7px 12px;border:1px solid #cbd5e1;' +
      'border-radius:8px;background:#fff;font-size:12.5px;cursor:pointer;color:#1e293b}' +
      '.grid-export-btn:hover{background:#f1f5f9}';
    d.head.appendChild(st);
  }

  w.GridExport = {toExcel: toExcel, addButton: addButton, autowire: autowire};
  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', autowire);
  else autowire();
})(window, document);
