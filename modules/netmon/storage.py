"""Здоровье дисков сервера баз данных: аппаратный RAID, физические диски, разделы.

Появилось по итогам аудита UPNET 2021, где было замечание «в зеркале MD1
не хватает диска» и «аппаратных RAID-контроллеров нет». Проверка 2026 года
показала, что оба замечания закрыты: стоит контроллер LSI 3108 MegaRAID,
все разделы собраны в зеркала RAID 1. Но закрыты они так, что **обычными
средствами этого не видно**, и здесь кроется ловушка.

Ловушка: для системы существуют только четыре диска `/dev/sda…sdd` — это
логические тома контроллера. `/proc/mdstat` пуст (программных массивов
действительно нет), а `smartctl /dev/sda` опрашивает том, а не железо, и
всегда отвечает «OK». То есть **штатная проверка SMART будет показывать
полное благополучие даже когда в зеркале сдохнет диск.** Первым признаком
станет отказ сервера.

Поэтому спрашиваем сам контроллер через `MegaCli64`: состояние томов,
состояние каждого из восьми физических дисков, счётчики ошибок и
предсказание отказа, температуру и батарею кэша (при её отказе контроллер
выключает отложенную запись, и база резко замедляется без видимой причины).

Разбор аудита: `docs/Netmon/AUDIT_2021_REVIEW.md`, раздел 4.
"""
from __future__ import annotations

import re

from modules.netmon import frontoffice

HOST = frontoffice.DB_HOST
HOST_NAME = frontoffice.DB_HOST_NAME
MEGACLI = "/opt/MegaRAID/MegaCli/MegaCli64"

# Разделы, за заполнением которых следим, и что там лежит. Порядок важен:
# в таком виде выводится на панель.
WATCHED = {
    "/db": "файлы данных Oracle",
    "/opt": "приложения и выгрузки",
    "/mnt/md3": "архивы (имя историческое, программного массива нет)",
    "/mnt/md4": "архивы (имя историческое, программного массива нет)",
    "/": "система",
}

# Порог заполнения. Oracle при нехватке места под архивные журналы
# останавливает запись, а не замедляет её, поэтому предупреждать заранее.
FULL_WARN = 85
FULL_CRIT = 92

# Температура дисков. Seagate и Toshiba в этих корпусах рассчитаны на 5–60 °C;
# 45 °C — повод проверить вентиляцию, 55 °C — сокращение срока службы.
TEMP_WARN = 45
TEMP_CRIT = 55

_COLLECT = r"""
M=%(mega)s
echo '===VD==='; $M -LDInfo -Lall -aALL -NoLog 2>/dev/null
echo '===PD==='; $M -PDList -aALL -NoLog 2>/dev/null
echo '===ADP==='; $M -AdpAllInfo -aALL -NoLog 2>/dev/null
echo '===BBU==='; $M -AdpBbuCmd -GetBbuStatus -aALL -NoLog 2>/dev/null
echo '===MDSTAT==='; cat /proc/mdstat 2>/dev/null
echo '===DF==='; df -P -m 2>/dev/null | tail -n +2
echo '===END==='
"""


