# Комиссии кредитования — эталон до интеграции с Ultra API

Требование владельца 28.08.2026: **после интеграции с Ultra API суммы
комиссий должны остаться такими же, как были до интеграции.**

Здесь зафиксировано состояние на момент, когда интеграция Ultra ещё не
влияла на цены. Это эталон для сверки — не документация «как считать».

Действующая комиссия = `TMS_CREDITE_PLAN.MARKUP_PCT` +
`TMS_CREDITE_ORG.TRANSPORT_MARKUP_PCT` (надбавка заменяет неоказанный
транспорт). Именно она умножает цену в рассрочку.

Снято: 2026-08-28 23:48

| Организация | Пакет | Наценка пакета | Надбавка орг. | **Комиссия** |
|---|---|---:|---:|---:|
| EasyCredit | Special 0% / 4 luni | 5% | 10% | **15%** |
| EasyCredit | Special 0% / 6 luni | 5% | 10% | **15%** |
| EasyCredit | Credit / 8 luni | 12.4% | 10% | **22.4%** |
| EasyCredit | Credit / 10 luni | 13% | 10% | **23%** |
| EasyCredit | Credit / 12 luni | 15.75% | 10% | **25.75%** |
| EasyCredit | Credit / 24 luni | 28.4% | 10% | **38.4%** |
| EasyCredit | Credit / 36 luni | 42% | 10% | **52%** |
| Liber Card MAIB | Liber Card / 6 rate | 8% | 10% | **18%** |
| MAIB Credit de consum | Credit de consum / 12 luni | 5% | 10% | **15%** |
| MAIB Credit de consum | Credit de consum / 18 luni | 5% | 10% | **15%** |
| MAIB Credit de consum | Credit de consum / 24 luni | 5% | 10% | **15%** |
| MAIB Credit de consum | Credit de consum / 36 luni | 5% | 10% | **15%** |
| MAIB Credit de consum | Credit de consum / 48 luni | 5% | 10% | **15%** |
| MAIB Credit de consum | Credit de consum / 60 luni | 5% | 10% | **15%** |
| Microinvest | Microinvest / 0% 4 luni plus | 16% | 0% | **16%** |
| Microinvest | Microinvest / 0% 6 luni plus | 18% | 0% | **18%** |
| Microinvest | Microinvest / Standard 6-48 luni | 5% | 0% | **5%** |

Всего пакетов: 17

## Как проверить, что ничего не поехало

```bash
./venv/bin/python scripts/check_comisioane.py
```

Скрипт сравнивает текущие значения с этой таблицей и показывает
расхождения. Запускать после каждого этапа интеграции Ultra.

## Где комиссия участвует в расчёте

Одна и та же цифра обязана совпадать в четырёх местах (см. `CLAUDE.md`):
`models/biro26_credit.py` (`calc`), `controllers/biro26_controller.py`
(`shop_invoice`) и три шаблона витрины. Расхождение = клиент видит одну
цену, платит другую.
