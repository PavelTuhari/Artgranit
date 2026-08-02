/* =====================================================================
   OfficePlus — noul site (Figma/landingfigma1): JS comun pentru toate
   paginile (header, cos partajat, i18n RO/RU, carduri produs).
   RO: cosul este ACELASI localStorage ('biro26_shop_cart') ca in
   magazinul clasic /biro26-shop — checkout-ul foloseste aceleasi API-uri.
   ===================================================================== */
const API = '/api/biro26/shop';
const CART_KEY = 'biro26_shop_cart';
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g,
  c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
async function j(url, opts) {
  opts = opts || {};
  if (opts.body) opts.headers = Object.assign({'Content-Type': 'application/json'},
                                              opts.headers || {});
  opts.credentials = 'include';
  const r = await fetch(url, opts);
  return r.json().catch(() => ({}));
}
function toast(m, err) {
  const d = document.createElement('div');
  d.className = 'toast' + (err ? ' err' : ''); d.textContent = m;
  document.body.appendChild(d); setTimeout(() => d.remove(), 3600);
}

/* ── i18n RO/RU ──────────────────────────────────────────────────────── */
const T = {
  hours:      {ro: 'Astăzi lucrăm de la 09:00 până la 19:00', ru: 'Сегодня работаем с 09:00 до 19:00'},
  delivery:   {ro: 'Livrare', ru: 'Доставка'},
  catalog:    {ro: 'Catalog', ru: 'Каталог'},
  search:     {ro: 'Caută produse…', ru: 'Найти товары…'},
  seeOffer:   {ro: 'Vezi oferta', ru: 'Смотреть предложение'},
  dealOfDay:  {ro: 'Produsul zilei', ru: 'Товар дня'},
  limited:    {ro: 'Stoc limitat', ru: 'Ограниченное наличие'},
  buy:        {ro: 'Cumpără', ru: 'Купить'},
  h1:         {ro: 'Magazin online de birotică și papetărie în Moldova', ru: 'Интернет-магазин канцтоваров и офисной техники в Молдове'},
  tag:        {ro: 'Oferte OfficePlus', ru: 'Предложения OfficePlus'},
  best:       {ro: 'Cei mai buni', ru: 'Лучшие товары'},
  bestSub:    {ro: 'Reduceri actuale la produsele populare pentru birou și studii', ru: 'Актуальные скидки на популярные товары для офиса и учебы'},
  popular:    {ro: 'Cele mai populare', ru: 'Самые популярные'},
  popularSub: {ro: 'Produse populare, alese cel mai des de clienții noștri', ru: 'Популярные товары, которые выбирают чаще всего'},
  seeAll:     {ro: 'Vezi toate →', ru: 'Смотреть все →'},
  brands:     {ro: 'Branduri populare', ru: 'Популярные бренды'},
  all:        {ro: 'Toate', ru: 'Все'},
  byCat:      {ro: 'Pe categorii', ru: 'По категориям'},
  nlTitle:    {ro: 'Abonează-te la newsletter', ru: 'Подпишитесь на рассылку'},
  nlText:     {ro: 'Abonează-te pentru noutăți: fii la curent cu cele mai noi produse, oferte și promoții, abonându-te la newsletter-ul nostru.', ru: 'Подпишитесь на новости: будьте в курсе новых товаров, предложений и акций.'},
  subscribe:  {ro: 'Abonează-te', ru: 'Подписаться'},
  footDesc:   {ro: 'Magazin online de papetărie și birotică cu livrare în toată Moldova. Sortiment orientat spre birouri, studenți și proiecte creative.', ru: 'Интернет-магазин канцелярских товаров с доставкой по всей Молдове. Ассортимент ориентирован на офисы, студентов и творческие задачи.'},
  forClients: {ro: 'Pentru clienți:', ru: 'Для клиентов:'},
  home:       {ro: 'Pagina principală', ru: 'Главная'},
  about:      {ro: 'Despre companie', ru: 'О компании'},
  contacts:   {ro: 'Contacte', ru: 'Контакты'},
  returns:    {ro: 'Retur produse', ru: 'Возврат товаров'},
  cart:       {ro: 'Coș', ru: 'Корзина'},
  useful:     {ro: 'Utile:', ru: 'Полезное:'},
  terms:      {ro: 'Termeni și condiții', ru: 'Условия использования'},
  payDelivery:{ro: 'Plată și livrare', ru: 'Оплата и доставка'},
  privacy:    {ro: 'Politica de confidențialitate', ru: 'Политика конфиденциальности'},
  backoffice: {ro: 'Back-office', ru: 'Бэк-офис'},
  phone:      {ro: 'Telefon', ru: 'Телефон'},
  rights:     {ro: 'Toate drepturile rezervate.', ru: 'Все права защищены.'},
  inStock:    {ro: 'În stoc', ru: 'В наличии'},
  onOrder:    {ro: 'La comandă', ru: 'Под заказ'},
  added:      {ro: 'Adăugat în coș', ru: 'Добавлено в корзину'},
  subscribed: {ro: 'Mulțumim! V-ați abonat.', ru: 'Спасибо! Вы подписались.'},
  /* catalog (PLP) */
  filters:    {ro: 'Filtre', ru: 'Фильтры'},
  categories: {ro: 'Categorii', ru: 'Категории'},
  price:      {ro: 'Preț, lei', ru: 'Цена, лей'},
  brandsF:    {ro: 'Branduri', ru: 'Бренды'},
  reset:      {ro: 'Resetează', ru: 'Сбросить'},
  results:    {ro: 'produse', ru: 'товаров'},
  sortName:   {ro: 'Alfabetic A–Z', ru: 'По алфавиту А–Я'},
  sortNameD:  {ro: 'Alfabetic Z–A', ru: 'По алфавиту Я–А'},
  sortUp:     {ro: 'Preț crescător', ru: 'Цена по возрастанию'},
  sortDown:   {ro: 'Preț descrescător', ru: 'Цена по убыванию'},
  noResults:  {ro: 'Nimic găsit — încercați alt cuvânt', ru: 'Ничего не найдено — попробуйте другое слово'},
  /* PDP */
  addCart:    {ro: 'Adaugă în coș', ru: 'В корзину'},
  qty:        {ro: 'Cantitate', ru: 'Количество'},
  descr:      {ro: 'Descriere', ru: 'Описание'},
  comments:   {ro: 'Comentarii', ru: 'Комментарии'},
  sendComment:{ro: 'Trimite', ru: 'Отправить'},
  yourComment:{ro: 'Comentariul dvs.…', ru: 'Ваш комментарий…'},
  ratePrice:  {ro: 'Preț ofertă în rate', ru: 'Цена в рассрочку'},
  rateFrom:   {ro: 'în rate de la', ru: 'в рассрочку от'},
  perMonth:   {ro: 'lei/lună', ru: 'лей/мес'},
  creditH:    {ro: 'Rate și credit', ru: 'Рассрочка и кредит'},
  code:       {ro: 'Cod', ru: 'Код'},
  variants:   {ro: 'Variante', ru: 'Варианты'},
  related:    {ro: 'Produse similare', ru: 'Похожие товары'},
  /* cart page */
  cartTitle:  {ro: 'Coșul meu', ru: 'Моя корзина'},
  cartEmpty:  {ro: 'Coșul este gol', ru: 'Корзина пуста'},
  goCatalog:  {ro: 'Mergi la catalog', ru: 'Перейти в каталог'},
  product:    {ro: 'Produs', ru: 'Товар'},
  total:      {ro: 'Total', ru: 'Итого'},
  clearCart:  {ro: 'Golește coșul', ru: 'Очистить корзину'},
  checkout:   {ro: 'Plasează comanda', ru: 'Оформить заказ'},
  transport:  {ro: 'Transport (obligatoriu)', ru: 'Транспорт (обязательно)'},
  distance:   {ro: 'Distanța, km', ru: 'Расстояние, км'},
  center:     {ro: 'Centrul logistic', ru: 'Логистический центр'},
  services:   {ro: 'Servicii opționale', ru: 'Дополнительные услуги'},
  payMethod:  {ro: 'Metoda de achitare', ru: 'Способ оплаты'},
  payMethodHint: {ro: 'Alege tipul de credit / rate sau plata standard', ru: 'Выберите тип кредита / рассрочки или обычную оплату'},
  payStd:     {ro: 'Standard (factură)', ru: 'Стандартно (счёт)'},
  payCredit:  {ro: 'Rate / credit', ru: 'Рассрочка / кредит'},
  tvaMode:    {ro: 'TVA', ru: 'НДС'},
  needLogin:  {ro: 'Pentru comandă autentificați-vă sau înregistrați-vă', ru: 'Для заказа войдите или зарегистрируйтесь'},
  invoiceOk:  {ro: 'Contul de plată a fost creat!', ru: 'Счёт на оплату создан!'},
  invoiceNr:  {ro: 'Cont de plată Nr.', ru: 'Счёт на оплату №'},
  pdfInvoice: {ro: '📄 PDF Cont de plată', ru: '📄 PDF Счёт'},
  pdfOrder:   {ro: '📄 PDF Comandă', ru: '📄 PDF Заказ'},
  avans:      {ro: 'Avans, lei', ru: 'Аванс, лей'},
  months:     {ro: 'luni', ru: 'мес'},
  ratesTiles: {ro: 'Alegeți termenul', ru: 'Выберите срок'},
  stdPrice:   {ro: 'Preț standard', ru: 'Обычная цена'},
  cartRate:   {ro: 'Preț în rate', ru: 'Цена в рассрочку'},
  /* account */
  account:    {ro: 'Contul meu', ru: 'Мой кабинет'},
  login:      {ro: 'Autentificare', ru: 'Вход'},
  register:   {ro: 'Înregistrare', ru: 'Регистрация'},
  logout:     {ro: 'Ieșire', ru: 'Выйти'},
  email:      {ro: 'Email', ru: 'Email'},
  password:   {ro: 'Parola', ru: 'Пароль'},
  name:       {ro: 'Nume Prenume', ru: 'Фамилия Имя'},
  address:    {ro: 'Adresa de livrare', ru: 'Адрес доставки'},
  phoneF:     {ro: 'Telefon', ru: 'Телефон'},
  idno:       {ro: 'IDNO (pers. juridice)', ru: 'IDNO (для юрлиц)'},
  welcome:    {ro: 'Bine ați venit', ru: 'Добро пожаловать'},
  /* favorite & comparare */
  favorites:  {ro: 'Favorite', ru: 'Избранное'},
  compare:    {ro: 'Compară produse', ru: 'Сравнить товары'},
  favAdded:   {ro: 'Adăugat la favorite', ru: 'Добавлено в избранное'},
  favRemoved: {ro: 'Scos din favorite', ru: 'Удалено из избранного'},
  cmpAdded:   {ro: 'Adăugat la comparare', ru: 'Добавлено к сравнению'},
  cmpRemoved: {ro: 'Scos din comparare', ru: 'Убрано из сравнения'},
  favEmpty:   {ro: 'Nu aveți produse favorite încă — apăsați ♡ pe carduri', ru: 'Пока нет избранных товаров — нажмите ♡ на карточках'},
  cmpEmpty:   {ro: 'Alegeți produse pentru comparare de pe fișele lor (max 4)', ru: 'Добавьте товары к сравнению со страниц товаров (макс. 4)'},
  cmpBtn:     {ro: '⚖ Compară', ru: '⚖ Сравнить'},
  characteristics: {ro: 'Caracteristici', ru: 'Характеристики'},
  contactUs:  {ro: 'Contactați-ne', ru: 'Свяжитесь с нами'},
  addr:       {ro: 'Adresa', ru: 'Адрес'},
  brandSearch:{ro: 'Caută brand…', ru: 'Найти бренд…'},
};
function curLang() {
  const l = localStorage.getItem('biro26_lang') || 'ro';
  return l === 'ru' ? 'ru' : 'ro';
}
function tr(k) { const e = T[k]; return e ? (e[curLang()] || e.ro) : ''; }
/* RO: text bilingv «RO · RU» — bl() alege dupa limba curenta, biS() taie o
   string gata scrisa in ambele limbi (separator « · », RO inainte, RU dupa). */
