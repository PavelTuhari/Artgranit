"""PECO: жизненный цикл смены и расчёт расхождений.

Функции расчёта — чистые: принимают и возвращают словари, к базе не
обращаются. Это делает главную бизнес-логику модуля тестируемой без Oracle.

Три расхождения соответствуют трём разным типам отказа и намеренно
не сводятся в одно число:

  liter_variance -- топливо вышло из пистолета, но не оплачено
  cash_variance  -- недостача или излишек денежного ящика
  tank_variance  -- утечка либо уход калибровки резервуара
"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from typing import Any, Dict, List, Optional

from models.peco_oracle_store import PecoStore

# Допуски. Выход за пределы переводит смену в DISPUTED и требует PIN менеджера.
TOLERANCE_LITERS: float = 0.5
TOLERANCE_CASH: float = 1.0

# Допуск по резервуару. Он НЕ равен допуску по счётчику: замер метрштоком
# на резервуаре 20000 л даёт погрешность порядка ±5 л, а тепловое расширение
# дизеля (~0,08 %/°C) — около 16 л на градус. Допуск 0,5 л здесь означал бы
# DISPUTED на каждой смене, и статус перестал бы что-либо значить.
# Значение подлежит настройке владельцем по фактической статистике.
TOLERANCE_TANK_LITERS: float = 50.0


def meter_delta(meters: List[Dict[str, Any]]) -> float:
    """Сумма (METER_CLOSE - METER_OPEN) по пистолетам со снятым показанием."""
    total = 0.0
    for m in meters:
        close = m.get("meter_close")
        if close is None:
            continue
        total += float(close) - float(m.get("meter_open") or 0.0)
    return round(total, 3)


def compute_variances(
    meters: List[Dict[str, Any]],
    txn_liters: float,
    cash_declared: float,
    cash_expected: float,
) -> Dict[str, Any]:
    """Считает расхождения смены по счётчикам и кассе.

    tank_variance здесь всегда None: расхождение по резервуару считается
    только по резервуарам отдельно, функцией tank_variances() ниже —
    станционная сумма как раз и есть та ошибка, ради которой резервуары
    не сводятся в одно число (см. модуль docstring).
    """
    delta = meter_delta(meters)

    liter_variance = round(delta - float(txn_liters), 3)
    cash_variance = round(float(cash_declared) - float(cash_expected), 2)

    return {
        "meter_delta": delta,
        "liter_variance": liter_variance,
        "cash_variance": cash_variance,
        "tank_variance": None,
    }


def tank_variances(
    tank_rows: List[Dict[str, Any]],
    meters: List[Dict[str, Any]],
    dips: Dict[int, float],
) -> List[Dict[str, Any]]:
    """Расхождение по каждому резервуару отдельно.

    tank_rows — строки PECO_SHIFT_TANKS (остаток на открытие и приход за
    смену). meters — строки PECO_SHIFT_METERS, каждая с TANK_ID своего
    пистолета. dips — {tank_id: замер на закрытие}.

    Считается по резервуарам, а не суммой по станции: утечка в одном
    резервуаре и излишек в другом взаимно погасились бы и обе исчезли.
    """
    dispensed: Dict[int, float] = {}
    for m in meters:
        close = m.get("meter_close")
        if close is None:
            continue
        tank_id = m.get("tank_id")
        if tank_id is None:
            continue
        delta = float(close) - float(m.get("meter_open") or 0.0)
        dispensed[tank_id] = dispensed.get(tank_id, 0.0) + delta

    out: List[Dict[str, Any]] = []
    for t in tank_rows:
        tank_id = t["tank_id"]
        dip = dips.get(tank_id)
        variance = None
        if dip is not None:
            # VOLUME_OPEN_L и DELIVERED_L — колонки NOT NULL; отсутствие
            # значения означает битые данные, а не законный ноль, и должно
            # упасть здесь, а не молча превратиться в 0.0.
            expected = (float(t.get("volume_open_l"))
                        + float(t.get("delivered_l"))
                        - dispensed.get(tank_id, 0.0))
            variance = round(float(dip) - expected, 3)
        out.append({
            "tank_id": tank_id,
            "grade_code": t.get("grade_code"),
            "dip_close_l": dip,
            "tank_variance": variance,
        })
    return out


def exceeds_tolerance(variances: Dict[str, Any]) -> bool:
    """Проверяется модуль отклонения: излишек — такое же расхождение.

    Отсутствие замера (None) — это не доказательство отсутствия
    расхождения, а недостаток данных. Чистой смена признаётся только
    если известно, что расхождения в допуске, поэтому отсутствующие
    liter_variance/cash_variance трактуются как «за пределами допуска»,
    а не как ноль. Для tank_variance это не так: пока станция считает
    tank_variance отдельно по резервуарам, отсутствие снимка по станции
    в целом ожидаемо и не должно само по себе диспутить смену — см.
    tank_variances_exceed() для проверки по каждому резервуару.
    """
    liter = variances.get("liter_variance")
    if liter is None or abs(float(liter)) > TOLERANCE_LITERS:
        return True
    cash = variances.get("cash_variance")
    if cash is None or abs(float(cash)) > TOLERANCE_CASH:
        return True
    tank = variances.get("tank_variance")
    if tank is not None and abs(float(tank)) > TOLERANCE_TANK_LITERS:
        return True
    return False


def tank_variances_exceed(rows: List[Dict[str, Any]]) -> bool:
    """Выходит ли расхождение хотя бы по одному резервуару за допуск.

    Проверяется каждый резервуар отдельно. Сумма по станции здесь не годится:
    утечка в одном резервуаре и излишек в другом взаимно погасились бы,
    и смена закрылась бы как чистая — ровно та ошибка, ради которой
    расхождение и считается по резервуарам.
    """
    for r in rows:
        v = r.get("tank_variance")
        if v is not None and abs(float(v)) > TOLERANCE_TANK_LITERS:
            return True
    return False


def resolve_status(variances: Dict[str, Any]) -> str:
    """Итоговый статус смены по расхождениям."""
    return "DISPUTED" if exceeds_tolerance(variances) else "CLOSED"


# ------------------------------------------------------------------
# Оркестрация (обращается к store, но не пишет SQL сама)
# ------------------------------------------------------------------


def open_shift(station_id: int, employee_id: int) -> Dict[str, Any]:
    """Открывает смену. На станции может быть только одна открытая смена."""
    existing = PecoStore.get_open_shift(station_id)
    if existing.get("success"):
        return {"success": False,
                "error": "На станции уже открыта смена",
                "shift_id": existing["shift"].get("id")}

    created = PecoStore.open_shift(station_id, employee_id)
    if not created.get("success"):
        err = str(created.get("error") or "")
        # Гонка: проверку выше прошли оба запроса, но уникальный индекс
        # UX_PECO_SHIFTS_ACTIVE пропустил только один. Возвращаем доменную
        # ошибку, а не текст ORA.
        if "UX_PECO_SHIFTS_ACTIVE" in err.upper() or "ORA-00001" in err.upper():
            return {"success": False, "error": "На станции уже открыта смена"}
        return created

    if created.get("shift_id") is None:
        # CURRVAL не вернул строку: смена формально создана, но у нас нет
        # её id. Возвращать success с null id хуже, чем явная ошибка.
        return {"success": False,
                "error": "Не удалось получить номер созданной смены"}

    log_r = PecoStore.log_event(
        "SHIFT_OPENED",
        station_id=station_id,
        shift_id=created["shift_id"],
        entity_type="SHIFT",
        entity_id=created["shift_id"],
        employee_id=employee_id,
    )
    if not log_r.get("success"):
        # Смена уже открыта в Oracle; сбой аудит-лога не должен откатывать
        # операцию, но и молчать о нём нельзя.
        created = dict(created, audit_warning="Не удалось записать событие открытия смены")
    return created


def close_shift(
    shift_id: int,
    employee_id: int,
    cash_declared: float,
    dips: Optional[Dict[int, float]] = None,
) -> Dict[str, Any]:
    """Закрывает смену со сверкой.

    dips — замеры на закрытие: {tank_id: измеренные литры}. Остаток на
    открытие и приход за смену НЕ принимаются от вызывающего: они читаются
    из PECO_SHIFT_TANKS, куда попали при открытии смены и при приёме
    цистерн. Иначе оператор мог бы подогнать расхождение под ноль,
    объявив удобные исходные цифры.
    """
    unresolved = PecoStore.count_unresolved_txn(shift_id)
    if not unresolved.get("success"):
        return unresolved
    if unresolved["count"] > 0:
        return {
            "success": False,
            "error": "Есть неразобранные транзакции: оплатите или аннулируйте",
            "unresolved": unresolved["count"],
        }

    meters_r = PecoStore.get_shift_meters(shift_id)
    if not meters_r.get("success"):
        return meters_r
    meters = meters_r["items"]

    # Смена не закрывается, пока не снято показание с КАЖДОГО пистолета.
    # meter_delta() пропускает пистолеты без METER_CLOSE, а не считает их
    # нулём — иначе отпуск без снятого показания дал бы liter_variance = 0
    # и смена ушла бы в CLOSED, хотя топливо физически ушло без следа: не
    # видно ни в кассе (транзакции нет), ни в резервуаре (тотализатор не
    # сдвинулся, и следующая смена унаследует то же самое METER_OPEN).
    missing_meters = [m.get("nozzle_id") for m in meters
                      if m.get("meter_close") is None]
    if missing_meters:
        codes = [str(m.get("nozzle_code") or m.get("nozzle_id"))
                 for m in meters if m.get("meter_close") is None]
        return {
            "success": False,
            "error": "Не сняты показания счётчиков: " + ", ".join(codes),
            "missing_meters": missing_meters,
        }

    paid = PecoStore.shift_paid_liters(shift_id)
    if not paid.get("success"):
        return paid

    # Смена помечается CLOSING до записи замеров: между началом закрытия и
    # finalize_shift она не должна выглядеть обычной открытой, иначе после
    # сбоя в реестре резервуаров останется замер на закрытие при статусе
    # OPEN, а колонки продолжат отпускать топливо.
    closing = PecoStore.mark_shift_closing(shift_id)
    if not closing.get("success"):
        return closing

    # Расхождение по каждому резервуару считается отдельно: у станции до
    # четырёх резервуаров, и утечка в одном не должна тонуть в сумме.
    tanks_r = PecoStore.get_shift_tanks(shift_id)
    if not tanks_r.get("success"):
        return tanks_r
    tank_rows = tanks_r["items"]
    dips = dips or {}

    known_tank_ids = {t["tank_id"] for t in tank_rows}
    ignored_dips = sorted(tid for tid in dips if tid not in known_tank_ids)

    per_tank = tank_variances(tank_rows, meters, dips)
    for row in per_tank:
        if row["tank_variance"] is not None:
            saved_tank = PecoStore.save_tank_close(
                shift_id, row["tank_id"], row["dip_close_l"],
                row["tank_variance"],
            )
            if not saved_tank.get("success"):
                return saved_tank

    measured = [r["tank_variance"] for r in per_tank
                if r["tank_variance"] is not None]
    tank_total = round(sum(measured), 3) if measured else None

    variances = compute_variances(
        meters,
        txn_liters=paid["liters"],
        cash_declared=cash_declared,
        cash_expected=paid["cash"],
    )
    variances["tank_variance"] = tank_total

    # Статус решается и по сумме, и по КАЖДОМУ резервуару отдельно.
    # Только по сумме нельзя: утечка в одном резервуаре и излишек в другом
    # погасили бы друг друга, и смена закрылась бы как чистая.
    status = ("DISPUTED"
              if exceeds_tolerance(variances) or tank_variances_exceed(per_tank)
              else "CLOSED")
    totals = {
        "cash_declared": cash_declared,
        "cash_expected": paid["cash"],
        "cash_variance": variances["cash_variance"],
        "liter_variance": variances["liter_variance"],
        "tank_variance": variances["tank_variance"],
    }

    saved = PecoStore.finalize_shift(
        shift_id, employee_id=employee_id, status=status, totals=totals
    )
    if not saved.get("success"):
        return saved

    log_r = PecoStore.log_event(
        "SHIFT_CLOSED",
        shift_id=shift_id,
        entity_type="SHIFT",
        entity_id=shift_id,
        employee_id=employee_id,
        payload={"status": status, **variances},
    )

    result: Dict[str, Any] = {"success": True, "status": status,
                               "variances": variances,
                               "mia_amount": paid["mia"], "tanks": per_tank}
    if ignored_dips:
        result["ignored_dips"] = ignored_dips
    if not log_r.get("success"):
        # Смена уже закрыта в Oracle; сбой аудит-лога не должен откатывать
        # операцию, но и молчать о нём нельзя.
        result["audit_warning"] = "Не удалось записать событие закрытия смены"
    return result


# Число итераций PBKDF2. PIN четырёхзначный, то есть пространство перебора
# крошечное — стойкость здесь даёт только стоимость одной проверки.
# 600_000 — текущая рекомендация OWASP для PBKDF2-HMAC-SHA256 (2023+).
# Эта стоимость платится один раз на подтверждение расхождения менеджером,
# а не на горячем пути: approve_disputed вызывается вручную, не в цикле
# обслуживания клиентов, так что лишние миллисекунды здесь не заметны.
_PIN_ITERATIONS = 600_000


def new_salt() -> str:
    """Случайная соль на сотрудника (32 hex-символа)."""
    return secrets.token_hex(16)


def hash_pin(pin: str, salt: str) -> str:
    """PBKDF2-HMAC-SHA256 от PIN с солью сотрудника.

    Соль обязательна: без неё одинаковый PIN у двух сотрудников даёт
    одинаковый хеш, и всё пространство четырёхзначных PIN вскрывается
    одной радужной таблицей. PIN в открытом виде не хранится и не логируется.
    """
    dk = hashlib.pbkdf2_hmac(
        "sha256", str(pin).encode("utf-8"), str(salt).encode("utf-8"),
        _PIN_ITERATIONS,
    )
    return dk.hex()


def verify_pin(pin: str, salt: str, expected_hash: str) -> bool:
    """Сравнение в постоянном времени, чтобы не утекала длина совпадения."""
    if not salt or not expected_hash:
        return False
    return hmac.compare_digest(hash_pin(pin, salt), str(expected_hash))


def approve_disputed(shift_id: int, manager_id: int, pin: str) -> Dict[str, Any]:
    """Подтверждение смены с расхождением. Требует роль MANAGER или ADMIN.

    Расхождение при этом не обнуляется: статус остаётся DISPUTED, а в
    APPROVED_BY фиксируется, кто принял его под ответственность.
    """
    # Единое сообщение об ошибке для "нет такого сотрудника", "не менеджер"
    # и "неверный PIN": по-разному сформулированные ответы сказали бы
    # атакующему, существует ли ID сотрудника и есть ли у него роль
    # менеджера — той же логике, что и в approve_shift ниже.
    generic_error = {"success": False, "error": "Неверный сотрудник или PIN"}

    emp_r = PecoStore.get_employee_credentials(manager_id)
    if not emp_r.get("success"):
        return generic_error
    emp = emp_r["employee"]

    if emp.get("role_code") not in ("MANAGER", "ADMIN"):
        return generic_error

    if not verify_pin(pin, emp.get("pin_salt"), emp.get("pin_hash")):
        return generic_error

    # Станция менеджера идёт в БД вместе с проверкой статуса: ADMIN
    # (STATION_ID NULL) утверждает по всей сети, MANAGER — только свою.
    station_id = None if emp.get("role_code") == "ADMIN" else emp.get("station_id")

    saved = PecoStore.approve_shift(shift_id, manager_id, station_id)
    if not saved.get("success"):
        return saved

    log_r = PecoStore.log_event(
        "SHIFT_APPROVED",
        shift_id=shift_id,
        entity_type="SHIFT",
        entity_id=shift_id,
        employee_id=manager_id,
    )
    result: Dict[str, Any] = {"success": True}
    if not log_r.get("success"):
        # Единственное назначение этого события — зафиксировать, кто принял
        # расхождение под ответственность; потерять его тише, чем
        # SHIFT_CLOSED, нельзя.
        result["audit_warning"] = "Не удалось записать событие подтверждения смены"
    return result
