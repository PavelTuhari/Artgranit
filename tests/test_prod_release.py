"""Релиз на прод: анализ различий и точка возврата.

Проверяется классификация файлов — она решает, отправлять ли релиз
вообще. Ошибка здесь стоит чужой работы: файл, помеченный «наша старая
версия» вместо «чужая правка», будет затёрт молча.

Сеть не нужна: обращения к серверу и к git подменяются.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import prod_release as pr  # noqa: E402


@pytest.fixture
def fake(monkeypatch):
    """Подменяет все три источника хэшей: локальный файл, сервер, история git."""
    state = {"local": {}, "remote": {}, "history": {}}
    monkeypatch.setattr(pr, "local_md5", lambda p: state["local"].get(p))
    monkeypatch.setattr(pr, "remote_md5", lambda paths: {p: state["remote"].get(p)
                                                         for p in paths})
    monkeypatch.setattr(pr, "git_history_md5", lambda p, limit=40: state["history"].get(p, set()))
    return state


def test_file_missing_on_the_server_is_new(fake):
    fake["local"]["a.py"] = "aaa"
    report = pr.analyse(["a.py"])
    assert report["new"] == [("a.py", "нет на сервере")]


def test_identical_file_is_skipped(fake):
    fake["local"]["a.py"] = "aaa"
    fake["remote"]["a.py"] = "aaa"
    report = pr.analyse(["a.py"])
    assert [p for p, _ in report["same"]] == ["a.py"]
    assert report["ours"] == [] and report["foreign"] == []


def test_older_version_of_ours_is_safe_to_overwrite(fake):
    # На сервере лежит версия, которая есть в истории нашей ветки:
    # сервер просто отстал, чужого там нет.
    fake["local"]["a.py"] = "new"
    fake["remote"]["a.py"] = "old"
    fake["history"]["a.py"] = {"old", "older"}
    report = pr.analyse(["a.py"])
    assert [p for p, _ in report["ours"]] == ["a.py"]
    assert report["foreign"] == []


def test_version_absent_from_our_history_is_foreign(fake):
    # Такой версии в нашей ветке никогда не было -- значит её выкатили
    # из другой ветки, и трогать файл нельзя.
    fake["local"]["a.py"] = "new"
    fake["remote"]["a.py"] = "somebody-elses"
    fake["history"]["a.py"] = {"old"}
    report = pr.analyse(["a.py"])
    assert [p for p, _ in report["foreign"]] == ["a.py"]


def test_file_missing_locally_is_reported_not_deleted(fake):
    fake["remote"]["gone.py"] = "x"
    report = pr.analyse(["gone.py"])
    assert [p for p, _ in report["missing_local"]] == ["gone.py"]
    # Инструмент ничего не удаляет на сервере: файла нет в списке отправки
    assert report["new"] == [] and report["ours"] == []


def test_read_paths_drops_the_customer_documents(tmp_path):
    listing = tmp_path / "release.txt"
    listing.write_text("modules/autopark/store.py\n"
                       "docs/Planograms/Bemol2/ТЗ.docx\n"
                       "# комментарий\n\n"
                       "tests/test_autopark.py\n", encoding="utf-8")

    class Args:
        paths_from = str(listing)
        path = None
        commits = 1

    assert pr.read_paths(Args()) == ["modules/autopark/store.py",
                                     "tests/test_autopark.py"]


def test_deploy_constants_point_at_the_nufarul_contour():
    # Инструмент рассчитан на nufarul. Контур officeplus обновляется
    # отдельно и только с разрешения владельца (CLAUDE.md).
    assert pr.REMOTE_HOST == "92.5.3.187"
    assert pr.REMOTE_DIR == "/home/ubuntu/artgranit"
    assert "nufarul" in pr.HEALTH_URL
    assert pr.SERVICE == "artgranit"


def test_backups_are_kept_but_not_forever():
    assert 3 <= pr.KEEP_BACKUPS <= 30