function bl(ro, ru) { return curLang() === 'ru' ? ru : ro; }
function biS(s) { s = String(s); const i = s.indexOf(' · ');
  return i < 0 ? s : (curLang() === 'ru' ? s.slice(i + 3) : s.slice(0, i)); }
function setLang(l) {
  localStorage.setItem('biro26_lang', l); applyLang();
  if (window.onLangChange) window.onLangChange();
}
function applyLang() {
  const l = curLang();
  document.querySelectorAll('.lang-item').forEach(e =>
    e.classList.toggle('is-active', e.dataset.lang === l));
  document.querySelectorAll('[data-t]').forEach(e => {
    const v = tr(e.dataset.t); if (v) e.textContent = v; });
  document.querySelectorAll('[data-p]').forEach(e => {
    const v = tr(e.dataset.p); if (v) e.placeholder = v; });
  // RO: elemente marcate data-bi — continutul original tine ambele limbi
  //     («RO · RU», poate contine si linkuri); afisam doar jumatatea limbii.
  document.querySelectorAll('[data-bi]').forEach(e => {
    if (!e.dataset.biOrig) e.dataset.biOrig = e.innerHTML;
    const s = e.dataset.biOrig, i = s.indexOf(' · ');
    if (i >= 0) e.innerHTML = l === 'ru' ? s.slice(i + 3) : s.slice(0, i);
  });
  document.querySelectorAll('[data-bp]').forEach(e => {   // placeholder bilingv
    if (!e.dataset.bpOrig) e.dataset.bpOrig = e.placeholder;
    const s = e.dataset.bpOrig, i = s.indexOf(' · ');
    if (i >= 0) e.placeholder = l === 'ru' ? s.slice(i + 3) : s.slice(0, i);
  });
}

