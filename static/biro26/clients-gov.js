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
    // RO: pagina veche nu are clasele .btn/.primary — stiluri inline, ca butoanele sa arate ca butoane
    const B = 'display:inline-block;margin:2px 6px 2px 0;padding:7px 12px;border:1px solid #cbd5e1;border-radius:8px;background:#fff;color:#1e293b;font-size:12.5px;text-decoration:none;cursor:pointer';
    const P = B + ';background:#2563eb;border-color:#1d4ed8;color:#fff;font-weight:700';
    const btn = (k, label) => '<a style="' + (k === cur ? P : B) + '" download href="' + LAUNCHER + k + '?return=' + ret + '">' + label + '</a>';
    // RO: Gatekeeper (05.09.2026, proprietarul: «Apple could not verify … is free of malware»):
    //     orice executabil descarcat primeste marcajul quarantine — dam trei iesiri
    const MAC_CMD = 'xattr -d com.apple.quarantine ~/Downloads/start_contragenti.command && ~/Downloads/start_contragenti.command';
    const hint = {
      command: 'macOS: dacă Contragenti e instalat, cel mai simplu — Launchpad → Contragenti. La dublu-click pe scriptul descărcat macOS spune «Apple could not verify…»: ' +
        'fie Setări sistem → Confidențialitate și securitate → «Deschide oricum», fie comanda în Terminal: <code style="background:#eef;padding:1px 5px;border-radius:4px">' + MAC_CMD + '</code> ' +
        '<button style="' + B + ';padding:2px 8px;font-size:11.5px" onclick="navigator.clipboard.writeText(\'' + MAC_CMD + '\');this.textContent=\'✓ copiat\'">Copiază comanda</button>',
      bat: 'Windows: dublu-click pe start_contragenti.bat (are nevoie de Python 3 dacă Contragenti nu e instalat din MSI). Dacă SmartScreen avertizează: «Mai multe informații» → «Rulează oricum».',
      py: 'Linux: python3 start_contragenti.py (Tkinter: sudo apt install python3-tk).'}[cur];
    msgEl.dataset.dl = '1';
    msgEl.innerHTML =
      '<div style="border:1px solid #f0ad4e;background:#fff8ec;border-radius:8px;padding:10px 12px;margin-top:6px">' +
      '<b>⚠ Contragenti (' + esc(host()) + ') nu este disponibil</b> · <span style="color:#64748b">Утилита Contragenti недоступна</span>' +
      '<div style="margin:6px 0;color:#475569">Utilitarul nu rulează pe acest calculator (sau a fost închis). Descărcați scriptul de pornire și lansați-l — ' +
      'găsește instalarea (sau o descarcă de pe GitHub), pornește utilitarul și vă întoarce aici. Apoi repetați căutarea.</div>' +
      '<div>' + btn('command', ' macOS — start_contragenti.command') + btn('bat', '⊞ Windows — start_contragenti.bat') +
      btn('py', '🐧 Linux / orice OS — start_contragenti.py') +
      '<button style="' + B + '" onclick="govRecheck()">↻ Verifică din nou</button></div>' +
      '<div style="margin-top:6px;color:#64748b;font-size:12px">' + hint + '</div></div>';
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
    if (!window.pickFromGov) return;
    const p = window.pickFromGov(q);
    // RO: pagina inlocuieste mesajul cu «Se deschide utilitarul…»; il completam cu contextul
    setTimeout(() => { if (msg && /^Se deschide/.test(msg.textContent)) msg.textContent = 'Nimic în baza OfficePlus pentru «' + q + '» → date.gov.md: ' + msg.textContent; }, 150);
    await p;
  };
})();
