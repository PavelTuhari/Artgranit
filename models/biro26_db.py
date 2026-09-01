"""Biro26 module — OfficePlus ERP access from the main (thin-mode) Flask app.

The OfficePlus ERP is Oracle 11g and needs python-oracledb THICK mode, which is a
whole-process switch that would break the main app's thin cloud-wallet connection
(production nufarul.eminescu.md). So Biro26DB does NOT connect in-process: it spawns
an isolated thick-mode subprocess worker (models/biro26_worker.py) per operation and
exchanges JSON over stdin/stdout. The main process never enables thick mode.

Method contract mirrors models.database.DatabaseModel so the store/controller layers
are identical to other modules:
    execute_query -> {success, data, columns, rowcount, message}
    execute_dml   -> {success, rowcount, message}
    call_proc     -> {success, output_lines, message}
    execute_script-> {success, results, message}   (multiple statements, one tx)
    test_connection -> {success, version, error}

Usable as a context manager for parity with DatabaseModel (`with Biro26DB() as db:`).
Transport: a small pool of LONG-LIVED --serve workers (spawning a process per
call cost ~1.5s and was the storefront's main slowness). Each call still gets
its own Oracle connection and transaction, so session state never leaks between
calls. BIRO26_WORKER_POOL=0 restores the old process-per-call transport.
"""
from __future__ import annotations

import json
import os
import queue
import select
import subprocess
import sys
import threading
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKER = os.path.join(_PROJECT_ROOT, "models", "biro26_worker.py")
_TIMEOUT = int(os.environ.get("BIRO26_WORKER_TIMEOUT", "300"))

# RO: BAZINUL de procese-lucrator DE LUNGA DURATA. Pornirea unui proces nou la
#     fiecare interogare costa ~1,5 s (Python + thick-client) si din asta se
#     compunea toata incetineala vitrinei. Procesul din bazin traieste si
#     raspunde pe rand la cereri; fiecare cerere isi deschide totusi PROPRIA
#     conexiune Oracle, deci starea de sesiune (NLS, contextul envun4,
#     variabilele de pachet) nu se poate scurge intre cereri — semantica e
#     identica cu vechiul proces-pe-interogare.
# EN: the POOL of LONG-LIVED workers. Spawning a process per query cost ~1.5s
#     and made the storefront slow. A pooled worker answers requests in turn;
#     each request still opens its OWN Oracle connection, so session state can
#     never leak between requests — semantics match the old process-per-call.
#
# RO: BIRO26_WORKER_POOL=0 il opreste (revine la proces-pe-interogare);
#     BIRO26_WORKER_POOL_SIZE regleaza cite procese stau pregatite.
_POOL_ENABLED = os.environ.get("BIRO26_WORKER_POOL", "1") != "0"
_POOL_SIZE = max(1, int(os.environ.get("BIRO26_WORKER_POOL_SIZE", "3")))


