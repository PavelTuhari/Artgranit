"""Biro26 — documentele PERSONALE ale clientului (TMS_MUNC_ADDFILES).

RO: clientul incarca in cabinetul sau copiile actelor (buletin fata/verso
    si alte documente cerute de creditor). Fisierele se pastreaza in Oracle,
    1:N fata de TMS_UNIVERS (unde ajung TOTI clientii — fizice si juridice),
    si pleaca mai departe catre creditor: la Microinvest nu exista API, deci
    cererea o depune operatorul, cu copiile actelor atasate la notificare.

    Date cu caracter PERSONAL (Legea 133/2011 / GDPR):
      * acces: clientul — doar la ale sale; operatorul back-office — la toate;
      * fiecare incarcare / vizualizare / stergere / trimitere se scrie in
        TMS_MUNC_ADDFILES_LOG (cine, cind, de la ce IP);
      * stergerea este FIZICA (dreptul la stergere), nu un marcaj;
      * se accepta doar imagini si PDF, maximum MAX_BYTES per fisier.

EN: the client's personal documents (ID scans) stored in Oracle, 1:N to
    TMS_UNIVERS, with an access journal and hard delete for GDPR.
"""
from __future__ import annotations

import base64
import hashlib
from typing import Any, Dict, List, Optional

from models.biro26_db import Biro26DB
from models.biro26_oracle_store import _result, _rows

# RO/EN: tipurile de documente acceptate in cabinet
DOC_KINDS = {
    "buletin_fata":  "Buletin de identitate — față",
    "buletin_verso": "Buletin de identitate — verso",
    "extras_venit":  "Confirmare venit / extras",
    "other":         "Alt document",
}
MAX_BYTES = 8 * 1024 * 1024          # 8 MB / fisier
ALLOWED_MIME = {"image/jpeg", "image/jpg", "image/png", "application/pdf"}
ALLOWED_EXT = {"jpg", "jpeg", "png", "pdf"}


