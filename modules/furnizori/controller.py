"""Контроллер модуля Работа с поставщиками: валидация и сборка ответов.

Возвращает (payload, http_status). SQL — только в store.py, чистые правила —
в rules.py (тестируются без wallet).
"""
from modules.furnizori import rules, store


def _err(msg, code=400):
    return {"success": False, "message": msg}, code


class FurnizoriController:
    # ------------------------------------------------------------ справки
    @staticmethod
    def status():
        try:
            data = store.counters()
        except Exception as e:  # noqa: BLE001 — наружу только текст
            return {"success": False, "message": str(e)}, 500
        return {"success": True, "data": data, "rules_version": rules.VERSION}, 200

    @staticmethod
    def reference():
        """Справочники для интерфейса: поставщики, статусы, типы."""
        try:
            sup = store.suppliers()
        except Exception as e:  # noqa: BLE001
            return _err(str(e), 500)
        return {"success": True, "data": {
            "suppliers": sup,
            "statuses": [{"code": s, "label": rules.STATUS_LABEL[s]} for s in rules.STATUSES],
            "tipuri": [{"code": t, "label": rules.TIP_LABEL[t]} for t in rules.TIPURI],
        }}, 200

    # ------------------------------------------------------------- письма
    @staticmethod
    def letters(status=None):
        if status and not rules.valid_status(status):
            return _err("Неизвестный статус")
        try:
            rows = store.list_letters(rules.normalize_code(status) if status else None)
            for r in rows:
                r["STATUS_LABEL"] = rules.STATUS_LABEL.get(r.get("STATUS"), r.get("STATUS"))
                r["TIP_LABEL"] = rules.TIP_LABEL.get(r.get("TIP"), r.get("TIP"))
        except Exception as e:  # noqa: BLE001
            return _err(str(e), 500)
        return {"success": True, "data": rows}, 200

    @staticmethod
    def create(payload, user=None):
        furn = (payload.get("furnizor") or "").strip()
        subj = (payload.get("subiect") or "").strip()
        if not furn:
            return _err("Не указан поставщик")
        if not subj:
            return _err("Не указана тема письма")
        tip = rules.normalize_code(payload.get("tip") or "GENERAL")
        if not rules.valid_tip(tip):
            return _err("Неизвестный тип письма")
        try:
            lid = store.create_letter({
                "src_code": rules.normalize_code(payload.get("src_code")) or None,
                "cod_org": payload.get("cod_org") or None,
                "furnizor": furn[:160], "subiect": subj[:400], "tip": tip,
                "n_pozitii": payload.get("n_pozitii") or None,
                "sent_to": (payload.get("sent_to") or "").strip()[:200] or None,
                "notes": (payload.get("notes") or "").strip()[:2000] or None,
            }, user)
        except Exception as e:  # noqa: BLE001
            return _err(str(e), 500)
        return {"success": True, "data": {"letter_id": lid}}, 201

    @staticmethod
    def update(letter_id, payload):
        fields = {}
        if "status" in payload:
            st = rules.normalize_code(payload["status"])
            if not rules.valid_status(st):
                return _err("Неизвестный статус")
            fields["status"] = st
        if "tip" in payload:
            tp = rules.normalize_code(payload["tip"])
            if not rules.valid_tip(tp):
                return _err("Неизвестный тип письма")
            fields["tip"] = tp
        for key, limit in (("sent_to", 200), ("notes", 2000),
                           ("furnizor", 160), ("subiect", 400)):
            if key in payload:
                fields[key] = (payload[key] or "").strip()[:limit] or None
        if not fields:
            return _err("Нечего изменять")
        try:
            ok = store.update_letter(letter_id, fields)
        except Exception as e:  # noqa: BLE001
            return _err(str(e), 500)
        return ({"success": True}, 200) if ok else _err("Письмо не найдено", 404)

    @staticmethod
    def remove(letter_id):
        try:
            ok = store.delete_letter(letter_id)
        except Exception as e:  # noqa: BLE001
            return _err(str(e), 500)
        return ({"success": True}, 200) if ok else _err("Письмо не найдено", 404)

    # ---------------------------------------------------------- вложения
    @staticmethod
    def files(letter_id):
        try:
            return {"success": True, "data": store.list_files(letter_id)}, 200
        except Exception as e:  # noqa: BLE001
            return _err(str(e), 500)

    @staticmethod
    def upload(letter_id, filename, blob, user=None):
        why = rules.check_upload(filename, len(blob or b""))
        if why:
            return _err(why)
        if not store.get_letter(letter_id):
            return _err("Письмо не найдено", 404)
        try:
            fid = store.add_file(letter_id, rules.safe_filename(filename), blob, user)
        except Exception as e:  # noqa: BLE001
            return _err(str(e), 500)
        return {"success": True, "data": {"file_id": fid}}, 201

    @staticmethod
    def drop_file(file_id):
        try:
            ok = store.delete_file(file_id)
        except Exception as e:  # noqa: BLE001
            return _err(str(e), 500)
        return ({"success": True}, 200) if ok else _err("Файл не найден", 404)
