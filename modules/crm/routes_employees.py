"""Rutele pentru angajati (administrarea conturilor ERP din admin-ul OfficePlus).

RO: fisier separat (regula nr. 2). Doar administratorul OfficePlus: chiriasul
trebuie sa fie `office` — clientul din cabinet nu are ce cauta in conturile
angajatilor firmei.
Parola generata se intoarce O SINGURA DATA, la crearea contului sau la
recuperare; nicaieri nu o pastram si nu o mai putem arata a doua oara.
EN: employee (ERP account) routes, OfficePlus admin only.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable

from flask import g, jsonify, request, session

from modules.crm import blueprint
from modules.crm import employees as R
from modules.crm.routes_process import err
from modules.crm.store_employees import EmployeeStore
from modules.crm import tenant as tenant_mod


def _actor() -> str:
    return str(session.get("user_name") or session.get("username") or "?")[:100]


def office_only(fn: Callable) -> Callable:
    """RO: numai OfficePlus (sesiunea portalului), niciodata un client."""
    @wraps(fn)
    def wrapper(*a, **kw):
        t = tenant_mod.current()
        if t is None:
            return err("login required", 401)
        if not t.is_office:
            return err("doar administratorul OfficePlus", 403)
        g.emp = EmployeeStore()
        try:
            return fn(*a, **kw)
        except ValueError as e:
            return err(str(e), 400, field=str(e).split(":")[0] if ":" in str(e) else "")
        except LookupError as e:
            return err(str(e), 404)
        except RuntimeError as e:
            return err("eroare ERP", 500, detail=str(e)[:400])
    return wrapper


@blueprint.route("/api/v2/employees")
@office_only
def api_employees():
    rows = g.emp.list(q=request.args.get("q", ""), only=request.args.get("only", "all"),
                      sort=request.args.get("sort", "username"))
    return jsonify({"success": True, "data": rows, "summary": R.summary(rows),
                    "groups": g.emp.groups()})


@blueprint.route("/api/v2/employees/<int:obj_id>")
@office_only
def api_employee(obj_id):
    e = g.emp.get(obj_id)
    if not e:
        raise LookupError("angajat inexistent")
    e["events"] = g.emp.events(20, obj_id)
    return jsonify({"success": True, "data": e})


@blueprint.route("/api/v2/employees", methods=["POST"])
@office_only
def api_employee_create():
    """RO: inregistrarea angajatului. Parola se intoarce o singura data."""
    b = request.get_json(silent=True) or {}
    if not b.get("group_id"):
        raise ValueError("group_id: alegeti grupa de utilizatori")
    r = g.emp.create(username=b.get("username") or "", group_id=int(b["group_id"]),
                     full_name=b.get("full_name") or "", email=b.get("email") or "",
                     phone=b.get("phone") or "", password=b.get("password") or "",
                     is_admin=bool(b.get("is_admin")), actor=_actor())
    return jsonify({"success": True, "data": r["employee"], "password": r["password"]}), 201


@blueprint.route("/api/v2/employees/<int:obj_id>", methods=["PUT"])
@office_only
def api_employee_update(obj_id):
    return jsonify({"success": True, "data": g.emp.update_card(
        obj_id, request.get_json(silent=True) or {}, actor=_actor())})


@blueprint.route("/api/v2/employees/<int:obj_id>/enabled", methods=["POST"])
@office_only
def api_employee_enabled(obj_id):
    b = request.get_json(silent=True) or {}
    return jsonify({"success": True, "data": g.emp.set_enabled(
        obj_id, bool(b.get("enabled")), actor=_actor())})


@blueprint.route("/api/v2/employees/<int:obj_id>/password", methods=["POST"])
@office_only
def api_employee_password(obj_id):
    """RO: parola standard noua (recuperare). Se arata o singura data."""
    b = request.get_json(silent=True) or {}
    r = g.emp.set_password(obj_id, password=b.get("password") or "", actor=_actor())
    return jsonify({"success": True, "data": r["employee"], "password": r["password"]})


@blueprint.route("/api/v2/employees/<int:obj_id>/check", methods=["POST"])
@office_only
def api_employee_check(obj_id):
    """RO: «Verifica parola» — chiar apelul pe care il face UniacCLNT la intrare."""
    e = g.emp.get(obj_id)
    if not e:
        raise LookupError("angajat inexistent")
    b = request.get_json(silent=True) or {}
    return jsonify({"success": True, "data": g.emp.check_login(e["username"], b.get("password") or "")})


@blueprint.route("/api/v2/employees/sync", methods=["POST"])
@office_only
def api_employees_sync():
    """RO: aduce utilizatorii aparuti sau schimbati direct din uniConf."""
    return jsonify({"success": True, "data": g.emp.sync(actor=_actor())})


@blueprint.route("/api/v2/employees/events")
@office_only
def api_employees_events():
    return jsonify({"success": True, "data": g.emp.events(request.args.get("limit", 50, type=int))})
