/* RO: Consimtamintul pentru cookie-uri — officeplus.md (01.10.2026, noua lege a
 * datelor cu caracter personal, model GDPR / ePrivacy).
 *
 * Regula: NIMIC ne-esential nu porneste inainte de alegerea vizitatorului.
 *   - Analitice  -> Google Analytics (cookie _ga, _ga_*): gtag.js se descarca abia
 *                   dupa «Accept» (consent mode basic; in <head> ramine doar coada
 *                   dataLayer cu consent default = denied, fara nicio cerere la Google);
 *   - Functionale -> chatul JivoChat (localStorage jv_*): scriptul lor abia dupa «Accept»;
 *   - Marketing  -> atribuirea reclamelor (cookie-urile serverului op_vid / op_attr,
 *                   models/biro26_social.py le pune DOAR daca alegerea contine m1).
 * Strict necesare (sesiunea contului, cosul, limba, alegerea insasi) nu cer acord.
 *
 * Alegerea: cookie `op_consent` = "v1.a0.f1.m0.<unix>", 180 de zile, pe tot domeniul.
 * La schimbarea categoriilor -> CONSENT_VERSION nou si toti vizitatorii sint intrebati din nou.
 * API: window.opConsent.has('a'|'f'|'m'), window.opConsent.open() (linkul «Setări cookie»
 * din subsol), eveniment `op:consent` pe document.
 * Folosit de templates/biro26/_site_cookie_consent.html si de mu-plugin-ul WordPress.
 * Documentatie: docs/Biro26/COOKIE_CONSIMTAMINT_2026-10-09.md
 */