/* ── cos ─────────────────────────────────────────────────────────────── */
function cart() { try { return JSON.parse(localStorage.getItem(CART_KEY) || '[]'); }
  catch (e) { return []; } }
function saveCartLS(c) { localStorage.setItem(CART_KEY, JSON.stringify(c)); cartBadge();
  if (window.onCartChange) window.onCartChange(); }
function cartBadge() {
  const n = cart().reduce((s, i) => s + (i.qty || 0), 0);
  const b = document.getElementById('cart-badge');
  if (b) { b.style.display = n ? '' : 'none'; b.textContent = n; }
}
window.addEventListener('storage', cartBadge);
function addToCart(cod, name, price, qty) {
  const c = cart(); const ex = c.find(i => i.cod === cod);
  if (ex) ex.qty += (qty || 1); else c.push({cod, name, price, qty: qty || 1});
  saveCartLS(c); toast('🛒 ' + tr('added'));
}

/* ── produse ─────────────────────────────────────────────────────────── */
function pname(p) { return (curLang() === 'ru' && p.namerus)
  ? p.namerus : (p.denumirea || p.namerus || ''); }
function pprice(p) {
  // RO: coloana de pret dupa TIPUL clientului (fizica/juridica) —
  //     window.PRICE_FIELD vine din server; fallback pe retail
  const f = window.PRICE_FIELD || 'retail1';
  const v = parseFloat(String(p[f] != null ? p[f] : '').replace(',', '.'));
  return (v > 0 ? v : parseFloat(String(p.retail1 || '').replace(',', '.'))) || 0;
}
function fmtLei(v) { return v.toLocaleString('ro-MD', {maximumFractionDigits: 2}) + ' lei'; }
function openProd(cod) { location.href = '/produs/' + cod; }
function uniq(rows) { const seen = new Set(); return (rows || []).filter(p => {
  const k = p.master_cod || p.denumirea; if (seen.has(k)) return false;
  seen.add(k); return true; }); }
