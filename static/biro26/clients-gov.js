/* Clienți magazin (biro26-clients) — căutarea unică OfficePlus → date.gov.md
   și pornirea utilitarului Contragenti (05.09.2026, cerința proprietarului:
   «căutare și pentru date.gov în singura celulă de căutare; dacă nu se
   găsește nimic în baza OfficePlus — automat pe date.gov.md; dacă utilitarul
   e închis, butonul spune că 127.0.0.1 nu este disponibil și se descarcă un
   script Python care îl pornește — Mac, Windows, Linux»).

   RO: fișier separat (regula nr. 2 din CLAUDE.md) — în clients.html rămîn doar
   apelurile. Depinde de GOV_BASE / pickFromGov / govHealth din pagină.
   Scriptul de pornire e generat de modulul CRM (modules/crm/launcher.py):
   /UNA.md/orasldev/crm/launcher/<py|command|bat>?return=<pagina curentă>.
   EN: single search with automatic date.gov.md fallback + Contragenti starter. */
(function () {
  const LAUNCHER = '/UNA.md/orasldev/crm/launcher/';
  function host() { return (window.GOV_BASE || 'http://127.0.0.1:9393').replace(/^https?:\/\//, ''); }
  function os() {
    const p = (navigator.platform || '') + ' ' + (navigator.userAgent || '');
    return /Mac/i.test(p) ? 'command' : /Win/i.test(p) ? 'bat' : 'py';
  }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c])); }

  /* RO: panoul «Contragenti (127.0.0.1:9393) nu este disponibil» + scriptul de pornire */
  window.govOffline = function (msgEl) {
    if (!msgEl) return;
    const ret = encodeURIComponent(location.pathname);
    const cur = os();
    const btn = (k, label) => '<a class="btn' + (k === cur ? ' primary' : '') + '" style="margin:2px 4px 2px 0" download href="' +
      LAUNCHER + k + '?return=' + ret + '">' + label + '</a>';
    const hint = {
      command: 'macOS: dublu-click pe start_contragenti.command (prima dată: click-dreapta → Deschide). Se deschide Terminal, pornește Contragenti și browserul revine aici.',
      bat: 'Windows: dublu-click pe start_contragenti.bat (are nevoie de Python 3 dacă Contragenti nu e instalat din MSI).',
      py: 'Linux: python3 start_contragenti.py (Tkinter: sudo apt install python3-tk).'}[cur];
    msgEl.dataset.dl = '1';
    msgEl.innerHTML =
      '<div style="border:1px solid #f0ad4e;background:#fff8ec;border-radius:8px;padding:10px 12px;margin-top:6px">' +
      '<b>⚠ Contragenti (' + esc(host()) + ') nu este disponibil</b> · <span style="color:#64748b">Утилита Contragenti недоступна</span>' +
      '<div style="margin:6px 0;color:#475569">Utilitarul nu rulează pe acest calculator (sau a fost închis). Descărcați scriptul de pornire și lansați-l — ' +
      'găsește instalarea (sau o descarcă de pe GitHub), pornește utilitarul și vă întoarce aici. Apoi repetați căutarea.</div>' +
      '<div>' + btn('command', ' macOS — start_contragenti.command') + btn('bat', '⊞ Windows — start_contragenti.bat') +
      btn('py', '🐧 Linux / orice OS — start_contragenti.py') +
      '<button class="btn" style="margin:2px 0" onclick="govRecheck()">↻ Verifică din nou</button></div>' +
      '<div style="margin-top:6px;color:#64748b;font-size:12px">' + esc(hint) + '</div></div>';
  };

  window.govRecheck = async function () {
    const msg = document.getElementById('nc-msg');
    const h = window.govHealth ? await window.govHealth() : null;
    if (h) {
      if (msg) { msg.dataset.dl = ''; msg.textContent = 'Contragenti răspunde (' + (h.db_count || 0) + ' înregistrări în baza locală). Repetați căutarea.'; }
      const el = document.getElementById('nc-gov'); if (el) { el.style.opacity = '1'; el.title = 'Contragenti activ'; }
      const q = document.getElementById('q'); if (q && q.value.trim()) window.govAuto(q.value.trim());
    } else if (msg) {
      window.govOffline(msg);
    }
  };

  /* RO: căutarea unică: pagina a căutat în baza OfficePlus și nu a găsit nimic
     → automat pe date.gov.md prin Contragenti, cu același filtru. */
  window.govAuto = async function (q) {
    const msg = document.getElementById('nc-msg');
    if (!q) return;
    const h = window.govHealth ? await window.govHealth() : null;
    if (!h) { window.govOffline(msg); return; }
    if (msg) { msg.dataset.dl = ''; msg.textContent = 'Nimic în baza OfficePlus pentru «' + q + '» — caut pe date.gov.md prin Contragenti… · В базе OfficePlus ничего нет, ищу на date.gov.md'; }
    const wrap = document.querySelector('.wrap'); if (wrap) wrap.scrollIntoView({behavior: 'smooth', block: 'start'});
    if (window.pickFromGov) await window.pickFromGov(q);
  };
})();