(function () {
  'use strict';
  if (window.opConsent) return;

  var CONSENT_VERSION = 'v1';
  var COOKIE = 'op_consent';
  var DAYS = 180;
  var PRIVACY_URL = '/politica-de-confidentialitate';

  var T = {
    ro: {
      title: 'Folosim cookie-uri',
      text: 'Cookie-urile strict necesare țin coșul, contul și limba aleasă. Cu acordul ' +
            'dumneavoastră folosim și cookie-uri pentru chatul de asistență, statistici de ' +
            'vizitare (Google Analytics) și măsurarea reclamelor. Puteți accepta, refuza sau ' +
            'alege pe categorii; alegerea se poate schimba oricînd din „Setări cookie”, jos pe pagină.',
      more: 'Politica de confidențialitate',
      accept: 'Accept toate', reject: 'Refuz', custom: 'Personalizez',
      save: 'Salvez alegerea', settings: 'Setări cookie', always: 'Mereu active',
      cats: {
        n: ['Strict necesare', 'Sesiunea contului, coșul, limba, această alegere. Fără ele site-ul nu funcționează.'],
        f: ['Funcționale', 'Chatul de asistență JivoChat (păstrează conversația între pagini).'],
        a: ['Analitice', 'Google Analytics — cîți vizitatori avem și ce pagini citesc (cookie _ga). Fără date de contact.'],
        m: ['Marketing', 'De unde ați venit (Facebook, Google, TikTok…), ca să știm care reclamă funcționează (cookie op_vid, op_attr, 90 de zile).']
      }
    },
    ru: {
      title: 'Мы используем cookie',
      text: 'Строго необходимые cookie хранят корзину, вход в аккаунт и выбранный язык. С вашего ' +
            'согласия мы также используем cookie для чата поддержки, статистики посещений ' +
            '(Google Analytics) и оценки рекламы. Можно принять, отказаться или выбрать по ' +
            'категориям; выбор можно изменить в любой момент в «Настройки cookie» внизу страницы.',
      more: 'Политика конфиденциальности',
      accept: 'Принять все', reject: 'Отказаться', custom: 'Настроить',
      save: 'Сохранить выбор', settings: 'Настройки cookie', always: 'Всегда активны',
      cats: {
        n: ['Строго необходимые', 'Сессия аккаунта, корзина, язык, этот выбор. Без них сайт не работает.'],
        f: ['Функциональные', 'Чат поддержки JivoChat (сохраняет переписку между страницами).'],
        a: ['Аналитика', 'Google Analytics — сколько посетителей и какие страницы читают (cookie _ga). Без контактных данных.'],
        m: ['Маркетинг', 'Откуда вы пришли (Facebook, Google, TikTok…), чтобы понимать, какая реклама работает (cookie op_vid, op_attr, 90 дней).']
      }
    }
  };

  function lang() {
    try { if (typeof curLang === 'function') return curLang() === 'ru' ? 'ru' : 'ro'; } catch (e) {}
    return /(^|;\s*)lang=ru/.test(document.cookie) || /[?&]lang=ru/.test(location.search) ? 'ru' : 'ro';
  }

  function read() {
    var m = document.cookie.match(/(?:^|;\s*)op_consent=([^;]+)/);
    if (!m) return null;
    var p = decodeURIComponent(m[1]).split('.');
    if (p[0] !== CONSENT_VERSION) return null;      // versiune veche -> intrebam din nou
    var c = { a: false, f: false, m: false, t: +p[4] || 0 };
    p.slice(1, 4).forEach(function (x) { if (x.length === 2 && x[0] in c) c[x[0]] = x[1] === '1'; });
    return c;
  }

  function write(c) {
    var v = [CONSENT_VERSION, 'a' + (c.a ? 1 : 0), 'f' + (c.f ? 1 : 0), 'm' + (c.m ? 1 : 0),
             Math.floor(Date.now() / 1000)].join('.');
    var dom = /(^|\.)officeplus\.md$/.test(location.hostname) ? '; domain=.officeplus.md' : '';
    document.cookie = COOKIE + '=' + v + '; max-age=' + DAYS * 86400 + '; path=/; SameSite=Lax' +
      (location.protocol === 'https:' ? '; Secure' : '') + dom;
  }

  function delCookie(name) {
    var host = location.hostname, parts = host.split('.');
    var doms = ['', host, '.' + host];
    if (parts.length > 1) doms.push('.' + parts.slice(-2).join('.'));
    doms.forEach(function (d) {
      document.cookie = name + '=; max-age=0; path=/' + (d ? '; domain=' + d : '');
    });
  }

  var started = { a: false, f: false };

  function startAnalytics() {
    if (started.a || !window.OP_GA_ID) return;
    started.a = true;
    try { window.gtag('consent', 'update', { analytics_storage: 'granted' }); } catch (e) {}
    var s = document.createElement('script');
    s.async = true;
    s.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(window.OP_GA_ID);
    document.head.appendChild(s);
  }

  function startFunctional() {
    if (started.f || !window.OP_JIVO_ID) return;
    started.f = true;
    var s = document.createElement('script');
    s.async = true;
    s.src = '//code.jivosite.com/widget/' + encodeURIComponent(window.OP_JIVO_ID);
    document.body.appendChild(s);
  }

  function apply(c, prev) {
    if (c.a) startAnalytics();
    if (c.f) startFunctional();
    // RO: acordul retras -> curatam ce s-a apucat sa se scrie
    if (prev && prev.a && !c.a) {
      try { window.gtag('consent', 'update', { analytics_storage: 'denied' }); } catch (e) {}
      document.cookie.split(/;\s*/).forEach(function (kv) {
        var n = kv.split('=')[0];
        if (n === '_ga' || n.indexOf('_ga_') === 0 || n === '_gid') delCookie(n);
      });
    }
    if (prev && prev.f && !c.f) {
      try { Object.keys(localStorage).forEach(function (k) { if (k.indexOf('jv_') === 0) localStorage.removeItem(k); }); } catch (e) {}
    }
    var reload = (prev && ((prev.a && !c.a) || (prev.f && !c.f)));
    try { document.dispatchEvent(new CustomEvent('op:consent', { detail: c })); } catch (e) {}
    // RO: scripturile deja pornite (GA, Jivo) nu se pot «descarca» — reincarcam pagina fara ele
    if (reload) location.reload();
  }

  var box, modal;

  function el(tag, cls, html) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    return e;
  }

  function choose(c) {
    var prev = read();
    write(c);
    hide();
    apply(c, prev);
  }

  function hide() {
    if (box) { box.remove(); box = null; }
    if (modal) { modal.remove(); modal = null; }
    document.documentElement.classList.remove('opcc-open');
  }

  function banner() {
    var t = T[lang()];
    hide();
    box = el('div', 'opcc-banner');
    box.setAttribute('role', 'region');
    box.setAttribute('aria-label', t.title);
    box.innerHTML =
      '<div class="opcc-body"><strong class="opcc-title">🍪 ' + t.title + '</strong>' +
      '<p class="opcc-text">' + t.text + ' <a href="' + PRIVACY_URL + '">' + t.more + '</a></p></div>' +
      '<div class="opcc-actions">' +
      '<button type="button" class="opcc-btn opcc-reject" data-opcc="reject">' + t.reject + '</button>' +
      '<button type="button" class="opcc-btn opcc-custom" data-opcc="custom">' + t.custom + '</button>' +
      '<button type="button" class="opcc-btn opcc-accept" data-opcc="accept">' + t.accept + '</button>' +
      '</div>';
    box.addEventListener('click', function (e) {
      var a = e.target.getAttribute && e.target.getAttribute('data-opcc');
      if (a === 'accept') choose({ a: true, f: true, m: true });
      else if (a === 'reject') choose({ a: false, f: false, m: false });
      else if (a === 'custom') settings();
    });
    document.body.appendChild(box);
    document.documentElement.classList.add('opcc-open');
  }

  function settings() {
    var t = T[lang()], cur = read() || { a: false, f: false, m: false };
    if (modal) modal.remove();
    modal = el('div', 'opcc-modal');
    modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true');
    modal.setAttribute('aria-label', t.settings);
    var rows = ['n', 'f', 'a', 'm'].map(function (k) {
      var on = k === 'n' ? true : cur[k];
      return '<label class="opcc-row"><span class="opcc-row-txt"><b>' + t.cats[k][0] + '</b><small>' +
        t.cats[k][1] + '</small></span>' +
        (k === 'n' ? '<span class="opcc-always">' + t.always + '</span>'
                   : '<input type="checkbox" class="opcc-sw" data-cat="' + k + '"' + (on ? ' checked' : '') + '>') +
        '</label>';
    }).join('');
    modal.innerHTML =
      '<div class="opcc-dialog"><div class="opcc-dhead"><strong>' + t.settings + '</strong>' +
      '<button type="button" class="opcc-x" data-opcc="close" aria-label="×">×</button></div>' + rows +
      '<div class="opcc-actions">' +
      '<button type="button" class="opcc-btn opcc-reject" data-opcc="reject">' + t.reject + '</button>' +
      '<button type="button" class="opcc-btn opcc-custom" data-opcc="save">' + t.save + '</button>' +
      '<button type="button" class="opcc-btn opcc-accept" data-opcc="accept">' + t.accept + '</button>' +
      '</div><p class="opcc-text"><a href="' + PRIVACY_URL + '">' + t.more + '</a></p></div>';
    modal.addEventListener('click', function (e) {
      var a = e.target.getAttribute && e.target.getAttribute('data-opcc');
      if (a === 'accept') choose({ a: true, f: true, m: true });
      else if (a === 'reject') choose({ a: false, f: false, m: false });
      else if (a === 'save') {
        var c = { a: false, f: false, m: false };
        modal.querySelectorAll('.opcc-sw').forEach(function (i) { c[i.getAttribute('data-cat')] = i.checked; });
        choose(c);
      } else if (a === 'close' || e.target === modal) {
        modal.remove(); modal = null;
        if (!read() && !box) banner();
      }
    });
    document.body.appendChild(modal);
    var first = modal.querySelector('.opcc-sw');
    if (first) first.focus();
  }

  function footerLink() {
    // RO: «Setări cookie» linga «Politica de confidentialitate» din subsol (fara sa atingem sablonul)
    var p = document.querySelector('a[href="' + PRIVACY_URL + '"]');
    if (!p || document.querySelector('[data-opcc-link]')) return;
    var a = el('a', null, T[lang()].settings);
    a.href = '#';
    a.setAttribute('data-opcc-link', '1');
    a.addEventListener('click', function (e) { e.preventDefault(); settings(); });
    var li = p.closest('li');
    if (li) { var nli = el('li'); nli.appendChild(a); li.parentNode.insertBefore(nli, li.nextSibling); }
    else p.parentNode.insertBefore(a, p.nextSibling);
  }

  window.opConsent = {
    has: function (k) { var c = read(); return !!(c && c[k]); },
    get: read,
    open: settings
  };

  function init() {
    var c = read();
    if (c) apply(c, null); else banner();
    footerLink();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