const PMAP = {};
/* RO: rata Liber Card (+X% silentios) — valorile vin din YBIRO_SETTINGS
   prin variabilele globale LIBER_PCT/LIBER_MIN setate de sablon. */
function liberHtml(price, small) {
  if (!(window.LIBER_PCT > 0) || price < (window.LIBER_MIN || 0)) return '';
  const v = price * (1 + window.LIBER_PCT / 100);
  return '<div style="font-size:' + (small ? 11.5 : 13) + 'px;color:#1d4ed8;' +
    'font-weight:700">' + tr('ratePrice') + ': ' + fmtLei(v) + '</div>';
}
/* RO: familii de variante (culoare/marime — BIRO26_VARIANTS): selectorul
   apare pe card cind produsul are variante; lista se incarca lenes la
   focus, iar in cos intra COD-ul variantei alese (ca in magazinul clasic). */
const VARC = {};
async function loadVariants(cod) {
  const sel = document.getElementById('v-' + cod);
  if (!sel || sel.dataset.loaded) return;
  sel.dataset.loaded = '1';
  const r = VARC[cod] || await j(API + '/variants?cod=' + cod);
  VARC[cod] = r;
  if (!r.success || !(r.data || []).length) return;
  const cur = sel.value;
  sel.innerHTML = r.data.map(v =>
    '<option value="' + v.cod_univers + '" data-name="' +
    esc(v.full_name || v.base_name || '') + '"' +
    (String(v.cod_univers) === String(cur) ? ' selected' : '') + '>' +
    esc(v.variant || v.full_name || ('#' + v.cod_univers)) + '</option>').join('');
}
function cardBuy(cod) {
  const p = PMAP[cod] || {};
  let realCod = cod, name = p.denumirea || '';
  const sel = document.getElementById('v-' + cod);
  if (sel && sel.dataset.loaded) {
    realCod = parseInt(sel.value, 10) || cod;
    const o = sel.options[sel.selectedIndex];
    if (o && o.dataset.name) name = o.dataset.name;
  }
  addToCart(realCod, name, pprice(p));
}
function cardHtml(p) {
  PMAP[p.cod] = p;
  const price = pprice(p);
  const inStock = (p.real_cant || 0) > 0;
  const varSel = (p.var_cnt || 1) > 1
    ? '<select class="varsel-sm" id="v-' + p.cod + '" ' +
      'onfocus="loadVariants(' + p.cod + ')" onclick="event.stopPropagation()">' +
      '<option value="' + p.cod + '">' + esc(p.variant || '—') + ' (' +
      p.var_cnt + ' variante ▾)</option></select>'
    : '';
  return '<article class="product-card">' +
    '<button class="wish' + (favHas(p.cod) ? ' on' : '') +
      '" type="button" aria-label="Favorite" onclick="favToggle(this,' + p.cod + ')">' +
      (favHas(p.cod) ? '❤' : '♡') + '</button>' +
    (p.image
      ? '<div class="product-img live" style="background-image:url(\'' + esc(p.image) +
        '\')" onclick="openProd(' + p.cod + ')"></div>'
      : '<div class="product-img p-markers" onclick="openProd(' + p.cod + ')"></div>') +
    '<span class="stock ' + (inStock ? 'in' : 'order') + '">' +
      tr(inStock ? 'inStock' : 'onOrder') + '</span>' +
    '<h3 class="product-name" onclick="openProd(' + p.cod + ')">' + esc(pname(p)) + '</h3>' +
    varSel +
    '<div class="product-prices"><span class="price">' + fmtLei(price) + '</span></div>' +
    liberHtml(price, true) +
    '<button class="btn-buy-sm" type="button" onclick="cardBuy(' + p.cod + ')">' +
      tr('buy') + '</button>' +
    '</article>';
}

