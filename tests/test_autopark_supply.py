"""Контур распределения топлива (ТЗ заказчика от 18.09.2026).

Проверяется чистая часть — `modules/autopark/supply_rules.py`: она не
импортирует БД, поэтому весь алгоритм гоняется без wallet и без Oracle.
Тесты структуры DDL — ниже, они читают SQL как текст.

Запуск: venv/bin/python -m pytest tests/test_autopark_supply.py -q
"""
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from modules.autopark import supply_rules as sr  # noqa: E402

SQL_DIR = os.path.join(ROOT, "modules", "autopark", "sql")


def _sql(name):
    with open(os.path.join(SQL_DIR, name), encoding="utf-8") as fh:
        return fh.read()


def sections(*volumes):
    """Отсеки цистерны: 1 — ближний к кабине, последний — хвостовой."""
    return [{"id": i + 1, "seq_no": i + 1, "volume_l": float(v)}
            for i, v in enumerate(volumes)]


def tail_first(secs):
    return sorted(secs, key=lambda s: -s["seq_no"])


# ── п.4.1: допустимый объём поставки ─────────────────────────────────

def test_allowed_volume_is_max_fill_minus_stock_tor_example():
    # Пример из ТЗ: допустимая вместимость 20 000, остаток 7 200 -> 12 800
    assert sr.allowed_volume_l(20000, 7200) == 12800


def test_allowed_volume_counts_fuel_already_on_the_road():
    # п.5: то, что уже везут, займёт место в резервуаре
    assert sr.allowed_volume_l(20000, 7200, in_transit_l=5000) == 7800


def test_allowed_volume_never_goes_negative():
    assert sr.allowed_volume_l(20000, 19000, in_transit_l=4000) == 0


def test_allowed_volume_uses_max_fill_not_nominal_capacity():
    # Паспортная вместимость 25 000, залить разрешено 20 000 -- считаем по
    # второму числу, иначе резервуар переливается на 5 000 л
    assert sr.allowed_volume_l(20000, 0) == 20000


# ── п.3, п.7: срок достижения минимума ───────────────────────────────

def test_days_to_min_counts_transit_stock():
    assert sr.days_to_min(10000, 4000, 1000, in_transit_l=2000) == 8


def test_days_to_min_is_negative_when_minimum_already_broken():
    assert sr.days_to_min(3000, 4000, 500) == -2


def test_days_to_min_is_none_without_sales():
    assert sr.days_to_min(10000, 4000, 0) is None


# ── п.4.2: потолок запаса в днях ─────────────────────────────────────

def test_target_volume_respects_the_days_cap():
    # минимум 3 000, продажи 1 000/сут, потолок 7 дней -> уровень 10 000,
    # остаток 4 000 -> добор 6 000
    assert sr.target_volume_l(4000, 3000, 1000, 7, 20000) == 6000


def test_target_volume_is_capped_by_the_tank_itself():
    # Резервуар физически не вмещает недельный запас: потолок задаёт железо
    assert sr.target_volume_l(4000, 3000, 1000, 7, 8000) == 4000


def test_cover_days_after_delivery():
    assert sr.cover_days_after(4000, 3000, 1000, delivered_l=6000) == 7


# ── п.4.2: отсек сливается целиком ───────────────────────────────────

def test_pick_sections_takes_whole_compartments_not_a_slice():
    picked, warns = sr.pick_sections(tail_first(sections(5000, 6000, 8000)),
                                     target_l=12000, allowed_l=20000)
    volume = sum(s["volume_l"] for s in picked)
    assert volume == 11000          # 5000 + 6000, а не «12 000 из отсека»
    assert warns == []


def test_pick_sections_never_overfills_the_tank():
    picked, _ = sr.pick_sections(tail_first(sections(5000, 6000, 8000)),
                                 target_l=20000, allowed_l=7000)
    assert sum(s["volume_l"] for s in picked) <= 7000


def test_pick_sections_takes_the_smallest_when_even_it_exceeds_the_days_cap():
    # ТЗ п.4.2, примечание: на мелкой АЗС даже самый маленький отсек
    # продаётся дольше недели. Отказ от поставки хуже превышения запаса.
    picked, warns = sr.pick_sections(tail_first(sections(5000, 8000)),
                                     target_l=1200, allowed_l=9000)
    assert sum(s["volume_l"] for s in picked) == 5000
    assert sr.WARN_COVER_EXCEEDED in warns


