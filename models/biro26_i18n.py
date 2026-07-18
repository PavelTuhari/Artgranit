"""Biro26/OfficePlus — managementul traducerilor grupării catalogului.

RO: Pagina admin «Traduceri» lucrează cu dicționarul YBIRO_GRP_I18N
    (principiul una-shops: traducerile sunt DATE editabile, fallback RO):
    - lista grupelor/categoriilor cu RU/EN editabile;
    - export CSV / import CSV;
    - traducere AUTOMATĂ prin serviciul OCI Multi-Translate
      (POST CSV -> job -> poll progres -> import rezultat).
EN: Admin translations management for the catalog grouping — manual
    editing, CSV export/import and automatic translation through the
    OCI Multi-Translate service.

Serviciu: Config.BIRO26_TRANSLATE_API_URL (+ cheia in .env);
API: POST /v1/translate/jobs (multipart, source_lang=ro, targets=ru,en,
text_col=text; coloanele suplimentare kind/name_ro se pastreaza in
rezultat) -> GET jobs/{id} (progress) -> GET jobs/{id}/result (CSV cu
tr_ru/tr_en). Documentatie: http://130.61.111.57/TRANSLATE_API_FOR_AI.md
"""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List

import requests

from config import Config
from models.biro26_db import Biro26DB
from models.biro26_oracle_store import Biro26Store, _rows


def _api(path: str) -> str:
    return Config.BIRO26_TRANSLATE_API_URL.rstrip("/") + path


def _hdr() -> Dict[str, str]:
    return {"Authorization": f"Bearer {Config.BIRO26_TRANSLATE_API_KEY}"}


