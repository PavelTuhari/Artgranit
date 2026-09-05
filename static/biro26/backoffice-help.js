/* Back-office OfficePlus — butoanele «?» de ajutor pe fiecare filă.
 *
 * RO: Fișier separat (CLAUDE.md, regula №2): în backoffice.html intră doar
 *     <script src>. Nu atinge nimic din logica filelor — doar adaugă lângă
 *     titlul fiecărei file un link spre secțiunea ei din ghidul utilizatorului
 *     și un buton «Ghid» în bara de sus.
 * RU: Отдельный файл (правило №2): в шаблон — одна строка <script src>.
 *
 * Ghidul: docs/Biro26/GHID_BACKOFFICE.md, servit de modulul b26docs.
 */
(function () {
  'use strict';

  var GUIDE = '/UNA.md/orasldev/b26docs/Biro26/GHID_BACKOFFICE.md';

  /* fila (id-ul panelului) → ancora din ghid */
  var ANCHORS = {
    'panel-source':   'sursa',
    'panel-dict':     'nomenclator',
    'panel-groups':   'grupe',
    'panel-prices':   'preturi',
    'panel-mapping':  'mapare',
    'panel-wizard':   'import',
    'panel-products': 'marfa',
    'panel-stock':    'stoc',
    'panel-services': 'servicii'
  };

  var TITLE = { ro: 'Ghid: cum se folosește această filă',
                ru: 'Справка: как пользоваться этой вкладкой',
                en: 'Guide: how to use this tab' };
  var LABEL = { ro: 'Ghid', ru: 'Справка', en: 'Guide' };

  function lang() {
    try { return (window.LANG || localStorage.getItem('biro26_lang') || 'ro'); }
    catch (e) { return 'ro'; }
  }

  function makeLink(href, text, title) {
    var a = document.createElement('a');
    a.href = href;
    a.target = '_blank';
    a.rel = 'noopener';
    a.className = 'bo-help';
    a.title = title;
    a.textContent = text;
    a.setAttribute('aria-label', title);
    return a;
  }

  function inject() {
    if (document.getElementById('bo-help-style')) return;
    var st = document.createElement('style');
    st.id = 'bo-help-style';
    st.textContent =
      '.bo-help{display:inline-flex;align-items:center;justify-content:center;' +
      'width:20px;height:20px;margin-left:8px;border-radius:50%;' +
      'border:1px solid #93c5fd;background:#eff6ff;color:#1d4ed8;' +
      'font:600 12px/1 system-ui,sans-serif;text-decoration:none;vertical-align:middle}' +
      '.bo-help:hover{background:#1d4ed8;color:#fff}' +
      '.bo-help.bo-help-top{width:auto;height:auto;padding:3px 9px;border-radius:12px;' +
      'font-size:12px;margin:0 8px 0 0}';
    document.head.appendChild(st);

    var L = lang(), t = TITLE[L] || TITLE.ro;

    Object.keys(ANCHORS).forEach(function (pid) {
      var panel = document.getElementById(pid);
      if (!panel) return;
      var h2 = panel.querySelector('.sec-header h2');
      if (!h2 || h2.parentNode.querySelector('.bo-help')) return;
      h2.insertAdjacentElement('afterend',
        makeLink(GUIDE + '#' + ANCHORS[pid], '?', t));
    });

    /* «Ghid» în bara de sus, înaintea comutatorului de limbă */
    var right = document.querySelector('.menu-bar .menu-right');
    var sw = right && right.querySelector('.lang-switch');
    if (right && sw && !right.querySelector('.bo-help-top')) {
      var top = makeLink(GUIDE, '📖 ' + (LABEL[L] || LABEL.ro), t);
      top.classList.add('bo-help-top');
      right.insertBefore(top, sw);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', inject);
  } else {
    inject();
  }
})();