/* ── header: cautare + newsletter ────────────────────────────────────── */
function goSearch() {
  const q = document.getElementById('q').value.trim();
  if (q) location.href = '/catalog?q=' + encodeURIComponent(q);
  return false;
}
async function subscribe() {
  const e = document.getElementById('nl-email').value.trim();
  if (e) {
    // RO: abonatii se stocheaza in Oracle (YBIRO_SITE_SUBSCRIBER)
    const r = await j('/api/biro26/site/subscribe', {method: 'POST',
      body: JSON.stringify({email: e, lang: curLang()})});
    if (r.success) { toast('✉️ ' + tr('subscribed'));
      document.getElementById('nl-email').value = ''; }
    else toast(r.error || 'Eroare', true);
  }
  return false;
}

/* ── favorite & comparare (localStorage, ca si cosul) ────────────────── */
function lsList(k) { try { return JSON.parse(localStorage.getItem(k) || '[]'); }
  catch (e) { return []; } }
function lsToggle(k, cod, max) {
  let l = lsList(k);
  if (l.includes(cod)) l = l.filter(x => x !== cod);
  else { if (max && l.length >= max) l.shift(); l.push(cod); }
  localStorage.setItem(k, JSON.stringify(l));
  return l.includes(cod);
}
function favHas(cod) { return lsList('biro26_fav').includes(cod); }
function favToggle(btn, cod) {
  const on = lsToggle('biro26_fav', cod);
  btn.classList.toggle('on', on); btn.textContent = on ? '❤' : '♡';
  toast(on ? '❤ ' + tr('favAdded') : tr('favRemoved'));
}
function cmpHas(cod) { return lsList('biro26_cmp').includes(cod); }
function cmpToggle(cod) {
  const on = lsToggle('biro26_cmp', cod, 4);
  toast(on ? '⚖ ' + tr('cmpAdded') : tr('cmpRemoved'));
  return on;
}

