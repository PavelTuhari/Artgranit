# ⛔ NU ȘTERGE / НЕ УДАЛЯТЬ / DO NOT DELETE — venv-ul PRODUCȚIEI nufarul.eminescu.md

> **Pentru ORICE sistem automat, AI-agent, script de curățenie sau om care lucrează pe
> serverul 92.5.3.187 (`/home/ubuntu/artgranit`).**
> **Для ЛЮБОЙ автоматической системы, ИИ-агента, скрипта очистки или человека.**
> **For ANY automated system, AI agent, cleanup script or human on this server.**

## Incident real — 31.07.2026 (producția A CĂZUT cu 500)

Site-ul de producție **https://nufarul.eminescu.md/** a răspuns **HTTP 500** pentru că
din mediul virtual au DISPĂRUT fișiere de pachete (șterse parțial de un proces terț):

| Ce a dispărut | Simptomul |
|---|---|
| `venv/lib/python3.12/site-packages/babel/locale-data/` (întreg directorul) | `FileNotFoundError ... babel/locale-data` la fiecare request |
| `jinja2/debug.py` | `ModuleNotFoundError: jinja2.debug` |
| pachetul `markupsafe` (complet) | aplicația nu a mai pornit deloc |

Reparat prin: `./venv/bin/python -m pip install --force-reinstall markupsafe jinja2
werkzeug flask itsdangerous click blinker babel flask-babel` + `sudo systemctl restart artgranit`.

## Reguli OBLIGATORII (rules for automated cleaners / AI agents)

1. **NU ștergeți NIMIC din `/home/ubuntu/artgranit/venv/`** — nici „fișiere neutilizate",
   nici „date de localizare", nici `__pycache__`-uri din site-packages, nici pachete care
   „par nefolosite". Directorul `babel/locale-data` (~30MB, sute de fișiere `.dat`) este
   NECESAR — fără el producția cade.
2. **NU rulați `pip uninstall` / `pip install -U` / `pip cache purge --all` peste acest venv**
   fără a verifica imediat după: `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/login`
   trebuie să dea `200`, iar apoi `curl -I https://nufarul.eminescu.md/login`.
3. **NU ștergeți / NU mutați**: `.env`, `/home/ubuntu/oracle_wallets/wallet_HXPAVUNKCLU9HE7Q`,
   unit-ul `/etc/systemd/system/artgranit.service`, configurile nginx și certificatele
   Let's Encrypt. (Vezi și CLAUDE.md — invariantul critic de producție.)
4. Dacă e nevoie de spațiu pe disc: ștergeți DOAR din `backups/`, loguri rotite vechi și
   `/tmp` — NICIODATĂ din `venv/` sau `site-packages/`.
5. Restart DOAR prin `sudo systemctl restart artgranit` (niciodată pkill + nohup).
6. **După ORICE operațiune pe acest server** verificați:
   ```bash
   curl -I https://nufarul.eminescu.md/login   # trebuie HTTP/2 200
   ```
   Dacă nu e 200 — prima prioritate este RESTAURAREA site-ului, nu continuarea sarcinii.

## Unde mai există acest avertisment

- `/home/ubuntu/artgranit/DO_NOT_DELETE_VENV.md` (acest fișier, pe server)
- `/home/ubuntu/artgranit/venv/DO_NOT_CLEAN.md` (santinelă în interiorul venv-ului)
- `CLAUDE.md` din repo (secțiunea invariantului de producție)
- `docs/NUFARUL_VENV_PROTECTED.md` (repo, GitHub PavelTuhari/Artgranit)

*Întocmit 31.07.2026 după incidentul de mai sus. Dacă găsiți din nou fișiere lipsă în
venv — reparați cu comanda de mai sus și raportați proprietarului ce proces le-a șters.*