class _PooledWorker:
    """RO: un proces --serve cu care se vorbeste linie-cu-linie.
    EN: one --serve process spoken to line-by-line."""

    def __init__(self):
        # RO: stderr la DEVNULL — altfel un lucrator vorbaret ar umple
        #     conducta si s-ar bloca; erorile calatoresc oricum in JSON.
        # EN: stderr to DEVNULL so a chatty worker can never fill the pipe.
        self.proc = subprocess.Popen(
            [sys.executable, _WORKER, "--serve"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, cwd=_PROJECT_ROOT)

    def alive(self) -> bool:
        return self.proc.poll() is None

    def kill(self) -> None:
        try:
            self.proc.kill()
        except Exception:                                    # noqa: BLE001
            pass

    def ask(self, req: Dict[str, Any], tmo: int) -> Dict[str, Any]:
        """RO: o cerere, un raspuns. La timeout procesul se OMOARA — sesiunea
        Oracle cade si face rollback, exact plasa de siguranta pe care o dadea
        si vechiul subprocess.run(timeout=...). EN: on timeout the process is
        KILLED so the Oracle session dies and rolls back — the same safety net
        the old per-call subprocess gave."""
        self.proc.stdin.write(json.dumps(req) + "\n")
        self.proc.stdin.flush()
        fd = self.proc.stdout
        ready, _, _ = select.select([fd], [], [], tmo)
        if not ready:
            self.kill()
            raise TimeoutError(f"worker timeout after {tmo}s")
        line = fd.readline()
        if not line:
            raise BrokenPipeError("worker died")
        return json.loads(line)


class _Pool:
    """RO: coada de lucratori pregatiti; thread-safe. Cind toti sint ocupati,
    apelantul NU asteapta la rand — porneste un proces de unica folosinta, ca
    inainte: mai lent, dar fara cozi si fara limita de paralelism.
    EN: a queue of ready workers. When all are busy the caller does not queue
    up — it falls back to a one-shot process, slower but unbounded."""

    def __init__(self, size: int):
        self.size = size
        self._q: "queue.Queue[_PooledWorker]" = queue.Queue()
        self._lock = threading.Lock()
        self._made = 0

    def acquire(self) -> Optional[_PooledWorker]:
        try:
            w = self._q.get_nowait()
            if w.alive():
                return w
            w.kill()
            with self._lock:
                self._made -= 1
        except queue.Empty:
            pass
        with self._lock:
            if self._made < self.size:
                self._made += 1
                try:
                    return _PooledWorker()
                except Exception:                            # noqa: BLE001
                    self._made -= 1
        return None

    def release(self, w: _PooledWorker, broken: bool) -> None:
        if broken or not w.alive():
            w.kill()
            with self._lock:
                self._made -= 1
            return
        self._q.put(w)


_pool = _Pool(_POOL_SIZE)


class Biro26DB:
    """Subprocess-backed accessor for the OfficePlus ERP (Oracle 11g, thick mode)."""

    def __enter__(self) -> "Biro26DB":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    # -- transport ----------------------------------------------------
    def _call(self, req: Dict[str, Any],
              timeout: Optional[int] = None) -> Dict[str, Any]:
        # RO/EN: `timeout` scurt = plasa de siguranta pentru operatiile care
        #        pot astepta un lock tinut de alta sesiune (ex. atribuirea
        #        NRMANUAL pe un document deschis in aplicatia nativa):
        #        procesul-lucrator e oprit, sesiunea Oracle cade si face
        #        rollback, iar apelantul primeste un mesaj clar in loc sa
        #        astepte minute intregi.
        tmo = int(timeout or _TIMEOUT)
        if _POOL_ENABLED:
            w = _pool.acquire()
            if w is not None:
                broken = False
                try:
                    return w.ask(req, tmo)
                except TimeoutError as e:
                    broken = True
                    return {"success": False, "message": str(e)}
                except Exception as e:                       # noqa: BLE001
                    # RO: lucratorul a murit sau a raspuns stricat — se arunca
                    #     si cererea trece pe procesul de unica folosinta.
                    # EN: dead or garbled worker — drop it, fall through to
                    #     the one-shot path below.
                    broken = True
                finally:
                    _pool.release(w, broken)
        try:
            proc = subprocess.run(
                [sys.executable, _WORKER],
                input=json.dumps(req),
                capture_output=True,
                text=True,
                cwd=_PROJECT_ROOT,
                timeout=tmo,
            )
        except subprocess.TimeoutExpired:
            return {"success": False, "message": f"worker timeout after {tmo}s"}
        except Exception as e:
            return {"success": False, "message": f"worker spawn failed: {e}"}
        if proc.returncode != 0:
            return {"success": False,
                    "message": f"worker exit {proc.returncode}: {(proc.stderr or '')[:500]}"}
        try:
            return json.loads(proc.stdout)
        except Exception:
            return {"success": False,
                    "message": f"bad worker output: {(proc.stdout or '')[:300]} "
                               f"{(proc.stderr or '')[:300]}"}

    # -- queries ------------------------------------------------------
    def execute_query(self, sql: str, params: Optional[Dict[str, Any]] = None,
                      timeout: Optional[int] = None) -> Dict[str, Any]:
        r = self._call({"op": "query", "sql": sql, "params": params or {}}, timeout)
        return {
            "success": r.get("success", False),
            "columns": r.get("columns", []),
            "data": [tuple(row) for row in r.get("data", [])],
            "rowcount": r.get("rowcount", 0),
            "message": r.get("message", ""),
        }

    def execute_dml(self, sql: str, params: Optional[Dict[str, Any]] = None,
                    timeout: Optional[int] = None) -> Dict[str, Any]:
        r = self._call({"op": "dml", "sql": sql, "params": params or {}}, timeout)
        return {"success": r.get("success", False),
                "rowcount": r.get("rowcount", 0),
                "message": r.get("message", "")}

    def call_proc(self, plsql: str, params: Optional[Dict[str, Any]] = None,
                  capture_output: bool = False) -> Dict[str, Any]:
        """Run an anonymous PL/SQL block (optionally capturing DBMS_OUTPUT).

        `plsql` is a full block, e.g. "BEGIN YBIRO_Import_Marfa.validate_input; END;".
        Set package g_* vars in the SAME block so session state is consistent — the
        worker uses one connection for the whole block.
        """
        r = self._call({"op": "plsql", "plsql": plsql, "params": params or {},
                        "capture_output": capture_output})
        return {"success": r.get("success", False),
                "output_lines": r.get("output_lines", []),
                "message": r.get("message", "")}

    def execute_script(self, statements: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run several statements in ONE transaction (atomic multi-statement ops).

        Each statement: {"sql": str, "params": dict, "kind": "query"|"dml"}.
        Returns {success, results:[{columns,data,rowcount} | {rowcount}], message}.
        """
        r = self._call({"op": "script", "statements": statements})
        return {"success": r.get("success", False),
                "results": r.get("results", []),
                "message": r.get("message", "")}

    def test_connection(self) -> Dict[str, Any]:
        r = self._call({"op": "test"})
        return {"success": r.get("success", False),
                "version": r.get("version"),
                "error": r.get("message")}