/* ── tipurile de plata din WP «site-plati» (footer, toate paginile) ────
   RO: maib cere siglele bancii si ale sistemelor internationale de plata in
   subsolul site-ului. Punem fisierele OFICIALE in /static/biro26/pay/<slug>.svg
   (sau .png); daca un fisier lipseste, <img> cade inapoi pe badge-ul text, deci
   subsolul arata corect si pina la primirea siglelor de la banca.
   EN: maib requires bank + card-scheme logos in the footer; official files go to
   /static/biro26/pay/, and a missing file gracefully falls back to a text badge. */
function paySlug(name) {
  return String(name).toLowerCase()
    .replace(/[ăâ]/g, 'a').replace(/[îi]/g, 'i').replace(/[șş]/g, 's')
    .replace(/[țţ]/g, 't').replace(/[^a-z0-9]/g, '');
}
function payBadgeHtml(name) {
  const slug = paySlug(name);
  if (!slug) return '';
  const alt = esc(name);
  // onerror: fisierul lipseste -> inlocuim <img> cu badge-ul text
  return '<img class="paylogo" src="/static/biro26/pay/' + slug + '.svg" alt="' + alt +
         '" title="' + alt + '" loading="lazy"' +
         ' onerror="this.onerror=null;this.outerHTML=\'<span class=&quot;paybadge&quot;>' +
         alt.replace(/'/g, '') + '</span>\'">';
}
(async function payBadges() {
  const box = document.getElementById('paybadges');
  if (!box) return;
  let html = '';
  try {
    const r = await j('/api/biro26/site/info/site-plati');
    if (r.success) html = r.data.html || '';
  } catch (e) {}

  // RO: daca in pagina WP «site-plati» au fost inserate IMAGINI din galerie,
  //     le folosim ca atare — asa siglele se administreaza din WordPress, fara
  //     deploy. Reconstruim <img>-urile curat (doar src/alt), nu injectam HTML.
  // EN: if the WP page contains gallery images, use them — logos are then
  //     managed from WordPress; the <img> tags are rebuilt from src/alt only.
  let imgs = [];
  try {
    const doc = new DOMParser().parseFromString(html, 'text/html');
    imgs = [...doc.querySelectorAll('img')]
      .map(im => ({src: im.getAttribute('src') || '', alt: im.getAttribute('alt') || ''}))
      .filter(o => /^(https?:)?\/\//.test(o.src) || o.src.startsWith('/'));
  } catch (e) {}
  if (imgs.length) {
    box.innerHTML = imgs.map(o =>
      '<img class="paylogo" src="' + esc(o.src) + '" alt="' + esc(o.alt) +
      '" title="' + esc(o.alt) + '" loading="lazy">').join('');
    return;
  }

  // altfel: denumirile din pagina -> sigle din /static/biro26/pay/ -> badge text
  const names = html.replace(/<[^>]+>/g, ' ')
    .split(',').map(s => s.trim()).filter(Boolean);
  // maib se afiseaza mereu primul — e cerinta bancii, nu optiune editoriala
  if (!names.some(n => paySlug(n) === 'maib')) names.unshift('maib');
  box.innerHTML = names.map(payBadgeHtml).join('');
})();

applyLang(); cartBadge();
