"""
Iute API client (REST API).
See: https://iute-core-partner-gateway.iute.eu/docs/public/guide.html
"""
from __future__ import annotations

from typing import Any

import requests

TIMEOUT = 30


def check_auth(
    base_url: str,
    api_key: str,
) -> dict[str, Any]:
    """
    GET /api/v1/physical-api-partners/me: проверка авторизации и получение информации о партнёре.
    Returns: { "success": bool, "data": { "partnerId": str, "posId": str, "products": [...] }, "error": str? }
    """
    url = base_url.rstrip("/") + "/api/v1/physical-api-partners/me"
    headers = {"Authorization": api_key}
    try:
        r = requests.get(url, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return {
            "success": True,
            "data": {
                "partnerId": data.get("partnerId", ""),
                "posId": data.get("posId", ""),
                "products": data.get("products", []),
            },
        }
    except requests.RequestException as e:
        return {"success": False, "data": {}, "error": str(e)}


def create_order(
    base_url: str,
    api_key: str,
    *,
    order_id: str = "test-order-001",
    myiute_phone: str = "+37369123456",
    total_amount: int | float = 1000,
    currency: str = "EUR",
    pos_identifier: str = "",
    salesman_identifier: str = "",
    user_pin: str | None = None,
    birthday: str | None = None,
    gender: str | None = None,
    items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """
    POST /api/v1/physical-api-partners/order: создание или обновление заказа.
    Returns: { "success": bool, "data": { "status": str, "message": str, "myiuteCustomer": bool }, "error": str? }
    """
    url = base_url.rstrip("/") + "/api/v1/physical-api-partners/order"
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json;charset=UTF-8",
    }
    payload = {
        "orderId": order_id,
        "myiutePhone": myiute_phone,
        "totalAmount": int(total_amount),
        "currency": currency,
        "merchant": {
            "posIdentifier": pos_identifier,
            "salesmanIdentifier": salesman_identifier,
            "userConfirmationUrl": None,
            "userCancelUrl": None,
        },
        "shippingAmount": None,
        "taxAmount": None,
        "subtotal": None,
        "userPin": user_pin,
        "birthday": birthday,
        "gender": gender,
        "shipping": None,
        "billing": None,
        "items": items or [],
        "discounts": None,
        "metadata": None,
    }
    try:
        r = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT)
        data = r.json() if r.text else {}
        if r.status_code == 200:
            return {
                "success": True,
                "data": {
                    "status": data.get("status", "PENDING"),
                    "message": data.get("message", "Order created"),
                    "myiuteCustomer": data.get("myiuteCustomer", False),
                },
            }
        elif r.status_code == 404:
            # Customer not exists
            return {
                "success": True,
                "data": {
                    "status": data.get("status", "CUSTOMER_NOT_EXISTS"),
                    "message": data.get("message", "Customer not found"),
                    "myiuteCustomer": data.get("myiuteCustomer", False),
                },
            }
        else:
            return {
                "success": False,
                "data": {
                    "status": data.get("status", "ERROR"),
                    "message": data.get("message", f"HTTP {r.status_code}"),
                    "myiuteCustomer": False,
                },
                "error": f"HTTP {r.status_code}: {data.get('message', r.text)}",
            }
    except requests.RequestException as e:
        return {
            "success": False,
            "data": {"status": "ERROR", "message": str(e), "myiuteCustomer": False},
            "error": str(e),
        }


def get_order_status(
    base_url: str,
    api_key: str,
    order_id: str,
) -> dict[str, Any]:
    """
    GET /api/v1/physical-api-partners/orders/{orderId}/status: проверка статуса заказа.
    Returns: { "success": bool, "data": { "orderId": str, "status": str, "productName": str?, "loanDuration": str? }, "error": str? }
    """
    if not (order_id or "").strip():
        return {
            "success": False,
            "data": {"orderId": "", "status": "", "productName": None, "loanDuration": None},
            "error": "Order ID required",
        }
    url = base_url.rstrip("/") + f"/api/v1/physical-api-partners/orders/{order_id}/status"
    headers = {"Authorization": api_key}
    try:
        r = requests.get(url, headers=headers, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        return {
            "success": True,
            "data": {
                "orderId": data.get("orderId", order_id),
                "status": data.get("status", ""),
                "productName": data.get("productName"),
                "loanDuration": data.get("loanDuration"),
            },
        }
    except requests.RequestException as e:
        return {
            "success": False,
            "data": {"orderId": order_id, "status": "", "productName": None, "loanDuration": None},
            "error": str(e),
        }
