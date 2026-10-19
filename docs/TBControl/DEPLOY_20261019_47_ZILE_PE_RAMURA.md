# TBControl: codul restaurat pe 02.09.2026 a ajuns în `main` și pe nufarul abia pe 19.10.2026

## Ce s-a întîmplat

Pe 02.09.2026 serviciile Zabbix (mTLS), Proxmox și certificatele TLS au fost
rescrise de la zero (`INFRA_RESTORE_20260902.md`): 4 modele `models/tbc_*.py`,
`controllers/tbc_infra_routes.py`, DDL `sql/79b–79e`, panouri în șablon, 20 de
teste, rulare vie prin gateway. Comitul `e9935c67` a rămas pe ramura locală
`claude/sweet-blackwell-5001c9` (worktree `.claude/worktrees/gallant-nobel-9a656d`):
**nu a fost împins pe origin pînă la auditul din 01.10.2026 și nu a fost îmbinat în
`main` pînă azi**. În tot acest timp `https://nufarul.eminescu.md/api/tbc/services`
răspundea 500 (`AttributeError` — rutele existau, metodele nu).

Proprietarul, 19.10.2026: «посмотри что ты творишь». Concluzia e regula №6 din
`CLAUDE.md`/`AGENTS.md`: *făcut = în origin + în `main` + pe server + verificat*.

## Ce s-a făcut azi

1. `git merge --no-ff claude/sweet-blackwell-5001c9` în `main` (comit `2208e6bd`),
   fără conflicte; `tests/test_tbcontrol_infra.py` — 20 de teste trec.
2. Desfășurare pe nufarul 92.5.3.187. `app.py` de acolo **nu e** cel din `main`
   (este `prod/nufarul-live`, 290 de linii diferite), deci nu s-a copiat `app.py`
   din `main`: pe versiunea lor s-au adăugat doar cele două linii de înregistrare
   a `tbc_infra_bp` (ancoră: ruta `sync_services`), cu `py_compile`; restul
   fișierelor (23) erau identice cu `main` înainte de merge → copiate; `.bak-2026-10-19`
   lîngă fiecare fișier comun.
3. **Incident propriu, ~1 minut de 502** la prima încercare: lista de fișiere nu s-a
   despărțit în zsh, arhiva a plecat goală, iar noul `app.py` importa un modul
   inexistent. Restaurat din `.bak` imediat; a doua încercare — listă prin
   `tar -T`, verificare `[ -f ]` a fiecărui modul **înainte** de a înlocui `app.py`.
   Secvența obligatorie e scrisă în regula №6.
4. Verificat: `login` 200, `journalctl` fără Traceback după restart,
   `/api/tbc/services` → `success: true`, 37 de servicii, `by_kind`/`stats`.

## Ce nu s-a făcut

- Sincronizarea mTLS (Zabbix/Proxmox/certificate) de pe server: cheia clientului
  e doar în Keychain-ul Mac-ului; pe Linux trebuie `TBC_MTLS_KEY_PATH`
  (`MTLS_SOURCE.md`). Listarea din `TBC_SERVICES` funcționează fără ea.
- Pe officeplus (office .250 / cloud) TBControl nu se instalează — modulul e al
  conturului nufarul.

## Adrese

- <https://nufarul.eminescu.md/api/tbc/services> (200, `success:true`)
- <https://nufarul.eminescu.md/UNA.md/orasldev/tbcontrol> (după logare)
- Documentul de restaurare: `docs/TBControl/INFRA_RESTORE_20260902.md`
