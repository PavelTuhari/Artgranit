// RO: Helper-e Handlebars pentru rapoartele modulului SDA. Fișierul pleacă
//     INLINE în corpul cererii către serviciul de randare (vezi report.py),
//     nu în magazia de șabloane a serviciului — modulul nu lasă nimic în
//     codul comun (docs/CORE_MODULES.md).

function inc(i) { return Number(i) + 1; }

function nvl(v, fallback) {
  if (v === null || v === undefined || v === '') { return fallback; }
  return v;
}

function num(v) {
  if (v === null || v === undefined || v === '') { return '—'; }
  return String(v).replace('.', ',');
}

function eq(a, b) { return a === b; }
