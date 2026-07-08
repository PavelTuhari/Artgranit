// RO: Helper-e Handlebars comune pentru rapoartele Biro26 (bani, index,
//     suma in litere in romana). / EN: shared Handlebars helpers for the
//     Biro26 reports (money format, row index, Romanian amount-in-words).

function fmt(n) {
  const v = Number(n) || 0;
  return v.toFixed(2).replace('.', ',').replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

function inc(i) { return Number(i) + 1; }

// RO: numarul intreg in litere (pana la 999 999 999)
function roWords(nRaw) {
  let n = Math.floor(Math.abs(Number(nRaw) || 0));
  if (n === 0) return 'zero';
  const uni = ['', 'unu', 'doi', 'trei', 'patru', 'cinci', 'șase', 'șapte', 'opt', 'nouă'];
  const spr = ['zece', 'unsprezece', 'doisprezece', 'treisprezece', 'paisprezece',
               'cincisprezece', 'șaisprezece', 'șaptesprezece', 'optsprezece', 'nouăsprezece'];
  function sub1000(x) {
    const parts = [];
    const h = Math.floor(x / 100), r = x % 100;
    if (h === 1) parts.push('o sută');
    else if (h === 2) parts.push('două sute');
    else if (h > 2) parts.push(uni[h] + ' sute');
    if (r >= 10 && r <= 19) parts.push(spr[r - 10]);
    else {
      const t = Math.floor(r / 10), u = r % 10;
      if (t === 2) parts.push(u ? 'douăzeci și ' + uni[u] : 'douăzeci');
      else if (t > 2) parts.push(u ? uni[t] + 'zeci și ' + uni[u] : uni[t] + 'zeci');
      else if (u) parts.push(u === 2 && x >= 100 ? 'doi' : uni[u]);
    }
    return parts.join(' ');
  }
  function scale(x, one, few, many) {
    if (x === 1) return one;
    if (x === 2) return 'două ' + few;
    if (x < 20) return sub1000(x) + ' ' + few;
    return sub1000(x) + ' de ' + many;
  }
  const out = [];
  const mil = Math.floor(n / 1000000); n %= 1000000;
  const mii = Math.floor(n / 1000); n %= 1000;
  if (mil) out.push(scale(mil, 'un milion', 'milioane', 'milioane'));
  if (mii) out.push(scale(mii, 'o mie', 'mii', 'mii'));
  if (n) out.push(sub1000(n));
  const s = out.join(' ');
  return s.charAt(0).toUpperCase() + s.slice(1);
}

// RO: "Șase sute șaizeci și cinci, 00 (665,00) lei"
function roAmount(total) {
  const v = Number(total) || 0;
  const bani = Math.round((v - Math.floor(v)) * 100);
  return roWords(v) + ', ' + String(bani).padStart(2, '0') + ' (' + fmt(v) + ') lei';
}
