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
};
function curLang() {
  const l = localStorage.getItem('biro26_lang') || 'ro';
  return l === 'ru' ? 'ru' : 'ro';
}
function tr(k) { const e = T[k]; return e ? (e[curLang()] || e.ro) : ''; }
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
function pprice(p) { return parseFloat(String(p.retail1 || '').replace(',', '.')) || 0; }
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
function cardHtml(p) {
  PMAP[p.cod] = p;
  const price = pprice(p);
  const inStock = (p.real_cant || 0) > 0;
  return '<article class="product-card">' +
    '<button class="wish" type="button" aria-label="Favorite">♡</button>' +
    (p.image
      ? '<div class="product-img live" style="background-image:url(\'' + esc(p.image) +
        '\')" onclick="openProd(' + p.cod + ')"></div>'
      : '<div class="product-img p-markers" onclick="openProd(' + p.cod + ')"></div>') +
    '<span class="stock ' + (inStock ? 'in' : 'order') + '">' +
      tr(inStock ? 'inStock' : 'onOrder') + '</span>' +
    '<h3 class="product-name" onclick="openProd(' + p.cod + ')">' + esc(pname(p)) + '</h3>' +
    '<div class="product-prices"><span class="price">' + fmtLei(price) + '</span></div>' +
    liberHtml(price, true) +
    '<button class="btn-buy-sm" type="button" onclick="addToCart(' + p.cod + ',\'' +
      esc(p.denumirea || '').replace(/'/g, '&#39;') + '\',' + price + ')">' +
      tr('buy') + '</button>' +
    '</article>';
}

/* ── header: cautare + newsletter ────────────────────────────────────── */
function goSearch() {
  const q = document.getElementById('q').value.trim();
  if (q) location.href = '/catalog?q=' + encodeURIComponent(q);
  return false;
}
function subscribe() {
  const e = document.getElementById('nl-email').value.trim();
  if (e) {
    try {
      const l = JSON.parse(localStorage.getItem('biro26_newsletter') || '[]');
      if (!l.includes(e)) l.push(e);
      localStorage.setItem('biro26_newsletter', JSON.stringify(l));
    } catch (er) {}
    toast('✉️ ' + tr('subscribed'));
    document.getElementById('nl-email').value = '';
  }
  return false;
}

applyLang(); cartBadge();
