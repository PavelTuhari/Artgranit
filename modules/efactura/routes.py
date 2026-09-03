"""Rutele modulului e-Factura — trei intrari, o singura logica.

RO: adresele sint FARA prefix (nucleul monteaza totul sub
/UNA.md/orasldev/efactura). Cele trei intrari se deosebesc DOAR prin cine are
voie sa le cheme:

  * `/admin/...`  — operatorul portalului (sesiunea de back-office);
  * `/my/...`     — clientul din cabinetul site-ului, DOAR documentele lui;
  * `/api/...`    — masina-la-masina prin X-API-Key (back-office nativ),
                    acelasi antet ca la restul API-ului Biro26.

EN: three entry points, one implementation; they differ only in who may call.
"""
from __future__ import annotations

from flask import jsonify, redirect, render_template, request

from controllers.auth_controller import AuthController
from controllers.biro26_controller import Biro26Controller

from modules.efactura import blueprint
from modules.efactura.controller import EfaController
from modules.efactura.store import EfaStore


def _body():
    return request.get_json(silent=True) or {}


def _reply(r, ok=200, bad=400):
    return jsonify(r), (ok if r.get("success") else bad)


# ── 1. BACK-OFFICE (sesiunea portalului) ───────────────────────────────
def _admin_guard():
    if AuthController.is_authenticated():
        return None
    return jsonify({"success": False, "error": "login required"}), 401


@blueprint.route("/")
def admin_page():
    if not AuthController.is_authenticated():
        return redirect("/login?next=/UNA.md/orasldev/efactura/")
    from modules.efactura import sfs
    return render_template("efactura_admin.html",
                           endpoint_test=sfs.ENDPOINT_TEST,
                           endpoint_prod=sfs.ENDPOINT_PROD)


@blueprint.route("/admin/settings", methods=["GET", "POST"])
def admin_settings():
    err = _admin_guard()
    if err:
        return err
    if request.method == "POST":
        return _reply(EfaStore.set_settings(_body()))
    return jsonify({"success": True, "data": EfaStore.settings_public()})


@blueprint.route("/admin/test", methods=["POST"])
def admin_test():
    err = _admin_guard()
    if err:
        return err
    # RO: verdict pe fiecare semnatar + indiciu «cont pe alt mediu» —
    #     vezi modules/efactura/conncheck.py (03.09.2026).
    from modules.efactura import conncheck
    r = conncheck.check("backoffice")
    EfaStore.log(None, "test", str({k: v for k, v in r.items()
                                    if k != "signers"})[:600], "backoffice")
    return _reply(r, bad=502)


@blueprint.route("/admin/docs")
def admin_docs():
    err = _admin_guard()
    if err:
        return err
    return jsonify(EfaStore.doc_list(request.args.get("status", ""),
                                     request.args.get("limit", 100, type=int)))


@blueprint.route("/admin/log")
def admin_log():
    err = _admin_guard()
    if err:
        return err
    return jsonify(EfaStore.log_list(request.args.get("limit", 200, type=int)))


# ── raportul «facturi transmise» (pachetul EFA_REPORT, 3 seturi) ────────
@blueprint.route("/report")
def report_page():
    if not AuthController.is_authenticated():
        return redirect("/login?next=/UNA.md/orasldev/efactura/report")
    from modules.efactura.report import STATUSES
    return render_template("efactura_report.html", statuses=STATUSES)


def _report_data():
    from modules.efactura import report
    filters = report.parse_filters(request.args)
    return report.fetch(filters)


@blueprint.route("/admin/report")
def admin_report():
    err = _admin_guard()
    if err:
        return err
    try:
        return jsonify(_report_data())
    except Exception as e:                                   # noqa: BLE001
        return jsonify({"success": False, "error": str(e)}), 400


@blueprint.route("/admin/report.xlsx")
def admin_report_xlsx():
    err = _admin_guard()
    if err:
        return err
    from flask import Response
    from modules.efactura import report
    try:
        data = _report_data()
    except Exception as e:                                   # noqa: BLE001
        return jsonify({"success": False, "error": str(e)}), 400
    return Response(report.to_xlsx(data),
                    mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=%s"
                             % report.file_name(data["filters"], "xlsx")})


@blueprint.route("/admin/report.pdf")
def admin_report_pdf():
    err = _admin_guard()
    if err:
        return err
    from flask import Response
    from modules.efactura import report
    try:
        data = _report_data()
    except Exception as e:                                   # noqa: BLE001
        return jsonify({"success": False, "error": str(e)}), 400
    return Response(report.to_pdf(data), mimetype="application/pdf",
                    headers={"Content-Disposition": "inline; filename=%s"
                             % report.file_name(data["filters"], "pdf")})


