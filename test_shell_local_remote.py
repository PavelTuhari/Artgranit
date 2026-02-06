#!/usr/bin/env python3
"""
Тест shell (список проектов, дашборд по проекту) локально и на удалённом сервере.
Запуск: python test_shell_local_remote.py [--remote] [--local]
По умолчанию тестирует оба.
"""
import argparse
import sys
import os

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import Config


def test_base(session, base: str, label: str) -> bool:
    ok = True
    user = Config.DEFAULT_USERNAME or "ADMIN"
    pwd = Config.DEFAULT_PASSWORD or "admin"

    r = session.post(f"{base}/login", data={"username": user, "password": pwd}, timeout=10)
    if r.status_code not in (200, 302):
        print(f"  [{label}] POST /login: FAIL {r.status_code}")
        return False
    print(f"  [{label}] POST /login: OK")

    r = session.get(f"{base}/una.md/shell/projects", timeout=10)
    if r.status_code != 200:
        print(f"  [{label}] GET /una.md/shell/projects: FAIL {r.status_code}")
        ok = False
    else:
        print(f"  [{label}] GET /una.md/shell/projects: OK (len={len(r.text)})")

    r = session.get(f"{base}/api/shell/projects", timeout=10)
    if not r.ok or not r.json().get("success"):
        print(f"  [{label}] GET /api/shell/projects: FAIL")
        ok = False
    else:
        n = r.json().get("count", 0)
        print(f"  [{label}] GET /api/shell/projects: OK ({n} projects)")

    r = session.get(f"{base}/una.md/shell/credit/dashboard", timeout=10)
    if r.status_code != 200:
        print(f"  [{label}] GET /una.md/shell/credit/dashboard: FAIL {r.status_code}")
        ok = False
    else:
        print(f"  [{label}] GET /una.md/shell/credit/dashboard: OK")

    r = session.get(f"{base}/api/dashboard/list?project_slug=credit", timeout=10)
    if not r.ok or r.json().get("count", 0) == 0:
        print(f"  [{label}] GET /api/dashboard/list?project_slug=credit: FAIL")
        ok = False
    else:
        print(f"  [{label}] GET /api/dashboard/list?project_slug=credit: OK ({r.json().get('count')} dashboards)")

    return ok


def main():
    ap = argparse.ArgumentParser(description="Test shell endpoints locally and/or remote")
    ap.add_argument("--local", action="store_true", help="Test local only (localhost:3003)")
    ap.add_argument("--remote", action="store_true", help="Test remote only (REMOTE_SERVER_URL)")
    args = ap.parse_args()
    do_local = args.local or (not args.local and not args.remote)
    do_remote = args.remote or (not args.local and not args.remote)

    import requests
    session = requests.Session()
    session.headers["User-Agent"] = "TestShell/1.0"

    all_ok = True
    if do_local:
        port = os.environ.get("PORT", "3003")
        base = f"http://localhost:{port}"
        print(f"\n=== Local: {base} ===")
        all_ok = test_base(session, base, "local") and all_ok
    if do_remote:
        base = Config.REMOTE_SERVER_URL
        print(f"\n=== Remote: {base} ===")
        all_ok = test_base(session, base, "remote") and all_ok

    print("")
    if all_ok:
        print("All shell tests passed.")
        return 0
    print("Some tests failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
