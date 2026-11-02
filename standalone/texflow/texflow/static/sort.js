// TexFlow — быстрый разбор мешка: сканер, матрица цвет × размер, поиск модели.
(function () {
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));
  const scan = document.getElementById("scan"), slog = document.getElementById("scanlog");
  if (scan) scan.addEventListener("keydown", async (e) => {
    if (e.key !== "Enter" || !scan.value.trim()) return;
    e.preventDefault();
    const code = scan.value.trim(); scan.value = "";
    try {
      const r = await fetch(SCAN_URL, {method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({code, bag_id: BAG, qty: 1})});
      const j = await r.json();
      slog.innerHTML = (j.success ? "✓ " + esc(j.sku) + " — " + esc(j.name) : "✗ " + esc(j.error)) + "<br>" + slog.innerHTML;
      try { new AudioContext().resume(); } catch (_) {}
    } catch (err) { slog.textContent = (window.TF_I18N || {})["ошибка сети"] + ": " + err; }
  });

  const body = document.getElementById("mbody"), tpl = document.getElementById("rowtpl");
  function recalc() {
    if (!body) return;
    let total = 0; const cols = {};
    body.querySelectorAll("tr").forEach((tr) => {
      let s = 0;
      tr.querySelectorAll("input").forEach((i) => {
        const v = parseInt(i.value, 10) || 0; s += v;
        const sid = i.name.split("_")[2]; cols[sid] = (cols[sid] || 0) + v;
      });
      tr.querySelector(".sum").textContent = s; total += s;
    });
    document.querySelectorAll(".csum").forEach((th) => th.textContent = cols[th.dataset.s] || 0);
    const t = document.getElementById("tsum"); if (t) t.textContent = total;
  }
  function inputs() { return body ? Array.from(body.querySelectorAll("input")) : []; }
  function cols() { const tr = body && body.querySelector("tr"); return tr ? tr.querySelectorAll("input").length : 1; }
  if (body) {
    body.addEventListener("input", recalc);
    body.addEventListener("keydown", (e) => {
      const all = inputs(), i = all.indexOf(e.target); if (i < 0) return;
      const n = cols(); let j = null;
      if (e.key === "Enter" && !e.ctrlKey) j = i + 1;
      else if (e.key === "ArrowRight") j = i + 1; else if (e.key === "ArrowLeft") j = i - 1;
      else if (e.key === "ArrowDown") j = i + n; else if (e.key === "ArrowUp") j = i - n;
      if (j !== null) { e.preventDefault(); if (all[j]) { all[j].focus(); all[j].select(); } }
    });
    document.querySelectorAll(".colorpick").forEach((ch) => {
      if (body.querySelector(`tr[data-color="${ch.dataset.id}"]`)) ch.classList.add("on");
      ch.addEventListener("click", () => {
        const ex = body.querySelector(`tr[data-color="${ch.dataset.id}"]`);
        if (ex) { ex.querySelector("input").focus(); return; }
        const html = tpl.innerHTML.replaceAll("__C__", ch.dataset.id).replaceAll("__H__", esc(ch.dataset.hex))
          .replaceAll("__N__", esc(ch.dataset.name));
        body.insertAdjacentHTML("beforeend", html); ch.classList.add("on");
        body.lastElementChild.querySelector("input").focus();
      });
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && e.ctrlKey) document.getElementById("mform").submit();
    });
  }

  const ps = document.getElementById("psearch"), pr = document.getElementById("presults");
  let t = null;
  if (ps) ps.addEventListener("input", () => {
    clearTimeout(t);
    t = setTimeout(async () => {
      const r = await fetch(API + "?q=" + encodeURIComponent(ps.value)); const list = await r.json();
      pr.innerHTML = list.map((p) => `<a class="chip" href="${SORT}?bag=${BAG}&product=${p.id}">${esc(p.style_code)} · ${esc(p.name)} (${p.stock})</a>`).join("");
    }, 200);
  });
})();