@blueprint.route("/admin/calls")
def admin_calls():
    """RO: TOATE comunicarile cu SFS — reusite si esuate — cu plicul trimis
    (parola mascata) si raspunsul intors (03.09.2026, cerinta proprietarului)."""
    err = _admin_guard()
    if err:
        return err
    from modules.efactura import journal
    try:
        rows = journal.recent(request.args.get("limit", 100, type=int))
    except Exception as e:                                   # noqa: BLE001
        return jsonify({"success": False, "error": str(e)}), 500
    return jsonify({"success": True, "data": rows})


@blueprint.route("/admin/calls/<int:call_id>")
def admin_call(call_id):
    err = _admin_guard()
    if err:
        return err
    from modules.efactura import journal
    row = journal.get(call_id)
    if not row:
        return jsonify({"success": False, "error": "apel inexistent"}), 404
    return jsonify({"success": True, "data": row})


@blueprint.route("/admin/send/<int:doc_cod>", methods=["POST"])
def admin_send(doc_cod):
    err = _admin_guard()
    if err:
        return err
    return _reply(EfaController.send(doc_cod, src="backoffice",
                                     resend=bool(_body().get("resend"))))


@blueprint.route("/admin/preview/<int:doc_cod>")
def admin_preview(doc_cod):
    err = _admin_guard()
    if err:
        return err
    return _reply(EfaController.preview_xml(doc_cod))


@blueprint.route("/admin/refresh", methods=["POST"])
def admin_refresh():
    err = _admin_guard()
    if err:
        return err
    return _reply(EfaController.refresh_statuses(
        _body().get("days", 7)), bad=502)


# ── 2. CABINETUL CLIENTULUI (site) ─────────────────────────────────────
def _client_cod():
    """RO: clientul logat pe site; None daca nu e autentificat."""
    from flask import session
    c = session.get("biro26_client")
    return int(c["univers_cod"]) if c else None


@blueprint.route("/my/status/<int:doc_cod>")
def my_status(doc_cod):
    cc = _client_cod()
    if cc is None:
        return jsonify({"success": False, "error": "login required"}), 401
    return _reply(EfaController.status(doc_cod, allowed_client_cod=cc),
                  bad=403)


@blueprint.route("/my/send/<int:doc_cod>", methods=["POST"])
def my_send(doc_cod):
    """RO: clientul cere factura fiscala electronica pentru comanda LUI —
    aceeasi logica, dar limitata la documentele proprii."""
    cc = _client_cod()
    if cc is None:
        return jsonify({"success": False, "error": "login required"}), 401
    return _reply(EfaController.send(doc_cod, src="cabinet",
                                     allowed_client_cod=cc), bad=403)


@blueprint.route("/my/preview/<int:doc_cod>")
def my_preview(doc_cod):
    cc = _client_cod()
    if cc is None:
        return jsonify({"success": False, "error": "login required"}), 401
    return _reply(EfaController.preview_xml(doc_cod, allowed_client_cod=cc),
                  bad=403)


# ── 3. API INTERN (X-API-Key) pentru back-office-uri native ────────────
def _api_guard():
    """RO: acelasi mecanism ca la restul API-ului Biro26 (X-API-Key sau
    ?api_key=), ca aplicatiile native sa nu invete inca un tip de acces."""
    if Biro26Controller._api_token_ok():
        return None
    return jsonify({"success": False, "error": "invalid api key"}), 401


@blueprint.route("/api/send/<int:doc_cod>", methods=["POST"])
def api_send(doc_cod):
    """RO: corpul JSON optional: {"override_date": "YYYY-MM-DD"} — DOAR pentru
    probe pe mediul de test cu documente vechi (SFS primeste facturi doar cu
    data de azi…azi+10). In productie nu se trimite."""
    err = _api_guard()
    if err:
        return err
    body = _body()
    return _reply(EfaController.send(doc_cod, src="api",
                                     override_date=body.get("override_date")))


@blueprint.route("/api/status/<int:doc_cod>")
def api_status(doc_cod):
    err = _api_guard()
    if err:
        return err
    return _reply(EfaController.status(doc_cod))


@blueprint.route("/api/preview/<int:doc_cod>")
def api_preview(doc_cod):
    err = _api_guard()
    if err:
        return err
    return _reply(EfaController.preview_xml(doc_cod))


@blueprint.route("/api/docs")
def api_docs():
    err = _api_guard()
    if err:
        return err
    return jsonify(EfaStore.doc_list(request.args.get("status", ""),
                                     request.args.get("limit", 100, type=int)))


@blueprint.route("/api/health")
def api_health():
    err = _api_guard()
    if err:
        return err
    s = EfaStore.settings_public()
    return jsonify({"success": True, "data": {
        "configured": s.get("configured"), "mode": s.get("mode"),
        "endpoint_set": bool(s.get("endpoint"))}})