def test_pick_sections_refuses_when_even_the_smallest_does_not_fit():
    picked, warns = sr.pick_sections(tail_first(sections(5000, 8000)),
                                     target_l=4000, allowed_l=3000)
    assert picked == []
    assert sr.WARN_NO_ROOM in warns


def test_pick_sections_uses_exact_subset_sum_not_greedy():
    # Жадный алгоритм взял бы 9000 и остановился; точный перебор находит
    # 4000 + 6000 = 10 000 -- ровно под потребность
    picked, _ = sr.pick_sections(tail_first(sections(9000, 6000, 4000)),
                                 target_l=10000, allowed_l=10000)
    assert sum(s["volume_l"] for s in picked) == 10000


# ── маршрут и норматив пробега ───────────────────────────────────────

DIST = {
    ("END", "PARC", "LOAD", 1): 12,
    ("LOAD", 1, "STATION", 10): 40,
    ("LOAD", 1, "STATION", 20): 65,
    ("STATION", 10, "STATION", 20): 30,
    ("STATION", 20, "STATION", 10): 30,
    ("STATION", 20, "END", "PARC"): 70,
    ("STATION", 10, "END", "PARC"): 45,
}


def dist_lookup(fk, fi, tk, ti):
    return DIST.get((fk, fi, tk, ti))


def test_route_km_includes_the_parking_to_terminal_leg():
    km, legs = sr.route_km("PARC", 1, [10, 20], "PARC", dist_lookup)
    assert km == 12 + 40 + 30 + 70
    assert legs[0]["from_kind"] == "END" and legs[0]["km"] == 12


def test_route_km_is_none_when_a_leg_is_missing_from_the_matrix():
    km, legs = sr.route_km("PARC", 1, [10, 99], "PARC", dist_lookup)
    assert km is None
    assert any(leg["km"] is None for leg in legs)


def test_route_order_picks_the_nearest_station_first():
    assert sr.route_order(1, [20, 10], dist_lookup) == [10, 20]


# ── сборка плана ─────────────────────────────────────────────────────

def tank(station_id, product="A95", **kw):
    base = {"tank_id": station_id * 10, "station_id": station_id,
            "product_code": product, "fuel_group": "PETROL",
            "current_l": 4000, "avg_daily_l": 1000, "min_stock_l": 3000,
            "max_fill_l": 20000, "in_transit_l": 0, "max_cover_days": None}
    base.update(kw)
    return base


TRUCK = {"id": 1, "plate": "ABC123", "fuel_group": "PETROL",
         "sections": sections(5000, 5000, 6000, 6000, 8000)}

SETTINGS = {"max_cover_days": 7, "plan_horizon_days": 2,
            "group_max_stations": 4, "load_point_id": 1}


def test_build_needs_skips_stations_that_are_fine():
    tanks = [tank(10, current_l=18000)]          # запаса на 15 дней
    assert sr.build_needs(tanks, 7, horizon_days=2) == []


def test_build_needs_orders_by_urgency():
    tanks = [tank(10, current_l=4500), tank(20, current_l=3200)]
    needs = sr.build_needs(tanks, 7, horizon_days=3)
    assert [n["station_id"] for n in needs] == [20, 10]


def test_build_plan_does_not_mix_petrol_and_diesel_in_one_tanker():
    tanks = [tank(10, product="A95"),
             tank(20, product="DIESEL", fuel_group="DIESEL")]
    plan = sr.build_plan(tanks, [TRUCK], [], SETTINGS, dist_lookup)
    for trip in plan["trips"]:
        products = {l["product_code"] for l in trip["loads"]}
        assert not ({"DIESEL"} & products and products - {"DIESEL"})
    # Дизельной цистерны в парке нет -- дизельная потребность осталась
    # без рейса, но из плана не исчезла
    diesel = [n for n in plan["needs"] if n["product_code"] == "DIESEL"]
    assert diesel and diesel[0]["planned_l"] == 0


def test_build_plan_never_plans_more_than_allowed():
    tanks = [tank(10, current_l=16000)]          # допустимо всего 4 000 л
    plan = sr.build_plan(tanks, [TRUCK], [], dict(SETTINGS, plan_horizon_days=30),
                         dist_lookup)
    for need in plan["needs"]:
        assert need["planned_l"] <= need["allowed_l"] + 1e-6