def _sections(raw: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    key = None
    for line in raw.splitlines():
        m = re.match(r"^===(\w+)===$", line.strip())
        if m:
            key = m.group(1)
            out[key] = []
        elif key:
            out[key].append(line)
    return out


def _field(line: str) -> tuple[str, str]:
    """Строка MegaCli вида «Ключ  : значение». Двоеточий в значении бывает больше."""
    k, _, v = line.partition(":")
    return k.strip().lower(), v.strip()


def _volumes(lines: list[str]) -> list[dict]:
    """Логические тома контроллера — то, что система видит как /dev/sdX."""
    vols: list[dict] = []
    cur: dict | None = None
    for line in lines:
        m = re.match(r"^Virtual Drive:\s*(\d+)\s*\(Target Id:\s*(\d+)\)", line.strip())
        if m:
            cur = {"id": int(m.group(1)), "target": int(m.group(2)), "name": "",
                   "level": "", "size": "", "state": "", "drives": 0,
                   "cache": "", "bad_blocks": ""}
            vols.append(cur)
            continue
        if cur is None:
            continue
        k, v = _field(line)
        if k == "name":
            cur["name"] = v
        elif k == "raid level":
            # «Primary-1, Secondary-0, RAID Level Qualifier-0» → RAID 1
            p = re.search(r"Primary-(\d+)", v)
            s = re.search(r"Secondary-(\d+)", v)
            lvl = p.group(1) if p else "?"
            if s and s.group(1) != "0":
                lvl += "0"
            cur["level"] = f"RAID {lvl}"
        elif k == "size":
            cur["size"] = v
        elif k == "state":
            cur["state"] = v
        elif k == "number of drives":
            cur["drives"] = int(v) if v.isdigit() else 0
        elif k == "current cache policy":
            cur["cache"] = v
        elif k.startswith("bad blocks"):
            cur["bad_blocks"] = v
    for v in vols:
        v["ok"] = v["state"].lower() == "optimal"
        # зеркало из одного диска зеркалом не является
        v["mirrored"] = v["level"] in ("RAID 1", "RAID 10", "RAID 5", "RAID 6") and v["drives"] > 1
    return vols


def _model(inquiry: str) -> str:
    """Из «31I9KG9TFJKATOSHIBA MG04ACA400E   FP4B» вытащить модель.

    MegaCli склеивает серийный номер, производителя и модель без разделителей;
    режем по известным именам производителей.
    """
    s = re.sub(r"\s+", " ", inquiry).strip()
    m = re.search(r"(TOSHIBA|SEAGATE|ST\d|WDC|HGST|SAMSUNG|INTEL|MICRON|HUS|MG0)\S*.*", s)
    return (m.group(0) if m else s)[:40].strip()


def _physical(lines: list[str]) -> list[dict]:
    """Физические диски за контроллером — те, что реально могут умереть."""
    disks: list[dict] = []
    cur: dict | None = None
    for line in lines:
        k, v = _field(line)
        if k == "slot number":
            cur = {"slot": int(v) if v.isdigit() else -1, "state": "", "model": "",
                   "size": "", "temp": None, "media_errors": 0, "other_errors": 0,
                   "predictive": 0}
            disks.append(cur)
            continue
        if cur is None:
            continue
        if k == "firmware state":
            cur["state"] = v
        elif k == "inquiry data":
            cur["model"] = _model(v)
        elif k == "raw size":
            cur["size"] = v.split("[")[0].strip()
        elif k == "drive temperature":
            t = re.match(r"(\d+)C", v)
            if t:
                cur["temp"] = int(t.group(1))
        elif k == "media error count":
            cur["media_errors"] = int(v) if v.isdigit() else 0
        elif k == "other error count":
            cur["other_errors"] = int(v) if v.isdigit() else 0
        elif k == "predictive failure count":
            cur["predictive"] = int(v) if v.isdigit() else 0
    for d in disks:
        d["ok"] = d["state"].lower().startswith("online")
    return disks


def _adapter(lines: list[str], bbu: list[str]) -> dict:
    a = {"product": "", "memory": "", "degraded": 0, "offline": 0,
         "critical": 0, "failed": 0, "roc_temp": None,
         "bbu_present": False, "bbu_state": "", "bbu_ok": None}
    for line in lines:
        k, v = _field(line)
        if k == "product name":
            a["product"] = v
        elif k == "memory size":
            a["memory"] = v
        elif k == "degraded":
            a["degraded"] = int(v) if v.isdigit() else 0
        elif k == "offline":
            a["offline"] = int(v) if v.isdigit() else 0
        elif k == "critical disks":
            a["critical"] = int(v) if v.isdigit() else 0
        elif k == "failed disks":
            a["failed"] = int(v) if v.isdigit() else 0
        elif k == "roc temperature":
            t = re.match(r"(\d+)", v)
            if t:
                a["roc_temp"] = int(t.group(1))
        elif k == "bbu" and v.lower() in ("present", "yes"):
            a["bbu_present"] = True
    for line in bbu:
        k, v = _field(line)
        if k == "battery state":
            a["bbu_state"] = v
            a["bbu_ok"] = v.lower() == "optimal"
    return a


def _arrays(lines: list[str]) -> list[dict]:
    """Программные массивы. На этом сервере их нет — RAID аппаратный."""
    arrays: list[dict] = []
    cur: dict | None = None
    for line in lines:
        m = re.match(r"^(md\d+)\s*:\s*(\S+)\s+(\S+)\s+(.*)$", line)
        if m:
            cur = {"name": m.group(1), "state": m.group(2), "level": m.group(3),
                   "members": len(re.findall(r"\w+\[\d+\]", m.group(4))),
                   "degraded": False, "status": ""}
            arrays.append(cur)
            continue
        if cur is None:
            continue
        st = re.search(r"\[(\d+)/(\d+)\]\s*\[([U_]+)\]", line)
        if st:
            cur["status"] = f"{st.group(1)}/{st.group(2)} [{st.group(3)}]"
            cur["degraded"] = "_" in st.group(3)
    return arrays


def _mounts(df_lines: list[str]) -> list[dict]:
    seen: dict[str, dict] = {}
    for line in df_lines:
        f = line.split()
        if len(f) < 6 or f[5] not in WATCHED:
            continue
        total = int(f[1]) if f[1].isdigit() else 0
        used = int(f[2]) if f[2].isdigit() else 0
        pct = int(round(used * 100 / total)) if total else 0
        seen[f[5]] = {
            "mount": f[5], "device": f[0], "what": WATCHED[f[5]],
            "total_gb": round(total / 1024, 1), "used_gb": round(used / 1024, 1),
            "free_gb": round((total - used) / 1024, 1), "percent": pct,
            "level": "crit" if pct >= FULL_CRIT else "warn" if pct >= FULL_WARN else "ok",
        }
    return [seen[m] for m in WATCHED if m in seen]


def collect() -> dict:
    raw = frontoffice._ssh(_COLLECT % {"mega": MEGACLI}, timeout=180)
    sec = _sections(raw)
    vols = _volumes(sec.get("VD", []))
    phys = _physical(sec.get("PD", []))
    adp = _adapter(sec.get("ADP", []), sec.get("BBU", []))
    arrays = _arrays(sec.get("MDSTAT", []))
    mounts = _mounts(sec.get("DF", []))
    return {
        "host": HOST, "host_name": HOST_NAME,
        "controller": adp, "volumes": vols, "physical": phys,
        "soft_arrays": arrays, "mounts": mounts,
        "redundancy": bool(vols) and all(v["mirrored"] for v in vols),
        "findings": findings(adp, vols, phys, mounts),
    }


def findings(adp: dict, vols: list[dict], phys: list[dict],
             mounts: list[dict]) -> list[dict]:
    """Что именно не так — словами, а не цифрами.

    Панель показывает этот список как есть: человеку нужен вывод, а не
    таблица, из которой вывод надо делать самому.
    """
    out: list[dict] = []

    if not vols and not phys:
        # Молчание контроллера — само по себе находка, но не повод терять
        # остальные: заполнение разделов и состояние батареи снимаются
        # другими путями и остаются известны.
        out.append({
            "level": "crit", "ref": "аудит 2021, п. 3.1.3",
            "title": "Состояние массивов неизвестно — контроллер не отвечает",
            "text": f"Не удалось опросить {MEGACLI}. Пока контроллер молчит, "
                    "отказ диска в зеркале останется незамеченным: система видит "
                    "только логические тома и всегда считает их здоровыми.",
        })

    for v in vols:
        if not v["ok"]:
            out.append({
                "level": "crit", "ref": "аудит 2021, п. 4.1",
                "title": f"Том {v['id']} «{v['name'] or 'без имени'}» в состоянии {v['state']}",
                "text": f"{v['level']}, {v['size']}. Зеркало неполно или разрушено — "
                        "менять диск немедленно.",
            })
        elif not v["mirrored"]:
            out.append({
                "level": "crit", "ref": "аудит 2021, п. 4.1",
                "title": f"Том {v['id']} без избыточности ({v['level']}, дисков {v['drives']})",
                "text": "Отказ одного диска — потеря всего тома. Резервных копий нет.",
            })
        if v["bad_blocks"].lower() in ("yes", "да"):
            out.append({
                "level": "warn", "ref": "контроллер",
                "title": f"Том {v['id']}: контроллер отметил сбойные блоки",
                "text": "Часть тома не читается. Проверить целостность данных.",
            })

    for d in phys:
        if not d["ok"]:
            out.append({
                "level": "crit", "ref": "контроллер",
                "title": f"Диск в слоте {d['slot']}: состояние «{d['state']}»",
                "text": f"{d['model']}, {d['size']}. Диск выведен из массива — "
                        "зеркало держится на одном диске.",
            })
        if d["predictive"]:
            out.append({
                "level": "crit", "ref": "контроллер, предсказание отказа",
                "title": f"Диск в слоте {d['slot']}: предсказано {d['predictive']} отказов",
                "text": "Контроллер считает, что диск скоро умрёт. Заменить до отказа, "
                        "пока зеркало целое и данные можно перестроить.",
            })
        if d["media_errors"]:
            out.append({
                "level": "warn", "ref": "контроллер",
                "title": f"Диск в слоте {d['slot']}: ошибок чтения {d['media_errors']}",
                "text": "Поверхность сыпется. Число растёт — готовить замену.",
            })
        if d["temp"] and d["temp"] >= TEMP_WARN:
            out.append({
                "level": "crit" if d["temp"] >= TEMP_CRIT else "warn",
                "ref": "температура",
                "title": f"Диск в слоте {d['slot']} нагрелся до {d['temp']} °C",
                "text": "Проверить вентиляторы корпуса и пыль в отсеке дисков.",
            })

    if adp.get("bbu_present") and adp.get("bbu_ok") is False:
        out.append({
            "level": "crit", "ref": "батарея кэша",
            "title": f"Батарея кэша контроллера: {adp['bbu_state']}",
            "text": "При неисправной батарее контроллер отключает отложенную запись, "
                    "и база резко замедляется без видимой причины в логах Oracle.",
        })
    if adp.get("roc_temp") and adp["roc_temp"] >= 80:
        out.append({
            "level": "warn", "ref": "температура контроллера",
            "title": f"Процессор контроллера нагрелся до {adp['roc_temp']} °C",
            "text": "Рабочий предел LSI 3108 — 100 °C. Проверить продув отсека.",
        })

    for m in mounts:
        if m["level"] != "ok":
            out.append({
                "level": m["level"], "ref": "аудит 2021, п. 3.1.5",
                "title": f"{m['mount']} заполнен на {m['percent']} %",
                "text": f"{m['what']}; свободно {m['free_gb']} ГБ. "
                        + ("Oracle при нехватке места под архивные журналы "
                           "останавливает запись." if m["mount"] == "/db"
                           else "Расчистить или перенести."),
            })

    order = {"crit": 0, "warn": 1}
    return sorted(out, key=lambda x: order.get(x["level"], 2))


def summary(data: dict) -> dict:
    p = data.get("physical", [])
    v = data.get("volumes", [])
    f = data.get("findings", [])
    adp = data.get("controller", {})
    return {
        "controller": adp.get("product", "—"),
        "volumes": len(v),
        "volumes_ok": sum(1 for x in v if x["ok"]),
        "disks": len(p),
        "disks_ok": sum(1 for x in p if x["ok"]),
        "redundancy": data.get("redundancy"),
        "bbu": adp.get("bbu_state") or ("нет" if not adp.get("bbu_present") else "—"),
        "temp_max": max((x["temp"] for x in p if x["temp"]), default=None),
        "crit": sum(1 for x in f if x["level"] == "crit"),
        "warn": sum(1 for x in f if x["level"] == "warn"),
        "fullest": max((m["percent"] for m in data.get("mounts", [])), default=0),
    }
