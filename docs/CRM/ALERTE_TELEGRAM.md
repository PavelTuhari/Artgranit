# Alerte Telegram: tranzacții nefinisate și datorii

**Data:** 08.09.2026 · **Ramura:** `feat/crm` (worktree `Artgranit-crm`) · **Contur:** `nufarul.eminescu.md`

**Cerința proprietarului:** „de adăugat notificări pe telegram cu tranzacțiile nefinisate și cu datorii”.

## Ce se raportează

O **tranzacție nefinisată** = un document care stă într-o etapă în care n-ar trebui să stea; o **datorie** = bani livrați și neîncasați. Cele opt tipuri, în ordinea gravității:

| Tip | Ce înseamnă | De unde vine condiția | Grav. |
|---|---|---|---|
| `debt` | livrat, plata nu acoperă totalul | etapa `await_payment` | !! |
| `overdue_work` | în lucru, termenul a trecut | `overdue_where("in_work")` | !! |
| `project_debt` | proiect deschis: buget − avans − plăți > prag | `CRM_PROJECT` | !! |
| `await_advance` | confirmat, avansul nu a intrat | etapa `await_advance` | ! |
| `ready_to_ship` | executat, livrarea neîntocmită | etapa `ready_to_ship` | ! |
| `unposted` | executat/plătit, dar necontabilizat (`POSTED = 0`) | `CRM_ORDER` | ! |
| `deal_stale` | ofertă în „Ofertă/Negocieri” cu data de închidere trecută | `CRM_DEAL` | .. |
| `due_soon` | termenul vine în N zile, încă nelivrat | `CRM_ORDER` | .. |

Condițiile comenzilor **nu sunt rescrise**: vin din `process.stage_where` / `overdue_where` — același adevăr despre etape ca tabloul de lucru și kanbanul (regula prototipului: etapele au un singur loc de definire).

În „TOTAL de încasat” intră doar `debt` și `project_debt` — restul sunt semnale de proces, nu bani de așteptat.

## Cum ajunge în Telegram

- **Botul:** același transport ca restul portalului (`Biro26Notify._send_telegram`). Tokenul îl ține **OfficePlus** (setările de notificări ale magazinului) — clientul din cabinet indică doar `chat_id`-ul lui, deci nu apar token-uri de clienți prin bază. Un client poate pune totuși tokenul lui, dacă vrea bot separat.
- **Mesaj text simplu**, fără `parse_mode`: denumirile firmelor conțin `_`, `*`, `(` și Markdown-ul ar refuza mesajul. Peste 3800 de caractere se taie pe rând întreg, cu „... și încă N”.
- **Fără spam:** o alertă deja trimisă se repetă doar dacă a trecut perioada de liniște (`QUIET_DAYS`) **sau** dacă suma s-a schimbat (datoria a crescut / s-a plătit parțial). Alertele rezolvate se șterg din istoric, ca la reapariție să fie anunțate din nou.
- **Per chiriaș:** OfficePlus are setările lui, fiecare client din cabinet — pe ale lui (`OWNER_KIND/OWNER_ID` în ambele tabele).

## Pagina «Alerte»

`/UNA.md/orasldev/crm/#alerts` (și în cabinet, `/crm/cabinet#alerts`): plitele (de încasat, deschise, noi, câte grave), lista alertelor deschise cu click pe document, **textul exact** care pleacă în Telegram și setările:

| Setare | Implicit | Ce face |
|---|---|---|
| Alerte pornite | oprit | fără ea sumarul programat nu pleacă |
| Telegram chat ID | — | scrieți botului un mesaj, luați id-ul din `@userinfobot` |
| Token bot | gol = al OfficePlus | doar dacă vreți bot separat |
| Limba mesajului | `ro` | ro / ru / en |
| Tipuri incluse | toate | bifele de mai sus |
| Avertizare cu N zile înainte | 3 | `due_soon`; 0 = oprit |
| Prag datorie | 0 | sub el datoriile nu se raportează |
| Nu repeta (zile) | 1 | perioada de liniște |
| Ora sumarului | 8 | ora locală (Europe/Chișinău) |

Butonul **Trimite acum** trimite imediat, chiar dacă nu e nimic nou.

## Obiecte și fișiere

| Ce | Unde |
|---|---|
| Reguli pure (tipuri, chei, text ro/ru/en, când se repetă) | `modules/crm/alerts.py` |
| Interogări + bot + rulare pe toți chiriașii | `modules/crm/notify.py` |
| Rute `/api/v2/alerts`, `/alerts/settings`, `/alerts/send` | `modules/crm/routes_alerts.py` |
| Pagina | `modules/crm/static/crm_alerts.js` + secțiunea `#sec-alerts` |
| DDL | `modules/crm/sql/03_crm_alerts.sql` — `CRM_ALERT_CFG`, `CRM_ALERT_SENT` |
| Script + timer | `modules/crm/scripts/crm_alerts.py`, `modules/crm/deploy/crm-alerts.{service,timer}` |
| Teste (fără Oracle) | `tests/test_crm.py` — 10 teste noi din 36 |

Fișiere separate, în modul, conform CLAUDE.md regula nr. 2; în codul comun nu s-a adăugat nimic.

## Rularea programată

Timerul pornește **în fiecare oră**; scriptul trimite doar chiriașilor a căror `SEND_HOUR` coincide și care au alertele pornite.

```bash
sudo cp /home/ubuntu/artgranit/modules/crm/deploy/crm-alerts.service /etc/systemd/system/
sudo cp /home/ubuntu/artgranit/modules/crm/deploy/crm-alerts.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now crm-alerts.timer
systemctl list-timers crm-alerts --no-pager
```

Verificări manuale:

```bash
cd /home/ubuntu/artgranit
venv/bin/python modules/crm/scripts/crm_alerts.py --dry-run --office   # arată textul, nu trimite
venv/bin/python modules/crm/scripts/crm_alerts.py --dry-run --client 7
venv/bin/python modules/crm/scripts/crm_alerts.py --now --office --force  # trimite acum
journalctl -u crm-alerts --since '-1d' --no-pager | tail
```

## Verificat pe 08.09.2026

| Verificare | Rezultat |
|---|---|
| `pytest tests/test_crm.py` | **36 passed** (10 noi pentru alerte) |
| `crm_deploy.py` | tabelele `CRM_ALERT_*` instalate, instalatorul rămâne idempotent |
| `crm_alerts.py --dry-run --office` | 21 alerte pe datele demo: 4 datorii, 3 termene depășite, 8 proiecte, 2+2+2 |
| Pagina, salvarea setărilor | prag 500 lei și două tipuri scoase → 21 → 18 alerte |
| Trimiterea reală | a ajuns la API-ul Telegram: `Bad Request: chat not found` — botul OfficePlus funcționează, doar `chat_id`-ul de test era inventat |
| După test | setările au fost readuse la starea inițială (oprite, fără chat) — baza e comună cu officeplus |

**Rămâne de făcut de proprietar:** deschideți pagina, puneți `chat_id`-ul dvs. (sau al grupului), bifați «Alerte pornite», alegeți ora — și instalați timerul cu comenzile de mai sus.