def test_build_plan_discharges_from_the_tail_towards_the_cab():
    # ТЗ п.4.2, примечание: слив идёт с крайнего хвостового отсека. Значит
    # номера отсеков в порядке разгрузки обязаны убывать: отсек можно
    # оставить пустым, но вернуться к хвостовому после переднего нельзя.
    group = {"id": 1, "code": "NORD", "name": "Nord", "station_ids": [10, 20]}
    tanks = [tank(10), tank(20)]
    plan = sr.build_plan(tanks, [TRUCK], [group], SETTINGS, dist_lookup)
    loads = plan["trips"][0]["loads"]
    assert [l["unload_seq"] for l in loads] == list(range(1, len(loads) + 1))
    numbers = [l["section_no"] for l in loads]
    assert numbers == sorted(numbers, reverse=True), numbers


def test_build_plan_serves_the_first_station_on_the_route_from_the_tail():
    group = {"id": 1, "code": "NORD", "name": "Nord", "station_ids": [10, 20]}
    plan = sr.build_plan([tank(10), tank(20)], [TRUCK], [group], SETTINGS,
                         dist_lookup)
    loads = plan["trips"][0]["loads"]
    first_station = loads[0]["station_id"]
    # АЗС 10 ближе к пункту погрузки -- она первая по маршруту и первая
    # по разгрузке, её отсеки ближе к хвосту
    assert first_station == 10
    tail_of_first = max(l["section_no"] for l in loads if l["station_id"] == 10)
    front_of_second = max((l["section_no"] for l in loads
                           if l["station_id"] == 20), default=0)
    assert tail_of_first > front_of_second


def test_build_plan_groups_several_stations_into_one_trip():
    group = {"id": 1, "code": "NORD", "name": "Nord",
             "station_ids": [10, 20]}
    tanks = [tank(10), tank(20)]
    plan = sr.build_plan(tanks, [TRUCK], [group], SETTINGS, dist_lookup)
    assert len(plan["trips"]) == 1
    assert set(plan["trips"][0]["stations"]) == {10, 20}


def test_build_plan_respects_the_max_stations_per_trip():
    group = {"id": 1, "code": "NORD", "name": "Nord",
             "station_ids": [10, 20, 30, 40, 50]}
    tanks = [tank(sid) for sid in (10, 20, 30, 40, 50)]
    plan = sr.build_plan(tanks, [TRUCK], [group],
                         dict(SETTINGS, group_max_stations=2), dist_lookup)
    assert all(len(t["stations"]) <= 2 for t in plan["trips"])


def test_partly_served_need_is_marked_underfill_not_no_room():
    # Отсеки сливаются целиком, поэтому попасть в цель до литра нельзя.
    # Строка, куда всё же запланирована поставка, не должна помечаться
    # как «нет свободного объёма» -- машина едет.
    truck = {"id": 1, "plate": "AAA", "fuel_group": "PETROL",
             "sections": sections(6000, 6000)}
    tanks = [tank(10, current_l=4000, avg_daily_l=1500, min_stock_l=4500,
                  max_fill_l=20000)]
    plan = sr.build_plan(tanks, [truck], [], SETTINGS, dist_lookup)
    need = plan["needs"][0]
    assert need["planned_l"] > 0
    assert sr.WARN_NO_ROOM not in need["warnings"]
    assert sr.WARN_UNDERFILL in need["warnings"]


def test_build_plan_keeps_a_station_without_free_space_visible():
    tanks = [tank(10, current_l=19800)]          # свободно 200 л
    plan = sr.build_plan(tanks, [TRUCK], [], dict(SETTINGS, plan_horizon_days=30),
                         dist_lookup)
    need = plan["needs"][0]
    assert need["planned_l"] == 0
    assert sr.WARN_NO_ROOM in need["warnings"]


def test_build_plan_reports_cover_days_after_delivery():
    tanks = [tank(10)]
    plan = sr.build_plan(tanks, [TRUCK], [], SETTINGS, dist_lookup)
    need = plan["needs"][0]
    assert need["cover_days_after"] == pytest.approx(
        (need["current_l"] + need["planned_l"] - need["min_stock_l"])
        / need["avg_daily_l"])


