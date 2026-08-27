"""Тесты автопостинга и двуязычных постов-разделов."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from unittest.mock import MagicMock, patch  # noqa: E402


# ── ключи и настройка площадок ─────────────────────────────────────────

def test_settings_keys_are_uppercase_like_in_the_database():
    """get_setting сравнивает точно: строчные ключи не находят ничего —
    на этом отправка в Telegram и не сработала с первого раза."""
    from modules.social import channels
    src = pathlib.Path(channels.__file__).read_text(encoding="utf-8")
    assert '"NOTIFY_TG_TOKEN"' in src and '"NOTIFY_TG_CHAT"' in src
    assert '"notify_tg_token"' not in src


def test_network_is_off_until_its_key_is_filled():
    from modules.social import channels
    with patch.object(channels, "_setting", lambda k, d="": "1" if k.endswith("ENABLED") else ""):
        assert channels.enabled("facebook") is False
    def filled(k, d=""):
        return "1" if k.endswith("ENABLED") else "секрет"
    with patch.object(channels, "_setting", filled):
        assert channels.enabled("facebook") is True


def test_publish_reports_each_network_separately():
    from modules.social import channels
    fake = {"telegram": lambda *a, **k: {"success": True},
            "vk": lambda *a, **k: {"success": False, "error": "нет ключа"}}
    with patch.dict(channels.SENDERS, fake), \
         patch.object(channels, "send_telegram", fake["telegram"]), \
         patch.object(channels, "send_vk", fake["vk"]):
        r = channels.publish({"text": "x"}, networks=["telegram", "vk"])
    assert r["telegram"]["success"] is True
    assert r["vk"]["success"] is False


def test_a_broken_network_does_not_stop_the_others():
    from modules.social import channels
    def boom(*a, **k):
        raise RuntimeError("сеть недоступна")
    ok = lambda *a, **k: {"success": True}
    with patch.dict(channels.SENDERS, {"telegram": boom, "vk": ok}), \
         patch.object(channels, "send_telegram", boom), \
         patch.object(channels, "send_vk", ok):
        r = channels.publish({"text": "x"}, networks=["telegram", "vk"])
    assert r["telegram"]["success"] is False
    assert r["vk"]["success"] is True


def test_instagram_refuses_without_an_image():
    """Instagram не публикует текстом — сообщаем это, а не молчим."""
    from modules.social import channels
    with patch.object(channels, "_setting", lambda k, d="": "секрет"):
        r = channels.send_instagram("текст", image_url="")
    assert r["success"] is False and "изображение" in r["error"]


# ── расписание ─────────────────────────────────────────────────────────

def test_autopost_is_off_by_default_and_once_a_day(monkeypatch):
    """Публикация в чужие сети не должна включаться сама собой."""
    import datetime
    from modules.social import scheduler
    vals = {}
    monkeypatch.setattr(scheduler, "_setting", lambda k, d="": vals.get(k, d))
    assert scheduler.due() is False                    # по умолчанию выключено

    vals.update({scheduler.K_ENABLED: "1", scheduler.K_HOUR: "10",
                 scheduler.K_LAST: ""})

    class _Now(datetime.datetime):
        @classmethod
        def now(cls):
            return cls(2026, 8, 26, 11, 0)
    monkeypatch.setattr(scheduler.datetime, "datetime", _Now)
    assert scheduler.due() is True
    vals[scheduler.K_LAST] = "2026-08-26"
    assert scheduler.due() is False, "второй раз за день публиковать нельзя"


def test_monday_is_bestsellers_other_days_a_section(monkeypatch):
    import datetime
    from modules.social import content

    class _Mon(datetime.date):
        @classmethod
        def today(cls):
            return cls(2026, 8, 24)          # понедельник
    monkeypatch.setattr(content.datetime, "date", _Mon)
    monkeypatch.setattr(content, "bestsellers_post", lambda l: {"kind": "bestsellers"})
    monkeypatch.setattr(content, "section_post", lambda l: {"kind": "section"})
    assert content.today_post()["kind"] == "bestsellers"

    class _Tue(datetime.date):
        @classmethod
        def today(cls):
            return cls(2026, 8, 25)
    monkeypatch.setattr(content.datetime, "date", _Tue)
    assert content.today_post()["kind"] == "section"


# ── двуязычные посты-разделы ───────────────────────────────────────────

def test_generator_builds_both_languages():
    src = (pathlib.Path(__file__).resolve().parent.parent
           / "modules/seoforge/scripts/wp_category_posts.py").read_text(encoding="utf-8")
    assert 'for lang in ("ro", "ru")' in src
    assert '"-ru"' in src, "у русской версии должен быть свой адрес"
    # русские названия берутся из справочника, а не машинного перевода
    assert "YBIRO_GRP_I18N" in src


def test_zero_price_never_reaches_the_text():
    """«от 0 lei» — обещание, которого магазин не выполняет."""
    src = (pathlib.Path(__file__).resolve().parent.parent
           / "modules/seoforge/scripts/wp_category_posts.py").read_text(encoding="utf-8")
    assert "CEIL(MIN(" in src, "минимальная цена округляется вверх"
    assert "> 0 " in src, "нулевая цена отсеивается запросом"
