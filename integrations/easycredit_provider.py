"""
EasyCredit провайдер — обёртка над easycredit_client.py с единым интерфейсом CreditProvider.
"""
from __future__ import annotations

from typing import Any

from integrations.base_provider import CreditProvider
from config import Config


class EasyCreditProvider(CreditProvider):
    """EasyCredit (Moldova) — SOAP API."""

    @property
    def id(self) -> str:
        return "easycredit"

    @property
    def name(self) -> str:
        return "EasyCredit"

    @property
    def icon(self) -> str:
        return "💳"

    @property
    def color(self) -> str:
        return "#667eea"

    @property
    def description(self) -> str:
        return "EasyCredit Moldova — SOAP API (Preapproved, Submit, Status, ClientInfo)"

    @property
    def capabilities(self) -> list[str]:
        return ["search_client", "preapproved", "submit", "status"]

    # --- Настройки ---

    def _base_url(self) -> str:
        return self._setting("base_url", Config.easycredit_base_url)

    def _user(self) -> str:
        return self._setting("api_user", Config.easycredit_api_user)

    def _password(self) -> str:
        return self._setting("api_password", Config.easycredit_api_password)

    def _basic_user(self) -> str:
        return self._setting("basic_user", Config.easycredit_basic_user)

    def _basic_password(self) -> str:
        return self._setting("basic_password", Config.easycredit_basic_password)

    # RO: identificatorii pe care ii atribuie EasyCredit contului de partener.
    #     Nu au valori implicite rezonabile — se introduc in back-office.
    def _shop_id(self) -> str:
        return self._setting("shop_id", "")

    def _product_id(self) -> str:
        return self._setting("product_id", "")

    def _first_installment_days(self) -> int:
        try:
            return int(self._setting("first_installment_days", "") or 31)
        except (TypeError, ValueError):
            return 31

    def _api(self):
        """RO: gateway-ul nou (api.ecredit.md) e REST; cel vechi ramine SOAP.
        EN: the new gateway is REST/JSON; the legacy one stays SOAP."""
        if "api.ecredit.md" in (self._base_url() or ""):
            from integrations import easycredit_rest as api
        else:
            from integrations import easycredit_client as api
        return api

    def _verify_ssl(self) -> bool:
        """RO: gateway-ul nou (api.ecredit.md) are certificat valid — verificam
        TLS mereu. Doar serviciul vechi de test are certificat self-signed.
        EN: the new gateway has a valid certificate, so always verify TLS;
        only the legacy test service needs the exception."""
        if "api.ecredit.md" in (self._base_url() or ""):
            return True
        return self._env() == "production"

    def _env(self) -> str:
        return self._setting("env", Config.easycredit_env) or "sandbox"

    def get_settings(self) -> dict[str, Any]:
        user = self._user()
        return {
            "env": self._env(),
            "base_url": self._base_url(),
            "user": (user[:3] + "***") if user else "",
            "has_password": bool(self._password()),
        }

    def is_configured(self) -> bool:
        return bool(self._base_url() and self._user() and self._password())

    # --- Тестовые клиенты ---

    def get_test_clients(self) -> list[dict[str, Any]]:
        return [
            {
                "fio": "Иванов Иван Иванович",
                "id_number": "2000000000001",
                "phone": "+37369000001",
                "amount": 15000,
                "currency": "MDL",
            },
            {
                "fio": "Петров Пётр Петрович",
                "id_number": "2000000000002",
                "phone": "+37369000002",
                "amount": 25000,
                "currency": "MDL",
            },
            {
                "fio": "Сидоров Сидор Сидорович",
                "id_number": "2000000000003",
                "phone": "+37369000003",
                "amount": 35000,
                "currency": "MDL",
            },
        ]

    # --- Операции ---

    def search_client(self, **kwargs) -> dict[str, Any]:
        """Поиск клиента по UIN (IDNP). kwargs: uin."""
        uin = kwargs.get("uin", "")
        if not uin:
            return {"success": False, "error": "UIN (IDNP) не указан"}

        if not self.is_configured():
            return {"success": False, "error": "EasyCredit не настроен (нет user/password)"}

        try:
            return self._api().get_client_info(
                self._base_url(), self._user(), self._password(),
                uin=uin, verify_ssl=self._verify_ssl(),
                basic_user=self._basic_user(),
                basic_password=self._basic_password()
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    def preapproved(self, **kwargs) -> dict[str, Any]:
        """Проверка предодобренной суммы. kwargs: uin, amount, phone, birth_date."""
        uin = kwargs.get("uin", "12345678901234")
        amount = int(kwargs.get("amount", 10000))

        if not self.is_configured():
            return {"success": False, "error": "EasyCredit не настроен"}

        try:
            return self._api().preapproved(
                self._base_url(), self._user(), self._password(),
                idn=uin, amount=amount,
                phone=kwargs.get("phone", ""),
                birth_date=kwargs.get("birth_date", ""),
                verify_ssl=self._verify_ssl(),
                basic_user=self._basic_user(),
                basic_password=self._basic_password()
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    def submit(self, **kwargs) -> dict[str, Any]:
        """Отправка заявки. kwargs: fio, phone, uin, amount, product_name, program_name, goods_price."""
        if not self.is_configured():
            return {"success": False, "error": "EasyCredit не настроен"}

        try:
            return self._api().submit_request(
                self._base_url(), self._user(), self._password(),
                amount=int(kwargs.get("amount", 10000)),
                fio=kwargs.get("fio", "Тест Тестович Тестов"),
                phone=kwargs.get("phone", "+37369123456"),
                idn=kwargs.get("uin", "12345678901234"),
                birth_date=kwargs.get("birth_date", ""),
                product_name=kwargs.get("product_name", "Тестовый товар"),
                program_name=kwargs.get("program_name", "0-0-12"),
                goods_price=int(kwargs.get("goods_price", kwargs.get("amount", 10000))),
                # RO: Request_v4 (cont de partener) cere ProductID + ShopID
                product_id=self._product_id(),
                shop_id=self._shop_id(),
                first_installment_days=self._first_installment_days(),
                months=int(kwargs.get("months") or 0),
                verify_ssl=self._verify_ssl(),
                basic_user=self._basic_user(),
                basic_password=self._basic_password(),
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    def check_status(self, **kwargs) -> dict[str, Any]:
        """Проверка статуса заявки по URN. kwargs: urn."""
        urn = kwargs.get("urn", "")
        if not urn:
            return {"success": False, "error": "URN не указан"}

        if not self.is_configured():
            return {"success": False, "error": "EasyCredit не настроен"}

        try:
            return self._api().status(
                self._base_url(), self._user(), self._password(),
                urn=urn, verify_ssl=self._verify_ssl(),
                basic_user=self._basic_user(),
                basic_password=self._basic_password()
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