class Biro26ClientFiles:

    # ── jurnal de acces (GDPR) ───────────────────────────────────────────

    @staticmethod
    def log(action: str, file_id: Optional[int], who: str,
            ip: str = "", note: str = "") -> None:
        try:
            Biro26DB().execute_dml(
                "INSERT INTO TMS_MUNC_ADDFILES_LOG "
                "(ID, FILE_ID, ACTION, WHO, IP_ADDR, NOTE) VALUES "
                "(TMS_MUNC_ADDFILES_LOG_SEQ.NEXTVAL, :f, :a, :w, :ip, :n)",
                {"f": int(file_id) if file_id else None, "a": (action or "")[:20],
                 "w": (who or "")[:100], "ip": (ip or "")[:45],
                 "n": (note or "")[:400]})
        except Exception:                                   # noqa: BLE001
            pass          # RO/EN: jurnalul nu trebuie sa blocheze operatia

    # ── incarcare ────────────────────────────────────────────────────────

    @staticmethod
    def add(univers_cod: int, doc_kind: str, file_name: str, content: bytes,
            mime: str = "", who: str = "client", ip: str = "",
            note: str = "") -> Dict[str, Any]:
        """RO: pastreaza un document al clientului. Acelasi TIP de document
        se INLOCUIESTE (o singura fata si un singur verso), restul se adauga."""
        kind = (doc_kind or "other").strip().lower()
        if kind not in DOC_KINDS:
            return {"success": False, "error": "tip de document necunoscut"}
        if not content:
            return {"success": False, "error": "fișier gol"}
        if len(content) > MAX_BYTES:
            return {"success": False,
                    "error": f"fișier prea mare (max {MAX_BYTES // 1024 // 1024} MB)"}
        ext = (file_name or "").rsplit(".", 1)[-1].lower()
        m = (mime or "").split(";")[0].strip().lower()
        if ext not in ALLOWED_EXT and m not in ALLOWED_MIME:
            return {"success": False,
                    "error": "se acceptă doar JPG, PNG sau PDF"}
        sha = hashlib.sha256(content).hexdigest()
        blob = {"__b64__": base64.b64encode(content).decode()}
        params = {"u": int(univers_cod), "k": kind,
                  "f": (file_name or f"{kind}.{ext or 'jpg'}")[:260],
                  "m": (m or "application/octet-stream")[:100],
                  "s": len(content), "h": sha, "b": blob,
                  "w": (who or "client")[:100], "n": (note or "")[:400]}
        try:
            res = Biro26DB().execute_script([
                # RO/EN: un singur fisier per (client, tip) pentru buletin
                {"sql": "DELETE FROM TMS_MUNC_ADDFILES "
                        "WHERE UNIVERS_COD = :u AND DOC_KIND = :k "
                        "  AND :k IN ('buletin_fata','buletin_verso')",
                 "params": {"u": int(univers_cod), "k": kind}, "kind": "dml"},
                {"sql": "INSERT INTO TMS_MUNC_ADDFILES "
                        "(ID, UNIVERS_COD, DOC_KIND, FILE_NAME, MIME_TYPE, "
                        " FILE_SIZE, SHA256, CONTENT, UPLOADED_BY, NOTE) VALUES "
                        "(TMS_MUNC_ADDFILES_SEQ.NEXTVAL, :u, :k, :f, :m, "
                        " :s, :h, :b, :w, :n)",
                 "params": params, "kind": "dml"},
                {"sql": "SELECT MAX(ID) ID FROM TMS_MUNC_ADDFILES "
                        "WHERE UNIVERS_COD = :u AND DOC_KIND = :k",
                 "params": {"u": int(univers_cod), "k": kind}, "kind": "query"},
            ])
            if not res.get("success"):
                return {"success": False, "error": res.get("message")}
            fid = res["results"][-1]["data"][0][0]
            Biro26ClientFiles.log("upload", fid, who, ip,
                                  f"{DOC_KINDS[kind]} · {len(content)} b")
            return {"success": True, "data": {"id": fid, "kind": kind,
                                              "size": len(content)}}
        except Exception as e:                              # noqa: BLE001
            return {"success": False, "error": str(e)}

    # ── citire ───────────────────────────────────────────────────────────

    @staticmethod
    def list(univers_cod: int) -> Dict[str, Any]:
        """RO: lista documentelor clientului (FARA continut)."""
        try:
            rows = _rows(Biro26DB().execute_query(
                "SELECT ID, DOC_KIND, FILE_NAME, MIME_TYPE, FILE_SIZE, "
                "UPLOADED_BY, TO_CHAR(CREATED_AT,'DD.MM.YYYY HH24:MI') CREATED "
                "FROM TMS_MUNC_ADDFILES WHERE UNIVERS_COD = :u "
                "ORDER BY DOC_KIND, ID", {"u": int(univers_cod)}))
            for r in rows:
                r["kind_label"] = DOC_KINDS.get(r.get("doc_kind"), r.get("doc_kind"))
            return {"success": True, "data": rows}
        except Exception as e:                              # noqa: BLE001
            return {"success": False, "error": str(e)}

    @staticmethod
    def get(file_id: int, univers_cod: Optional[int] = None,
            who: str = "", ip: str = "") -> Dict[str, Any]:
        """RO: continutul unui document. `univers_cod` != None limiteaza
        accesul la documentele ACELUI client (paza pentru cabinet)."""
        try:
            w = "WHERE ID = :i"
            p: Dict[str, Any] = {"i": int(file_id)}
            if univers_cod is not None:
                w += " AND UNIVERS_COD = :u"
                p["u"] = int(univers_cod)
            rows = _rows(Biro26DB().execute_query(
                f"SELECT ID, UNIVERS_COD, DOC_KIND, FILE_NAME, MIME_TYPE, "
                f"CONTENT FROM TMS_MUNC_ADDFILES {w}", p))
            if not rows:
                return {"success": False, "error": "document inexistent"}
            r = rows[0]
            raw = r.get("content")
            # RO/EN: continut binar — vine ca {"__b64__": ...} de la worker
            if isinstance(raw, dict) and "__b64__" in raw:
                raw = base64.b64decode(raw["__b64__"])
            elif isinstance(raw, str):
                raw = raw.encode("utf-8")
            Biro26ClientFiles.log("download", int(file_id), who, ip,
                                  r.get("file_name") or "")
            return {"success": True, "data": {
                "id": r["id"], "univers_cod": r["univers_cod"],
                "kind": r["doc_kind"], "file_name": r["file_name"],
                "mime": r.get("mime_type") or "application/octet-stream",
                "content": raw or b""}}
        except Exception as e:                              # noqa: BLE001
            return {"success": False, "error": str(e)}

    @staticmethod
    def delete(file_id: int, univers_cod: Optional[int] = None,
               who: str = "", ip: str = "") -> Dict[str, Any]:
        """RO: stergere FIZICA (dreptul la stergere al persoanei vizate)."""
        try:
            w = "WHERE ID = :i"
            p: Dict[str, Any] = {"i": int(file_id)}
            if univers_cod is not None:
                w += " AND UNIVERS_COD = :u"
                p["u"] = int(univers_cod)
            r = Biro26DB().execute_dml(
                f"DELETE FROM TMS_MUNC_ADDFILES {w}", p)
            if not r.get("success"):
                return {"success": False, "error": r.get("message")}
            Biro26ClientFiles.log("delete", int(file_id), who, ip)
            return {"success": True, "data": {"deleted": r.get("rowcount", 0)}}
        except Exception as e:                              # noqa: BLE001
            return {"success": False, "error": str(e)}

    # ── pentru creditor: pachetul de acte al clientului ──────────────────

    @staticmethod
    def bundle(univers_cod: int, kinds: Optional[List[str]] = None,
               who: str = "", ip: str = "") -> List[Dict[str, Any]]:
        """RO: documentele clientului ca atasamente (nume + octeti), pentru
        notificarea catre operator si transmiterea mai departe la creditor."""
        out: List[Dict[str, Any]] = []
        lst = Biro26ClientFiles.list(univers_cod)
        for f in (lst.get("data") or []):
            if kinds and f.get("doc_kind") not in kinds:
                continue
            g = Biro26ClientFiles.get(f["id"], univers_cod, who=who, ip=ip)
            if g.get("success") and g["data"]["content"]:
                out.append({"id": g["data"]["id"],
                            "name": g["data"]["file_name"],
                            "mime": g["data"]["mime"],
                            "content": g["data"]["content"],
                            "kind": g["data"]["kind"]})
        if out:
            Biro26ClientFiles.log("send", None, who, ip,
                                  f"pachet {len(out)} fișiere · client {univers_cod}")
        return out