def test_build_plan_subtracts_fuel_already_in_transit():
    # 6 000 л уже едут -- потребности нет, повторная заявка не создаётся
    tanks = [tank(10, in_transit_l=6000)]
    plan = sr.build_plan(tanks, [TRUCK], [], SETTINGS, dist_lookup)
    assert plan["needs"] == []
    assert plan["trips"] == []


# ── п.7: проверка ручной правки ──────────────────────────────────────

TANK_STATE = {(10, "A95"): {"allowed_l": 12800}}
SECTION_MAP = {1: {"volume_l": 5000, "seq_no": 1, "truck_id": 1},
               2: {"volume_l": 6000, "seq_no": 2, "truck_id": 1},
               3: {"volume_l": 8000, "seq_no": 3, "truck_id": 1}}


def test_validate_loads_accepts_a_correct_manual_plan():
    loads = [{"section_id": 1, "station_id": 10, "product_code": "A95",
              "volume_l": 5000},
             {"section_id": 2, "station_id": 10, "product_code": "A95",
              "volume_l": 6000}]
    assert sr.validate_loads(loads, TANK_STATE, SECTION_MAP) == []


def test_validate_loads_rejects_an_overfill():
    loads = [{"section_id": 2, "station_id": 10, "product_code": "A95",
              "volume_l": 6000},
             {"section_id": 3, "station_id": 10, "product_code": "A95",
              "volume_l": 8000}]
    problems = sr.validate_loads(loads, TANK_STATE, SECTION_MAP)
    assert any(p["code"] == "overfill" and p["level"] == "error"
               for p in problems)


def test_validate_loads_rejects_more_than_a_compartment_holds():
    loads = [{"section_id": 1, "station_id": 10, "product_code": "A95",
              "volume_l": 7000}]
    problems = sr.validate_loads(loads, TANK_STATE, SECTION_MAP)
    assert any(p["code"] == "over_section" for p in problems)


def test_validate_loads_warns_on_a_partially_discharged_compartment():
    loads = [{"section_id": 1, "station_id": 10, "product_code": "A95",
              "volume_l": 4000}]
    problems = sr.validate_loads(loads, TANK_STATE, SECTION_MAP)
    assert any(p["code"] == sr.WARN_PARTIAL and p["level"] == "warning"
               for p in problems)


def test_validate_loads_rejects_one_compartment_used_twice():
    loads = [{"section_id": 1, "station_id": 10, "product_code": "A95",
              "volume_l": 5000},
             {"section_id": 1, "station_id": 10, "product_code": "A95",
              "volume_l": 5000}]
    problems = sr.validate_loads(loads, TANK_STATE, SECTION_MAP)
    assert any(p["code"] == "section_reused" for p in problems)


def test_validate_loads_rejects_petrol_and_diesel_in_one_tanker():
    loads = [{"section_id": 1, "station_id": 10, "product_code": "A95",
              "volume_l": 5000, "fuel_group": "PETROL"},
             {"section_id": 2, "station_id": 10, "product_code": "DIESEL",
              "volume_l": 6000, "fuel_group": "DIESEL"}]
    problems = sr.validate_loads(loads, TANK_STATE, SECTION_MAP)
    assert any(p["code"] == "mixed_fuel" for p in problems)


# ── DDL контура ──────────────────────────────────────────────────────

def test_supply_ddl_declares_every_new_table():
    text = _sql("125_flt_supply.sql")
    for table in ("FLT_TRUCK_SECTIONS", "FLT_STATION_GROUPS",
                  "FLT_STATION_GROUP_ITEMS", "FLT_TANK_STOCK",
                  "FLT_SUPPLY_PLANS", "FLT_SUPPLY_NEEDS",
                  "FLT_SUPPLY_TRIPS", "FLT_SUPPLY_LOADS"):
        assert f"CREATE TABLE {table}" in text, table


def test_supply_ddl_has_no_semicolons_in_comments():
    # Разделитель команд -- ';', и он не различает код и комментарий:
    # точка с запятой в комментарии режет команду пополам (на этом уже
    # спотыкался DDL модуля SDA).
    for name in ("125_flt_supply.sql", "126_flt_supply_views.sql",
                 "127_flt_supply_seed.sql"):
        for line_no, line in enumerate(_sql(name).splitlines(), 1):
            if line.strip().startswith("--"):
                assert ";" not in line, f"{name}:{line_no}: {line}"


