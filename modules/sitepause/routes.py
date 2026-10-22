"""RO: hook-ul pauzei (pe toata aplicatia) + comutatorul din backoffice."""
from flask import jsonify, redirect, render_template, request

from config import Config
from controllers.auth_controller import AuthController
from modules.sitepause import blueprint, rules, store


@blueprint.before_app_request
def _site_pause():
    try:
        if not rules.is_shop_host(request.host, Config.BIRO26_SHOP_HOSTS):
            return None                        # nufarul & co.: niciodata
        if not rules.path_is_paused(request.path):
            return None
        st = store.state()
        if not st.get("on"):
            return None
        if AuthController.is_authenticated():
            return None                        # personalul vede magazinul ca sa-l verifice
    except Exception:                                        # noqa: BLE001
        return None                            # nicio eroare a pauzei nu opreste site-ul
    headers = {"Retry-After": "3600", "Cache-Control": "no-store",
               "X-Robots-Tag": "noindex"}
    if rules.wants_json(request.path):
        return jsonify({"success": False, "maintenance": True,
                        "message": "Se efectuează lucrări tehnice. Reveniți mai tîrziu."}), 503, headers
    return render_template("sitepause/pause.html", msg_ro=st.get("ro") or "",
                           msg_ru=st.get("ru") or ""), 503, headers


@blueprint.route("")
@blueprint.route("/")
def admin():
    if not AuthController.is_authenticated():
        return redirect("/login?next=/UNA.md/orasldev/sitepause/")
    return render_template("sitepause/admin.html", st=store.state(),
                           hosts=", ".join(Config.BIRO26_SHOP_HOSTS))


@blueprint.route("/toggle", methods=["POST"])
def toggle():
    if not AuthController.is_authenticated():
        return jsonify({"success": False, "message": "Требуется вход в систему"}), 401
    d = request.get_json(silent=True) or request.form
    on = rules.flag_on(d.get("on"))
    r = store.set_pause(on, d.get("msg_ro"), d.get("msg_ru"))
    if request.is_json:
        return jsonify(r), (200 if r.get("success") else 500)
    return redirect("/UNA.md/orasldev/sitepause/")


# ── WordPress (wp-login.php, /wp-admin/) pe pauza — 22.10.2026 ─────────────
# RO: WordPress-ul officeplus.md ruleaza pe 92.5.130.1, in afara Flask; nginx-ul de
#     acolo intreaba aceasta adresa la fiecare cerere spre wp-login.php si /wp-admin/
#     (auth_request, deploy/officeplus/wp-pause.inc). 204 = deschis, 403 = pauza ->
#     nginx arata pagina de mai jos cu 503. Acelasi parametru SITE_PAUSE ca vitrina:
#     un singur comutator pentru tot punctul de intrare officeplus.md.
#     Cererea vine de la nginx local, fara host-ul magazinului — de aceea nu se
#     verifica domeniul aici. EN: nginx auth_request gate for the WordPress admin.

@blueprint.route("/gate")
def wp_gate():
    try:
        on = bool(store.state().get("on"))
    except Exception:                                        # noqa: BLE001
        on = False                            # eroarea pauzei nu inchide nimic
    return ("", 403 if on else 204, {"Cache-Control": "no-store"})


@blueprint.route("/page")
def wp_pause_page():
    st = store.state()
    return render_template("sitepause/pause.html", msg_ro=st.get("ro") or "",
                           msg_ru=st.get("ru") or ""), 503, {
        "Retry-After": "3600", "Cache-Control": "no-store", "X-Robots-Tag": "noindex"}
