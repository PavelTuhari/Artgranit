"""
EasyCredit SOAP API client (Preapproved, Request, URNStatus).
Based on WSDL from tst.ecmoldova.cloud:8082 (test) / w81.ecredit.md:8082 (prod).
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

import requests

NS_SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
NS_TEMP = "http://tempuri.org/"
NS_DATA = "http://schemas.datacontract.org/2004/07/"
TIMEOUT = 30


def _soap_post(url: str, action: str, body_el: str, verify_ssl: bool = True) -> requests.Response:
    envelope = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<s:Envelope xmlns:s="' + NS_SOAP + '">'
        "<s:Body>" + body_el + "</s:Body>"
        "</s:Envelope>"
    )
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": '"' + action + '"',
    }
    return requests.post(url, data=envelope.encode("utf-8"), headers=headers, timeout=TIMEOUT, verify=verify_ssl)


def _el(tag: str, text: str | None = None) -> str:
    """Create XML element with optional text content."""
    if text is None or text == "":
        return f"<{tag}/>"
    safe = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    return f"<{tag}>{safe}</{tag}>"


def _parse_soap_response(text: str, result_tag: str) -> dict[str, Any] | None:
    """Parse SOAP response and extract result element."""
    try:
        root = ET.fromstring(text)
        # Find result element (may be namespaced)
        for el in root.iter():
            tag = el.tag or ""
            if result_tag in tag or tag.endswith("}" + result_tag):
                result = {}
                for child in el:
                    child_tag = child.tag.split("}")[-1] if "}" in (child.tag or "") else child.tag
                    # Handle nil values
                    nil = child.attrib.get("{http://www.w3.org/2001/XMLSchema-instance}nil", "false")
                    if nil.lower() == "true":
                        result[child_tag] = None
                    else:
                        result[child_tag] = (child.text or "").strip()
                if result:
                    return result
                # If no children, return text content
                raw = (el.text or "").strip()
                if raw:
                    return {"Result": raw, "value": raw}
        return None
    except ET.ParseError:
        return None


def _parse_fault(text: str) -> str | None:
    """Extract SOAP fault message."""
    try:
        root = ET.fromstring(text)
        for n in root.iter():
            if n.tag and "faultstring" in (n.tag or "").lower():
                return (n.text or "").strip()
        return None
    except ET.ParseError:
        return None


def preapproved(
    base_url: str,
    user: str,
    passwd: str,
    idn: str = "12345678901234",
    amount: int | float = 10000,
    phone: str = "",
    birth_date: str = "",
    card_id: str = "",
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """
    Preapproved_v2.1: проверка предодобренной суммы.
    
    WSDL fields: Login, Password, UIN, BirthDate, Phone, cardid
    SOAPAction: http://tempuri.org/IPreapproved_v2_1/Preapproved
    
    Returns: { "success": bool, "data": { "preapproved": bool, "max_amount": int, "status": str, "message": str }, "error": str? }
    """
    url = (base_url.rstrip("/") + "/Preapproved_v2.1.svc").replace(".svc.svc", ".svc")
    action = "http://tempuri.org/IPreapproved_v2_1/Preapproved"
    
    body = (
        '<Preapproved xmlns="' + NS_TEMP + '">'
        + _el("Login", user)
        + _el("Password", passwd)
        + _el("UIN", idn or "12345678901234")
        + _el("BirthDate", birth_date)
        + _el("Phone", phone)
        + _el("cardid", card_id)
        + "</Preapproved>"
    )
    
    try:
        r = _soap_post(url, action, body, verify_ssl=verify_ssl)
        r.raise_for_status()
        
        parsed = _parse_soap_response(r.text, "PreapprovedResult")
        if parsed:
            status = parsed.get("Status") or ""
            max_reuseste = int(parsed.get("MaxAutoApproveAmountForReuseste") or 0)
            max_esimplu = int(parsed.get("MaxAutoApproveAmountForeSimplu") or 0)
            max_amount = max(max_reuseste, max_esimplu)
            
            # "Wrong Customer" means not found, anything else might be approved
            is_approved = max_amount > 0 and "Wrong" not in status
            
            return {
                "success": True,
                "data": {
                    "preapproved": is_approved,
                    "max_amount": max_amount,
                    "max_reuseste": max_reuseste,
                    "max_esimplu": max_esimplu,
                    "status": status,
                    "message": status or ("Предодобрено." if is_approved else "Не предодобрено."),
                    "first_name": parsed.get("FirstName"),
                    "last_name": parsed.get("LastName"),
                    "father_name": parsed.get("FatherName"),
                    "birth_date": parsed.get("BirthDate"),
                },
            }
        
        fault = _parse_fault(r.text)
        if fault:
            return {"success": False, "data": {"preapproved": False, "max_amount": 0, "message": fault}, "error": fault}
        
        return {"success": False, "data": {"preapproved": False, "max_amount": 0, "message": "Не удалось разобрать ответ."}, "error": "Parse error"}
    
    except requests.RequestException as e:
        return {"success": False, "data": {"preapproved": False, "max_amount": 0, "message": str(e)}, "error": str(e)}


def submit_request(
    base_url: str,
    user: str,
    passwd: str,
    *,
    amount: int | float = 10000,
    fio: str = "Тест Тестович Тестов",
    phone: str = "+37369123456",
    idn: str = "12345678901234",
    product_name: str = "Тестовый товар",
    program_name: str = "0-0-12",
    product_id: int = 0,
    goods_price: int | float = 0,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """
    Request_v4_PJ: отправка заявки на кредит.
    
    WSDL fields: Login, Password, Product, UIN, GoodsName, GoodsPrice, CreditAmount, etc.
    SOAPAction: http://tempuri.org/Request_v4_PJ_I/InsertRequest
    
    Returns: { "success": bool, "data": { "urn": str, "message": str }, "error": str? }
    """
    url = (base_url.rstrip("/") + "/Request_v4_PJ.svc").replace(".svc.svc", ".svc")
    action = "http://tempuri.org/Request_v4_PJ_I/InsertRequest"
    
    # Parse FIO into parts
    fio_parts = (fio or "Тест Тестович Тестов").strip().split()
    last_name = fio_parts[0] if len(fio_parts) > 0 else "Тестов"
    first_name = fio_parts[1] if len(fio_parts) > 1 else "Тест"
    father_name = fio_parts[2] if len(fio_parts) > 2 else "Тестович"
    
    credit_amount = int(amount or 10000)
    price = int(goods_price or amount or 10000)
    
    body = (
        '<InsertRequest xmlns="' + NS_TEMP + '">'
        + _el("Login", user)
        + _el("Password", passwd)
        + _el("Product", str(product_id or 0))
        + _el("UIN", idn or "12345678901234")
        + _el("CompanyName", "")
        + _el("DateOfRegistration", "")
        + _el("Director", "")
        + _el("DirectorMobile", "")
        + _el("GUFirstName", first_name)
        + _el("GULastName", last_name)
        + _el("GUFatherName", father_name)
        + _el("GUMobile", phone or "+37369123456")
        + _el("GoodsName", product_name or "Тестовый товар")
        + _el("GoodsPrice", str(price))
        + _el("CreditAmount", str(credit_amount))
        + _el("FirstInstallmentDate", "")
        + _el("IdCard", "")
        + _el("CaRegion", "")
        + _el("CaCity", "")
        + _el("CaPhone", phone or "")
        + _el("CaStreet", "")
        + _el("CaBlock", "")
        + _el("CaAppartmentNum", "")
        + _el("JobCompany", "")
        + _el("JobPhone", "")
        + _el("CpFirstName", "")
        + _el("CpLastName", "")
        + _el("CpMobile", "")
        + _el("Imei1", "")
        + _el("Imei2", "")
        + _el("Imei3", "")
        + _el("Sex", "")
        + _el("Nationality", "")
        + _el("ExpiryDate", "")
        + _el("MarritalStatus", "")
        + _el("CaCountry", "")
        + _el("CaMail", "")
        + _el("CaCurYearAddress", "")
        + _el("CaHomeOwnership", "")
        + _el("BaCountry", "")
        + _el("BaRegion", "")
        + _el("BaCity", "")
        + _el("BaStreet", "")
        + _el("BaBlock", "")
        + _el("BaAppartmentNum", "")
        + _el("BaPhone", "")
        + _el("BaMobile", "")
        + _el("BaCurYearAddress", "")
        + _el("BaHomeOwnership", "")
        + _el("DependantChildren", "")
        + _el("SpFirstName", "")
        + _el("SpLastName", "")
        + _el("SpDateOfBirth", "")
        + _el("JobFieldActivity", "")
        + _el("JobProfessionOther", "")
        + _el("JobContractType", "")
        + _el("JobHireDate", "")
        + _el("JobHireEndDate", "")
        + _el("JobWorkYears", "")
        + _el("JobCountry", "")
        + _el("JobRegion", "")
        + _el("JobCity", "")
        + _el("JobStreet", "")
        + _el("JobBlock", "")
        + _el("JobAppartmentNum", "")
        + _el("JobMobile", "")
        + _el("JobEmail", "")
        + _el("RefundBank", "")
        + _el("RefundBankCode", "")
        + _el("RefundAccount", "")
        + _el("CpFatherName", "")
        + _el("CpCountry", "")
        + _el("CpRegion", "")
        + _el("CpCity", "")
        + _el("CpStreet", "")
        + _el("CpBlock", "")
        + _el("CpAppartmentNum", "")
        + _el("CpPhone", "")
        + _el("CpEmail", "")
        + _el("FiNetIncome", "")
        + _el("FiSpouseNetIncome", "")
        + _el("SpFathername", "")
        + _el("CardNo", "")
        + _el("GU_UIN", "")
        + _el("GU_IdentityCard", "")
        + _el("GU_ICExpiryDate", "")
        + _el("GU_Birth_Date", "")
        + _el("GU_CA_City", "")
        + _el("GU_CA_RegionDesc", "")
        + _el("GU_CA_Street", "")
        + _el("GU_CA_Block", "")
        + _el("GU_CA_AppartmentNum", "")
        + _el("GU_CA_Phone", "")
        + _el("GU_CA_Mobile2", "")
        + _el("GU_JO_MonthlyIncome", "")
        + "</InsertRequest>"
    )
    
    try:
        r = _soap_post(url, action, body, verify_ssl=verify_ssl)
        r.raise_for_status()
        
        parsed = _parse_soap_response(r.text, "InsertRequestResult")
        if parsed:
            urn = parsed.get("URN") or parsed.get("urn") or parsed.get("RequestId") or ""
            status = parsed.get("Status") or parsed.get("status") or ""
            message = parsed.get("Message") or parsed.get("message") or status or "Заявка отправлена."
            return {"success": True, "data": {"urn": urn, "status": status, "message": message}}
        
        fault = _parse_fault(r.text)
        if fault:
            return {"success": False, "data": {"urn": "", "message": fault}, "error": fault}
        
        return {"success": False, "data": {"urn": "", "message": "Не удалось разобрать ответ."}, "error": "Parse error"}
    
    except requests.RequestException as e:
        return {"success": False, "data": {"urn": "", "message": str(e)}, "error": str(e)}


def status(
    base_url: str,
    user: str,
    passwd: str,
    urn: str,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """
    URNStatus_v2: статус заявки по URN.
    
    WSDL fields: Login, Password, URN
    SOAPAction: http://tempuri.org/URNStatus_v2_I/GetUrnStatus
    
    Returns: { "success": bool, "data": { "urn": str, "status": str, "message": str }, "error": str? }
    """
    if not (urn or "").strip():
        return {"success": False, "data": {"urn": "", "status": "", "message": "URN не указан."}, "error": "URN required"}
    
    url = (base_url.rstrip("/") + "/URNStatus_v2.svc").replace(".svc.svc", ".svc")
    action = "http://tempuri.org/URNStatus_v2_I/GetUrnStatus"
    
    body = (
        '<GetUrnStatus xmlns="' + NS_TEMP + '">'
        + _el("Login", user)
        + _el("Password", passwd)
        + _el("URN", urn.strip())
        + "</GetUrnStatus>"
    )
    
    try:
        r = _soap_post(url, action, body, verify_ssl=verify_ssl)
        r.raise_for_status()
        
        parsed = _parse_soap_response(r.text, "GetUrnStatusResult")
        if parsed:
            st = parsed.get("Status") or parsed.get("status") or ""
            return {"success": True, "data": {"urn": urn, "status": st, "message": "Статус получен."}}
        
        fault = _parse_fault(r.text)
        if fault:
            return {"success": False, "data": {"urn": urn, "status": "", "message": fault}, "error": fault}
        
        return {"success": False, "data": {"urn": urn, "status": "", "message": "Не удалось разобрать ответ."}, "error": "Parse error"}
    
    except requests.RequestException as e:
        return {"success": False, "data": {"urn": urn, "status": "", "message": str(e)}, "error": str(e)}


def get_client_info_by_phone(
    base_url: str,
    user: str,
    passwd: str,
    phone: str,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """
    ECM_GetClientInfoByPhone: получить информацию о клиенте по телефону.
    
    WSDL fields: Login, Password, Phone
    SOAPAction: http://tempuri.org/ECM_GetClientInfoByPhone_I/GetClientInfoByPhone
    
    Returns: { "success": bool, "data": { client info }, "error": str? }
    """
    if not (phone or "").strip():
        return {"success": False, "data": {}, "error": "Phone required"}
    
    url = (base_url.rstrip("/") + "/ECM_GetClientInfoByPhone.svc").replace(".svc.svc", ".svc")
    action = "http://tempuri.org/ECM_GetClientInfoByPhone_I/GetClientInfoByPhone"
    
    body = (
        '<GetClientInfoByPhone xmlns="' + NS_TEMP + '">'
        + _el("Login", user)
        + _el("Password", passwd)
        + _el("Phone", phone.strip())
        + "</GetClientInfoByPhone>"
    )
    
    try:
        r = _soap_post(url, action, body, verify_ssl=verify_ssl)
        r.raise_for_status()
        
        parsed = _parse_soap_response(r.text, "GetClientInfoByPhoneResult")
        if parsed:
            return {"success": True, "data": parsed, "raw": r.text}
        
        fault = _parse_fault(r.text)
        if fault:
            return {"success": False, "data": {}, "error": fault, "raw": r.text}
        
        return {"success": False, "data": {}, "error": "Parse error", "raw": r.text}
    
    except requests.RequestException as e:
        return {"success": False, "data": {}, "error": str(e)}


def _parse_customer_info_xml(xml_str: str) -> dict[str, Any]:
    """Parse embedded CustomerInfo XML into structured dict."""
    try:
        root = ET.fromstring(xml_str)
        customer = {}
        # Find Customer element
        cust_el = root.find("Customer") or root
        for child in cust_el:
            tag = child.tag
            if tag == "Loans":
                loans = []
                for loan_el in child.findall("Loan"):
                    loan = {}
                    for lc in loan_el:
                        loan[lc.tag] = (lc.text or "").strip()
                    if loan:
                        loans.append(loan)
                customer["Loans"] = loans
            else:
                customer[tag] = (child.text or "").strip()
        return customer
    except ET.ParseError:
        return {}


def get_client_info(
    base_url: str,
    user: str,
    passwd: str,
    uin: str,
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """
    eShopClientInfo_v3: получить информацию о клиенте по UIN (IDNP).
    
    WSDL fields: Login, Password, Uin, RequestStatusID, DocumentStatusID, Messages
    SOAPAction: http://tempuri.org/eShopClientInfo_v3_I/eShopClientInfo_v3
    
    Returns: { "success": bool, "data": { client info }, "error": str? }
    """
    if not (uin or "").strip():
        return {"success": False, "data": {}, "error": "UIN required"}
    
    url = (base_url.rstrip("/") + "/eShopClientInfo_v3.svc").replace(".svc.svc", ".svc")
    action = "http://tempuri.org/eShopClientInfo_v3_I/eShopClientInfo_v3"
    
    body = (
        '<eShopClientInfo_v3 xmlns="' + NS_TEMP + '">'
        + _el("Login", user)
        + _el("Password", passwd)
        + _el("Uin", uin.strip())
        + _el("RequestStatusID", "")
        + _el("DocumentStatusID", "")
        + _el("Messages", "")
        + "</eShopClientInfo_v3>"
    )
    
    try:
        r = _soap_post(url, action, body, verify_ssl=verify_ssl)
        r.raise_for_status()
        
        parsed = _parse_soap_response(r.text, "eShopClientInfo_v3Result")
        if parsed:
            # Parse embedded XML in Info field
            info_xml = parsed.get("Info") or ""
            if info_xml.startswith("<?xml") or info_xml.startswith("<CustomerInfo"):
                customer = _parse_customer_info_xml(info_xml)
                if customer:
                    parsed["Customer"] = customer
            return {"success": True, "data": parsed, "raw": r.text}
        
        fault = _parse_fault(r.text)
        if fault:
            return {"success": False, "data": {}, "error": fault, "raw": r.text}
        
        return {"success": False, "data": {}, "error": "Parse error", "raw": r.text}
    
    except requests.RequestException as e:
        return {"success": False, "data": {}, "error": str(e)}


def get_urns_per_uin(
    base_url: str,
    user: str,
    passwd: str,
    uin: str,
    group: str = "",
    status_filter: str = "",
    mode: str = "",
    verify_ssl: bool = True,
) -> dict[str, Any]:
    """
    ECM_GetUrnPerUin_V2: получить список заявок (URN) клиента по UIN.
    
    WSDL fields: Login, Password, UIN, Group, Status, Mode
    SOAPAction: http://tempuri.org/ECM_GetUrnPerUin_V2_I/ECM_GetUrnPerUin
    
    Returns: { "success": bool, "data": { urns list }, "error": str? }
    """
    if not (uin or "").strip():
        return {"success": False, "data": {}, "error": "UIN required"}
    
    url = (base_url.rstrip("/") + "/ECM_GetUrnPerUin_V2.svc").replace(".svc.svc", ".svc")
    action = "http://tempuri.org/ECM_GetUrnPerUin_V2_I/ECM_GetUrnPerUin"
    
    body = (
        '<ECM_GetUrnPerUin xmlns="' + NS_TEMP + '">'
        + _el("Login", user)
        + _el("Password", passwd)
        + _el("UIN", uin.strip())
        + _el("Group", group)
        + _el("Status", status_filter)
        + _el("Mode", mode)
        + "</ECM_GetUrnPerUin>"
    )
    
    try:
        r = _soap_post(url, action, body, verify_ssl=verify_ssl)
        r.raise_for_status()
        
        parsed = _parse_soap_response(r.text, "ECM_GetUrnPerUinResult")
        if parsed:
            return {"success": True, "data": parsed, "raw": r.text}
        
        fault = _parse_fault(r.text)
        if fault:
            return {"success": False, "data": {}, "error": fault, "raw": r.text}
        
        return {"success": False, "data": {}, "error": "Parse error", "raw": r.text}
    
    except requests.RequestException as e:
        return {"success": False, "data": {}, "error": str(e)}