def test_supply_ddl_columns_are_added_under_a_guard():
    text = _sql("125_flt_supply.sql")
    assert "USER_TAB_COLUMNS" in text
    assert "ALTER TABLE" not in re.sub(r"EXECUTE IMMEDIATE .*", "", text)


def test_every_new_id_table_has_a_sequence_and_a_trigger():
    text = _sql("125_flt_supply.sql")
    for table in ("FLT_TRUCK_SECTIONS", "FLT_STATION_GROUPS", "FLT_TANK_STOCK",
                  "FLT_SUPPLY_PLANS", "FLT_SUPPLY_NEEDS", "FLT_SUPPLY_TRIPS",
                  "FLT_SUPPLY_LOADS"):
        assert f"CREATE SEQUENCE SEQ_{table}" in text, table
        assert f"TRG_{table}_BI" in text, table


def test_every_new_trigger_is_fenced_by_slashes():
    import deploy_oracle_objects as shared
    text = _sql("125_flt_supply.sql")
    for block in shared._sql_blocks(text):
        if shared._is_comment_only(block) or not shared._is_plsql_block(block):
            continue
        creates = re.findall(r"(?im)^\s*CREATE\s+(\S+)", block)
        assert creates in ([], ["OR"]), block[:160]


def test_views_file_declares_the_supply_views():
    text = _sql("126_flt_supply_views.sql")
    for view in ("V_FLT_TANK_STATE", "V_FLT_SUPPLY_PLAN", "V_FLT_SUPPLY_LOADS",
                 "V_FLT_TRIP_EXECUTION", "V_FLT_TRIP_PAY"):
        assert f"CREATE OR REPLACE VIEW {view}" in text, view


def test_tank_state_view_subtracts_transit_from_the_allowed_volume():
    text = _sql("126_flt_supply_views.sql")
    body = text.split("CREATE OR REPLACE VIEW V_FLT_TANK_STATE")[1]
    body = body.split("CREATE OR REPLACE VIEW")[0]
    assert "IN_TRANSIT_L" in body and "ALLOWED_L" in body
    assert "GREATEST(" in body            # допустимый объём не бывает отрицательным


def test_pay_view_is_driven_by_the_status_reference_not_by_a_literal():
    text = _sql("126_flt_supply_views.sql")
    body = text.split("CREATE OR REPLACE VIEW V_FLT_TRIP_PAY")[1]
    assert "IS_PAYABLE" in body
    assert "<> 'DRAFT'" not in body


def test_seed_sets_the_new_rate_only_on_an_untouched_contour():
    text = _sql("127_flt_supply_seed.sql")
    assert "RATE_PER_KM = 3.50" in text
    # Ставку, уже исправленную заказчиком вручную, повторный запуск файла
    # затирать не должен
    assert "AND RATE_PER_KM = 2.75" in text


def test_seed_declares_the_execution_chain_of_the_tor():
    text = _sql("127_flt_supply_seed.sql")
    for code in ("PLANNED", "LOAD_REQ", "LOADED", "IN_TRANSIT", "DELIVERED",
                 "ACCEPTED"):
        assert f"'{code}'" in text, code


def test_seed_declares_every_loading_terminal_named_in_the_tor():
    text = _sql("127_flt_supply_seed.sql")
    for name in ("Chisinau", "MSPD", "Constanta", "Burgas", "Ruse", "Navodari"):
        assert name in text, name


def test_seed_is_idempotent_merge_or_guarded_update_only():
    import deploy_oracle_objects as shared
    text = _sql("127_flt_supply_seed.sql")
    for block in shared._sql_blocks(text):
        for stmt in shared._split_ddl_dml(block):
            stmt = stmt.strip()
            if not stmt or shared._is_comment_only(stmt):
                continue
            head = "\n".join(l for l in stmt.splitlines()
                             if not l.strip().startswith("--")).upper().lstrip()
            if head.startswith("MERGE") or head.startswith("COMMIT"):
                continue
            assert head.startswith("UPDATE") or head.startswith("INSERT"), stmt[:80]
            assert "WHERE" in stmt.upper(), stmt[:120]


# ── экономика перевозки (ТЗ автопарка, отчёт руководству) ────────────

