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
        return Config.easycredit_base_url()

    def _user(self) -> str:
        return Config.easycredit_api_user()

    def _password(self) -> str:
        return Config.easycredit_api_password()

    def _verify_ssl(self) -> bool:
        return Config.easycredit_env() == "production"

    def get_settings(self) -> dict[str, Any]:
        user = self._user()
        return {
            "env": Config.easycredit_env(),
            "base_url": self._base_url(),
            "user": (user[:3] + "***") if user else "",
            "has_password": bool(self._password()),
        }

    def is_configured(self) -> bool:
        return bool(self._user() and self._password())

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
            from integrations.easycredit_client import get_client_info
            return get_client_info(
                self._base_url(), self._user(), self._password(),
                uin=uin, verify_ssl=self._verify_ssl()
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
            from integrations.easycredit_client import preapproved as ec_preapproved
            return ec_preapproved(
                self._base_url(), self._user(), self._password(),
                idn=uin, amount=amount,
                phone=kwargs.get("phone", ""),
                birth_date=kwargs.get("birth_date", ""),
                verify_ssl=self._verify_ssl()
            )
        except Exception as e:
            return {"success": False, "error": str(e)}

    def submit(self, **kwargs) -> dict[str, Any]:
        """Отправка заявки. kwargs: fio, phone, uin, amount, product_name, program_name, goods_price."""
        if not self.is_configured():
            return {"success": False, "error": "EasyCredit не настроен"}

        try:
            from integrations.easycredit_client import submit_request as ec_submit
            return ec_submit(
                self._base_url(), self._user(), self._password(),
                amount=int(kwargs.get("amount", 10000)),
                fio=kwargs.get("fio", "Тест Тестович Тестов"),
                phone=kwargs.get("phone", "+37369123456"),
                idn=kwargs.get("uin", "12345678901234"),
                product_name=kwargs.get("product_name", "Тестовый товар"),
                program_name=kwargs.get("program_name", "0-0-12"),
                goods_price=int(kwargs.get("goods_price", kwargs.get("amount", 10000))),
                verify_ssl=self._verify_ssl(),
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
            from integrations.easycredit_client import status as ec_status
            return ec_status(
                self._base_url(), self._user(), self._password(),
                urn=urn, verify_ssl=self._verify_ssl()
            )
        except Exception as e:
            return {"success": False, "error": str(e)}