# ── 4. FACTURA DE TEST — mini-modul universal ─────────────────────────
# RO: pagina si API-ul probei. Sint deschise si operatorului portalului, si
#     (prin X-API-Key) altor aplicatii; orice modul al platformei poate pune
#     butonul cu o singura linie — vezi /widget.js.
@blueprint.route("/test")
def test_page():
    if not AuthController.is_authenticated():
        return redirect("/login?next=/UNA.md/orasldev/efactura/test")
    # RO: pagina probei NU citeste setarile e-Factura ale magazinului —
    #     contul API il scrie directorul aici, iar adresa implicita e mediul
    #     de proba al SFS. Asa proba merge la fel din orice modul.
    from modules.efactura import sfs
    from modules.efactura.testff import MAX_LINES, MAX_TOTAL, MIN_TOTAL
    return render_template("efactura_test.html", min_total=MIN_TOTAL,
                           max_total=MAX_TOTAL, max_lines=MAX_LINES,
                           test_endpoint=sfs.TEST_ENDPOINT,
                           endpoint_test=sfs.ENDPOINT_TEST,
                           endpoint_prod=sfs.ENDPOINT_PROD)


def _test_guard():
    """RO: proba o poate face operatorul logat SAU o aplicatie cu cheie."""
    if AuthController.is_authenticated() or Biro26Controller._api_token_ok():
        return None
    return jsonify({"success": False, "error": "login or api key required"}), 401


@blueprint.route("/test/preview", methods=["POST"])
def test_preview():
    err = _test_guard()
    if err:
        return err
    from modules.efactura import testff
    return _reply(testff.preview(_body()))


@blueprint.route("/test/send", methods=["POST"])
def test_send():
    err = _test_guard()
    if err:
        return err
    from modules.efactura import testff
    src = "api" if not AuthController.is_authenticated() else "test-page"
    return _reply(testff.send(_body(), src=src))


@blueprint.route("/test/queues", methods=["GET", "POST"])
def test_queues():
    err = _test_guard()
    if err:
        return err
    from modules.efactura import testff
    return _reply(testff.signing_queues(_body().get("api")))


@blueprint.route("/test/log")
def test_log():
    """RO: jurnalul apelurilor paginii de proba — ce s-a trimis, ce a raspuns
    SFS, cit a durat. Parola nu e in jurnal (mascata la scriere)."""
    err = _test_guard()
    if err:
        return err
    from modules.efactura import journal
    try:
        rows = journal.recent(int(request.args.get("limit", 40)), src="test-page")
    except Exception as e:                                   # noqa: BLE001
        return jsonify({"success": False, "error": str(e)[:300]}), 500
    return jsonify({"success": True, "data": rows})


@blueprint.route("/test/ping", methods=["POST"])
def test_ping():
    """RO: verifica contul API scris in formular — nu trimite nimic in SFS.

    Credentialele venite aici se folosesc pentru ACEST apel si atit: nu se
    salveaza nicaieri, nu intra in jurnal.
    """
    err = _test_guard()
    if err:
        return err
    from modules.efactura import testff
    return _reply(testff.ping(_body().get("api")))


@blueprint.route("/widget.js")
def widget_js():
    """RO: butonul «Factura de test» pentru ORICE modul al platformei.

    Activarea intr-un modul strain e o singura linie in sablonul lui:
        <script src="/UNA.md/orasldev/efactura/widget.js"></script>
    Scriptul pune butonul in coltul din dreapta-jos si deschide pagina probei
    intr-o fereastra separata. Nu cere nimic de la modulul-gazda: nici stiluri,
    nici biblioteci, nici modificari in codul lui.
    EN: one-line drop-in button for any module on the platform.
    """
    # RO: textul butonului cu diacritice — direct, fara secvente \uXXXX
    #     (intr-un literal Python obisnuit ele s-ar interpreta ca escape-uri)
    js = r"""(function () {
  // butonul nu se pune de doua ori si nu apare pe pagina probei
  if (window.__efaWidget || location.pathname.indexOf('/efactura/test') > -1) return;
  window.__efaWidget = true;
  var base = '/UNA.md/orasldev/efactura';
  function make() {
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = 'FACTURA_LABEL';
    b.title = 'Emite o factura fiscala de proba (max 10 lei)';
    b.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:9998;' +
      'background:#194681;color:#fff;border:0;border-radius:999px;' +
      'padding:10px 18px;font:600 13px/1.2 Inter,system-ui,sans-serif;' +
      'box-shadow:0 6px 18px rgba(0,0,0,.22);cursor:pointer';
    b.onmouseover = function () { b.style.background = '#0f3460'; };
    b.onmouseout = function () { b.style.background = '#194681'; };
    b.onclick = function () {
      window.open(base + '/test', 'efactura_test',
                  'width=980,height=880,scrollbars=yes');
    };
    document.body.appendChild(b);
  }
  if (document.readyState === 'loading')
    document.addEventListener('DOMContentLoaded', make);
  else make();
})();""".replace("FACTURA_LABEL", "\U0001F9FE Factur\u0103 de test")
    from flask import Response
    return Response(js, mimetype="application/javascript",
                    headers={"Cache-Control": "public, max-age=300"})
