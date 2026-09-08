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

## Pe ce canale pleacă

**Nu se configurează canale noi.** Sumarul merge pe exact aceleași canale ca notificările despre comenzile de pe site — cele din **Back-office → Setări notificări** (`/UNA.md/orasldev/biro26-notify-settings`): e-mail, Telegram, WhatsApp, fiecare dacă e bifat acolo. Starea lor se vede în pagina «Alerte», cu bifă verde / cruce roșie.

| Canal | Text trimis | De ce |
|---|---|---|
| Telegram | sumarul întreg | fără `parse_mode`: denumirile firmelor conțin `_`, `*`, `(` și Markdown-ul ar refuza mesajul; peste 3800 de caractere se taie pe rând întreg |
| WhatsApp `callmebot` | **variantă scurtă** (total + câte de fiecare tip + link) | callmebot trece textul prin adresa URL — sumarul întreg dă `HTTP 414 Request-URI Too Large` (verificat 08.09.2026) |
| WhatsApp `cloud` | sumarul întreg | Cloud API nu are limita de adresă |
| E-mail | sumarul întreg, cu subiect | — |

**Clientul din cabinet** nu are acces la setările magazinului, deci el indică doar `chat_id`-ul lui de Telegram; botul rămâne cel al magazinului — așa nu apar token-uri de clienți în bază. OfficePlus poate pune și el un chat separat doar pentru CRM (câmpul e opțional): atunci sumarul pleacă doar acolo.

**Fără spam:** o alertă deja trimisă se repetă doar dacă a trecut perioada de liniște (`QUIET_DAYS`) **sau** dacă suma s-a schimbat (datoria a crescut / s-a plătit parțial). Alertele rezolvate se șterg din istoric, ca la reapariție să fie anunțate din nou.

## Pagina «Alerte»

`/UNA.md/orasldev/crm/#alerts` (și în cabinet, `/crm/cabinet#alerts`): plitele (de încasat, deschise, noi, câte grave), lista alertelor deschise cu click pe document, **textul exact** care pleacă în Telegram și setările:

| Setare | Implicit | Ce face |
|---|---|---|
| Alerte pornite | oprit | fără ea sumarul programat nu pleacă |
| Telegram chat ID | gol | **opțional**: un chat separat doar pentru CRM; gol = canalele magazinului |
| Token bot | gol = al magazinului | doar dacă vreți bot separat |
| Limba mesajului | `ro` | ro / ru / en |
| Tipuri incluse | toate | bifele de mai sus |
| Avertizare cu N zile înainte | 3 | `due_soon`; 0 = oprit |
| Prag datorie | 0 | sub el datoriile nu se raportează |
| Nu repeta (zile) | 1 | perioada de liniște |
| Ora sumarului | 8 | ora locală (Europe/Chișinău) |

Butonul **Trimite acum** trimite imediat pe toate canalele pregătite, chiar dacă nu e nimic nou.

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
| **Trimitere reală pe canalele magazinului** | Telegram **OK**, WhatsApp **OK** (după trecerea la varianta scurtă), e-mail — `SMTP is not configured` (așa e și pentru comenzile de pe site) |
| Timer | `crm-alerts.timer` instalat și pornit pe nufarul |
| Alerte pornite | da, limba `ru`, ora 8:00 (Europe/Chișinău) |

**De reținut:** e-mailul nu pleacă până nu se completează SMTP în `.env` — aceeași situație ca la notificările despre comenzi. Telegram și WhatsApp funcționează.