def test_economics_counts_overruns_per_trip_not_on_the_period_total():
    # Рейс с перепробегом и рейс с недопробегом не гасят друг друга:
    # лишние километры оплачены, сэкономленные никем не возвращены.
    trips = [
        {"norm_km": 100, "fact_km": 130, "norm_fuel_l": 30, "fact_fuel_l": 40,
         "volume_l": 20000, "capacity_l": 25000, "pay": 350},
        {"norm_km": 100, "fact_km": 70, "norm_fuel_l": 30, "fact_fuel_l": 22,
         "volume_l": 20000, "capacity_l": 25000, "pay": 350},
    ]
    e = sr.transport_economics(trips, rate_per_km=3.5, fuel_price_lei=20)
    assert e["extra_km"] == 30
    assert e["fuel_over_l"] == 10
    assert e["optimization_effect"] == 30 * 3.5 + 10 * 20


def test_economics_cost_per_liter_includes_pay_and_fuel_overrun_only():
    trips = [{"norm_km": 100, "fact_km": 100, "norm_fuel_l": 30, "fact_fuel_l": 35,
              "volume_l": 10000, "capacity_l": 20000, "pay": 350}]
    e = sr.transport_economics(trips, rate_per_km=3.5, fuel_price_lei=20)
    assert e["cost_per_liter"] == round((350 + 5 * 20) / 10000, 4)
    assert e["avg_load_pct"] == 50.0


def test_economics_ignores_trips_without_a_measured_fuel_fact():
    trips = [{"norm_km": 100, "fact_km": 100, "norm_fuel_l": 30, "fact_fuel_l": None,
              "volume_l": 10000, "capacity_l": 10000, "pay": 350}]
    e = sr.transport_economics(trips, rate_per_km=3.5, fuel_price_lei=20)
    assert e["fuel_over_l"] == 0
    assert e["fuel_fact_l"] == 0


def test_driver_rating_ranks_by_percentage_not_by_kilometres():
    drivers = [
        {"driver_id": 1, "full_name": "Дальние рейсы", "total_norm_km": 10000,
         "total_fact_km": 10200},                       # +2 %
        {"driver_id": 2, "full_name": "Городские рейсы", "total_norm_km": 500,
         "total_fact_km": 550},                         # +10 %
    ]
    rating = sr.driver_rating(drivers)
    assert [r["driver_id"] for r in rating] == [1, 2]
    assert rating[0]["extra_pct"] == 2.0


def test_driver_rating_skips_drivers_without_a_fact():
    drivers = [{"driver_id": 1, "full_name": "Без факта", "total_norm_km": 100,
                "total_fact_km": 0}]
    assert sr.driver_rating(drivers) == []


# ── изоляция модуля (правило №1 проекта) ─────────────────────────────

def test_supply_contour_leaves_shared_code_alone():
    """Контур распределения не оставляет следов в общем коде.

    Ни `app.py`, ни общий установщик DDL про него не знают: маршруты
    объявлены на blueprint'е модуля, таблицы ставит собственный
    установщик модуля.
    """
    with open(os.path.join(ROOT, "app.py"), encoding="utf-8") as fh:
        app_py = fh.read()
    # Проверяем по маркерам МОДУЛЯ, а не по голым словам: в общем app.py
    # живёт топливный контур планограмм с классом PecoSupplyController,
    # и подстрока "SupplyController" находится в нём -- к этому модулю
    # она отношения не имеет.
    assert "modules.autopark" not in app_py
    assert "autopark.supply" not in app_py
    assert "FLT_SUPPLY" not in app_py

    with open(os.path.join(ROOT, "deploy_oracle_objects.py"), encoding="utf-8") as fh:
        installer = fh.read()
    for name in ("125_flt_supply.sql", "126_flt_supply_views.sql",
                 "127_flt_supply_seed.sql"):
        assert name not in installer, name


def test_supply_rules_do_not_import_the_database():
    """Правила расчёта проверяются без wallet и без Oracle."""
    with open(os.path.join(ROOT, "modules", "autopark", "supply_rules.py"),
              encoding="utf-8") as fh:
        source = fh.read()
    for forbidden in ("models.database", "DatabaseModel", "oracledb", "import store"):
        assert forbidden not in source, forbidden


def test_supply_routes_are_registered_on_the_module_blueprint():
    from modules.autopark import blueprint
    import modules.autopark.supply_routes  # noqa: F401
    assert blueprint.name == "autopark"
