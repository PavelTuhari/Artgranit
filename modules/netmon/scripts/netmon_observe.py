#!/usr/bin/env python3
"""Фоновый процесс «серьёзного наблюдения»: замер нагрузки каждые N секунд в SQLite.

Запускает и останавливает его панель (кнопка на вкладке «Нагрузка БД»), но
можно и руками:

    python modules/netmon/scripts/netmon_observe.py          # работать, пока не остановят
    python modules/netmon/scripts/netmon_observe.py --once   # один замер и выйти

Почему отдельный процесс, а не поток в веб-сервере: локальный Flask в режиме
отладки перезапускается при каждой правке кода и убил бы наблюдение на
середине. Процесс отвязан от сервера и страницы — закрытая вкладка браузера
наблюдение не прерывает.

Остановка — тремя путями, любой срабатывает:
  * панель пишет control.desired = 'stopped' — процесс видит это на
    следующем замере и выходит сам;
  * прошло max_hours часов — выходит сам, чтобы забытое наблюдение не
    нагружало сервер бесконечно;
  * SIGTERM.

Интервал перечитывается из настроек на каждом замере: изменение в панели
действует сразу, без перезапуска.
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(ROOT / ".env")

from modules.netmon import observe_store as store  # noqa: E402
from modules.netmon.observe_sampler import Sampler  # noqa: E402

_stop = False


def _on_term(*_):
    global _stop
    _stop = True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    a = ap.parse_args()
    signal.signal(signal.SIGTERM, _on_term)
    signal.signal(signal.SIGINT, _on_term)

    started = time.time()
    store.set_control(desired="running", pid=os.getpid(), started_at=started, heartbeat=started,
                      last_error=None, samples=0)
    sampler = Sampler()
    errors_in_row = 0
    tick = 0
    try:
        while not _stop:
            cfg = store.get_settings()
            t0 = time.monotonic()
            try:
                s = sampler.sample()
                if s is not None:
                    store.save_sample(s)
                    if a.once:
                        break
                else:
                    store.set_control(heartbeat=time.time())
                errors_in_row = 0
            except Exception as e:  # noqa: BLE001
                errors_in_row += 1
                store.set_control(last_error=f"{time.strftime('%H:%M:%S')} {type(e).__name__}: {e}"[:400],
                                  heartbeat=time.time())
                sampler.close()            # следующее обращение переподключится
                if errors_in_row >= 20:
                    raise RuntimeError("20 сбоев подряд — наблюдение остановлено") from e
            tick += 1
            if tick % 200 == 0:
                store.prune(cfg["retention_days"])
            ctl = store.control()
            if ctl["desired"] != "running" or ctl["pid"] != os.getpid():
                break                      # остановили из панели или запущен другой процесс
            if time.time() - started > cfg["max_hours"] * 3600:
                store.set_control(last_error=f"остановлено по таймеру: {cfg['max_hours']} ч")
                break
            # ждём остаток интервала, но проверяем остановку каждые полсекунды
            wait = cfg["interval_sec"] - (time.monotonic() - t0)
            end = time.monotonic() + max(wait, 0)
            while not _stop and time.monotonic() < end:
                time.sleep(min(0.5, end - time.monotonic()))
    except Exception as e:  # noqa: BLE001
        store.set_control(last_error=f"{type(e).__name__}: {e}"[:400])
        traceback.print_exc()
    finally:
        sampler.close()
        ctl = store.control()
        if ctl["pid"] == os.getpid():
            store.set_control(desired="stopped", pid=None)


if __name__ == "__main__":
    main()
