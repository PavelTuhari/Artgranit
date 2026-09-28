"""ServOuts26 module — UNITEST schema access (same Oracle 11g host as OfficePlus).

The target DB (unitest@orange.una.md:4024/cloudbd.world) is Oracle 11g, reachable
only in python-oracledb THICK mode. Thick mode is a whole-process switch that
would break the main Flask app's thin cloud-wallet connection (production
nufarul.eminescu.md), so — exactly like Biro26 — every operation runs in an
isolated subprocess worker (models/biro26_worker.py). ServOuts26DB subclasses
Biro26DB and only injects its own credentials into each worker request.

Method contract (inherited): execute_query / execute_dml / call_proc /
execute_script / test_connection — identical to models.database.DatabaseModel.
"""
from __future__ import annotations

from typing import Any, Dict

from config import Config
from models.biro26_db import Biro26DB


class ServOuts26DB(Biro26DB):
    """Subprocess-backed accessor for the UNITEST schema (Oracle 11g, thick mode)."""

    def _call(self, req: Dict[str, Any]) -> Dict[str, Any]:
        req = dict(req)
        req["nls_date_format"] = "DD.MM.RRRR"
        req["auth"] = {
            "user": Config.SERVOUTS26_DB_USER,
            "password": Config.SERVOUTS26_DB_PASSWORD,
            "dsn": Config.SERVOUTS26_DB_DSN,
        }
        return super()._call(req)