class Biro26I18n:

    # ── lista + editare manuala ──

    @staticmethod
    def groups_list() -> Dict[str, Any]:
        """Toate grupele + categoriile cu traducerile curente (daca exista)."""
        try:
            rows = _rows(Biro26DB().execute_query(
                "SELECT x.KIND, x.NAME_RO, i.NAME_RU, i.NAME_EN, x.CNT FROM ("
                "  SELECT 'grupa' KIND, g.GRUPA NAME_RO, COUNT(*) CNT "
                "  FROM BIRO26_GOODS g JOIN TMS_UNIVERS u ON u.COD=g.COD_UNIVERS "
                "  WHERE u.TIP='P' AND g.GRUPA IS NOT NULL GROUP BY g.GRUPA "
                "  UNION ALL "
                "  SELECT 'categorie', g.CATEGORIE, COUNT(*) "
                "  FROM BIRO26_GOODS g JOIN TMS_UNIVERS u ON u.COD=g.COD_UNIVERS "
                "  WHERE u.TIP='P' AND g.CATEGORIE IS NOT NULL GROUP BY g.CATEGORIE"
                ") x LEFT JOIN YBIRO_GRP_I18N i "
                "  ON i.KIND = x.KIND AND i.NAME_RO = x.NAME_RO "
                "ORDER BY DECODE(x.KIND,'grupa',0,1), x.NAME_RO"))
            total = len(rows)
            missing = sum(1 for r in rows
                          if not (r["name_ru"] and r["name_en"]))
            return {"success": True, "data": rows,
                    "total": total, "missing": missing}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @staticmethod
    def save_rows(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """MERGE traducerile editate manual (sau importate)."""
        try:
            db = Biro26DB()
            n = 0
            steps = []
            for r in rows:
                kind = (r.get("kind") or "").strip()
                ro = (r.get("name_ro") or "").strip()
                if kind not in ("grupa", "categorie") or not ro:
                    continue
                steps.append({
                    "sql": "MERGE INTO YBIRO_GRP_I18N t USING "
                           "(SELECT :k KIND, :ro NAME_RO FROM dual) s "
                           "ON (t.KIND = s.KIND AND t.NAME_RO = s.NAME_RO) "
                           "WHEN MATCHED THEN UPDATE SET "
                           "  t.NAME_RU = :ru, t.NAME_EN = :en "
                           "WHEN NOT MATCHED THEN INSERT "
                           "  (KIND, NAME_RO, NAME_RU, NAME_EN) "
                           "  VALUES (:k2, :ro2, :ru2, :en2)",
                    "params": {"k": kind, "ro": ro[:200],
                               "ru": (r.get("name_ru") or "")[:200] or None,
                               "en": (r.get("name_en") or "")[:200] or None,
                               "k2": kind, "ro2": ro[:200],
                               "ru2": (r.get("name_ru") or "")[:200] or None,
                               "en2": (r.get("name_en") or "")[:200] or None},
                    "kind": "dml"})
                n += 1
            if steps:
                res = db.execute_script(steps)
                if not res.get("success"):
                    return {"success": False, "error": res.get("message")}
            return {"success": True, "saved": n}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── export / import CSV ──

    @staticmethod
    def export_csv(only_missing: bool = False) -> str:
        r = Biro26I18n.groups_list()
        buf = io.StringIO()
        w = csv.writer(buf)
        # RO: format compatibil cu serviciul de traducere (text_col=text);
        #     kind/name_ro se pastreaza in rezultat -> import fara stare
        w.writerow(["id", "kind", "name_ro", "text", "name_ru", "name_en"])
        i = 0
        for row in (r.get("data") or []):
            if only_missing and row["name_ru"] and row["name_en"]:
                continue
            i += 1
            w.writerow([i, row["kind"], row["name_ro"], row["name_ro"],
                        row["name_ru"] or "", row["name_en"] or ""])
        return buf.getvalue()

    @staticmethod
    def import_csv(text: str) -> Dict[str, Any]:
        """RO: accepta atat CSV-ul exportat/editat (name_ru/name_en) cat si
        rezultatul serviciului (tr_ru/tr_en). EN: accepts both formats."""
        try:
            rd = csv.DictReader(io.StringIO(text))
            rows = []
            for r in rd:
                ru = (r.get("tr_ru") or r.get("name_ru") or "").strip()
                en = (r.get("tr_en") or r.get("name_en") or "").strip()
                if not (ru or en):
                    continue
                rows.append({"kind": (r.get("kind") or "").strip(),
                             "name_ro": (r.get("name_ro") or r.get("text") or "").strip(),
                             "name_ru": ru, "name_en": en})
            res = Biro26I18n.save_rows(rows)
            res["parsed"] = len(rows)
            return res
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── traducere automata (serviciul OCI Multi-Translate) ──

    @staticmethod
    def auto_start(only_missing: bool = True) -> Dict[str, Any]:
        if not Config.BIRO26_TRANSLATE_API_KEY:
            return {"success": False,
                    "error": "BIRO26_TRANSLATE_API_KEY nesetat in .env"}
        payload = Biro26I18n.export_csv(only_missing=only_missing)
        n = max(0, payload.count("\n") - 1)
        if n == 0:
            return {"success": False, "error": "nimic de tradus — totul e gata"}
        try:
            r = requests.post(
                _api("/v1/translate/jobs"), headers=_hdr(), timeout=60,
                files={"file": ("grupare.csv", payload.encode("utf-8"),
                                "text/csv")},
                data={"source_lang": "ro", "targets": "ru,en",
                      "text_col": "text"})
            b = r.json()
        except Exception as e:
            return {"success": False, "error": f"translate service: {e}"}
        if not b.get("job_id"):
            return {"success": False, "error": str(b)[:300]}
        # RO: retinem ultimul job ca pagina sa poata relua polling-ul
        Biro26Store.set_setting("I18N_LAST_JOB", b["job_id"])
        return {"success": True, "data": {"job_id": b["job_id"], "rows": n}}

    @staticmethod
    def auto_status(job_id: str) -> Dict[str, Any]:
        """Progresul job-ului; la 'completed' importa automat rezultatul."""
        try:
            r = requests.get(_api(f"/v1/translate/jobs/{job_id}"),
                             headers=_hdr(), timeout=30)
            b = r.json()
        except Exception as e:
            return {"success": False, "error": f"translate service: {e}"}
        status = b.get("status")
        out: Dict[str, Any] = {"success": True,
                               "status": status,
                               "progress": b.get("progress") or {},
                               "error": b.get("error")}
        if status == "completed":
            try:
                rr = requests.get(_api(f"/v1/translate/jobs/{job_id}/result"),
                                  headers=_hdr(), timeout=120)
                imp = Biro26I18n.import_csv(rr.text)
                out["imported"] = imp.get("saved")
                out["import_error"] = imp.get("error")
                Biro26Store.set_setting("I18N_LAST_JOB", "")
            except Exception as e:
                out["import_error"] = str(e)
        if status == "failed":
            Biro26Store.set_setting("I18N_LAST_JOB", "")
        return out

    @staticmethod
    def last_job() -> str:
        return Biro26Store.get_setting("I18N_LAST_JOB", "")
