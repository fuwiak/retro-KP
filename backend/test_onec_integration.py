"""Manual test helpers for 1C integration (invoice, fulfillment, payment)."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict

from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).parent))

from services.onec_service import OneCService
from services import onec_service as onec_module
from main import app

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover - optional dependency in test context
    TestClient = None  # type: ignore


def banner(title: str) -> None:
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sample_invoice_payload() -> Dict[str, Any]:
    return {
        "lead_id": 123,
        "crm_contact_id": 456,
        "customer_name": "ТОО \"Даниял Лтд Групп\"",
        "customer_bin": "170940034703",
        "customer_email": "billing@example.com",
        "customer_phone": "+7 707 555 55 55",
        "currency": "KZT",
        "items": [
            {
                "name": "АВР Stalker Electric Т1+Т2, 630А, 400В, IP54",
                "article": "OMPC200-INOX",
                "description": "Автоматический ввод резерва",
                "quantity": 2,
                "price": 5000,
                "amount": 10000,
            },
            {
                "name": "Контактор Siemens 3RT2026-1AP00",
                "article": "LV480857",
                "description": "Контактор силовой",
                "quantity": 1,
                "price": 8000,
                "amount": 8000,
            },
        ],
        "metadata": {
            "source": "test",
            "comment": "Integration test payload",
        },
    }


def sample_fulfillment_payload() -> Dict[str, Any]:
    return {
        "lead_id": 123,
        "crm_contact_id": 456,
        "customer_name": "ТОО \"Даниял Лтд Групп\"",
        "customer_bin": "170940034703",
        "delivery_address": "г. Алматы, ул. Тестовая 1",
        "documents": {"power_of_attorney": "№42 от 28.10.2025"},
        "items": [
            {
                "name": "АВР Stalker Electric Т1+Т2, 630А, 400В, IP54",
                "article": "OMPC200-INOX",
                "description": "Автоматический ввод резерва",
                "quantity": 2,
                "price": 5000,
                "amount": 10000,
            }
        ],
    }


def sample_payment_payload() -> Dict[str, Any]:
    return {
        "lead_id": 123,
        "invoice_number": "INV-2025-00042",
        "amount": 18000.0,
        "currency": "KZT",
        "payer_name": "ТОО \"Даниял Лтд Групп\"",
    }


# ---------------------------------------------------------------------------
# Async service tests
# ---------------------------------------------------------------------------


async def test_onec_service_mock_mode() -> None:
    banner("TEST 1: OneCService mock mode (no ONEC_BASE_URL)")
    env_backup = {key: os.environ.get(key) for key in ["ONEC_BASE_URL", "ONEC_API_KEY"]}
    try:
        os.environ.pop("ONEC_BASE_URL", None)
        os.environ.pop("ONEC_API_KEY", None)
        service = OneCService()
        invoice = await service.create_invoice(sample_invoice_payload())
        print("Mock invoice response:")
        print(invoice)
        assert invoice["invoiceNumber"].startswith("INV-"), "Mock invoice number missing"

        fulfillment = await service.create_fulfillment_documents(sample_fulfillment_payload())
        print("Mock fulfillment response:")
        print(fulfillment)
        assert "waybillNumber" in fulfillment, "Mock fulfillment response missing waybill"
    finally:
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


async def test_onec_service_http_call() -> None:
    banner("TEST 2: OneCService real HTTP call (mocked httpx client)")
    env_backup = {key: os.environ.get(key) for key in ["ONEC_BASE_URL", "ONEC_API_KEY"]}
    try:
        os.environ["ONEC_BASE_URL"] = "https://onec.example.com/api"
        os.environ["ONEC_API_KEY"] = "secret-token"

        service = OneCService()

        captured = {}

        class DummyResponse:
            def __init__(self, data: Dict[str, Any], status_code: int = 200) -> None:
                self._data = data
                self.status_code = status_code

            @property
            def is_error(self) -> bool:
                return not (200 <= self.status_code < 300)

            def json(self) -> Dict[str, Any]:
                return self._data

        class DummyClient:
            def __init__(self, *args, **kwargs) -> None:
                self.args = args
                self.kwargs = kwargs

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, url: str, json: Dict[str, Any], headers: Dict[str, Any]):
                captured["url"] = url
                captured["json"] = json
                captured["headers"] = headers
                return DummyResponse({"invoiceNumber": "INV-REMOTE-42"})

        with patch("httpx.AsyncClient", DummyClient):
            response = await service.create_invoice(sample_invoice_payload())

        assert response["invoiceNumber"] == "INV-REMOTE-42"
        expected_suffix = service.invoice_endpoint
        assert captured["url"].endswith(expected_suffix), captured["url"]
        auth_header = captured["headers"].get("Authorization", "")
        assert auth_header.startswith("Bearer") or auth_header.startswith("Basic"), auth_header
        print("Captured request:")
        print(captured)
    finally:
        for key, value in env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


# ---------------------------------------------------------------------------
# FastAPI endpoint smoke tests
# ---------------------------------------------------------------------------


def test_fastapi_invoice_endpoint() -> None:
    if TestClient is None:
        print("fastapi.TestClient unavailable, skipping API tests")
        return

    banner("TEST 3: FastAPI /api/integrations/1c/invoices")
    client = TestClient(app)

    async def fake_create_invoice(payload):
        assert payload["leadId"] == 123
        return {"invoiceNumber": "INV-API-777", "invoicePdfBase64": "UEZG"}

    with patch.object(onec_module.onec_service, "create_invoice", new=AsyncMock(side_effect=fake_create_invoice)):
        response = client.post("/api/integrations/1c/invoices", json=sample_invoice_payload())

    assert response.status_code == 200, response.text
    data = response.json()
    print("API response:", data)
    assert data["invoice"]["invoiceNumber"] == "INV-API-777"


def test_fastapi_fulfillment_endpoint() -> None:
    if TestClient is None:
        return

    banner("TEST 4: FastAPI /api/integrations/1c/fulfillment")
    client = TestClient(app)

    async def fake_create_fulfillment(payload):
        assert payload["leadId"] == 123
        return {
            "waybillNumber": "WB-API-007",
            "actNumber": "ACT-API-007",
        }

    with patch.object(onec_module.onec_service, "create_fulfillment_documents", new=AsyncMock(side_effect=fake_create_fulfillment)):
        response = client.post("/api/integrations/1c/fulfillment", json=sample_fulfillment_payload())

    assert response.status_code == 200, response.text
    data = response.json()
    print("API response:", data)
    assert data["documents"]["waybillNumber"] == "WB-API-007"


def test_fastapi_payment_notification_endpoint() -> None:
    if TestClient is None:
        return

    banner("TEST 5: FastAPI /api/integrations/1c/payment-notification")
    client = TestClient(app)

    async def fake_record_payment(*args, **kwargs):
        print("record_payment_notification called with:", args, kwargs)

    with patch.object(onec_module.crm_service, "record_payment_notification", new=AsyncMock(side_effect=fake_record_payment)):
        response = client.post("/api/integrations/1c/payment-notification", json=sample_payment_payload())

    assert response.status_code == 200, response.text
    data = response.json()
    print("API response:", data)
    assert data["status"] == "ok"


def test_raw_onec_invoice_endpoint():
    banner("TEST 6: Raw curl for https://buh.uchet.kz/.../PostDataInvoice")
    import json
    import subprocess

    payload = {
        "date": "2025-10-21",
        "warehouse": "Основной склад",
        "contractorIIN": "170940034703",
        "contractorName": "ТОО \"Даниял Лтд Групп\"",
        "items": [
            {
                "name": "АВР Stalker Electric Т1+Т2, 630А, 400В, IP54",
                "article": "OMPC200-INOX",
                "description": "Автоматический ввод резерва",
                "price": 5000,
                "quantity": 2,
                "amount": 10000,
            },
            {
                "name": "Контактор Siemens 3RT2026-1AP00",
                "article": "LV480857",
                "description": "Контактор силовой",
                "price": 8000,
                "quantity": 1,
                "amount": 8000,
            },
            {
                "name": "Реле промежуточное Finder 55.34.8.230.0040",
                "article": "JL-595 36W 3200Lm (4000K)",
                "description": "Реле промежуточное",
                "price": 1500,
                "quantity": 3,
                "amount": 4500,
            },
        ],
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Basic U3RhbGtlcjpWNERIYUpHUkZEMFZ3RGk=",
    }

    cmd = [
        "curl",
        "--location",
        "https://buh.uchet.kz/C3beseath3649/hs/AH_AVR/PostDataInvoice",
        "--header",
        f"Content-Type: {headers['Content-Type']}",
        "--header",
        f"Authorization: {headers['Authorization']}",
        "--data",
        json.dumps(payload, ensure_ascii=False),
    ]

    print("Executing:")
    print(" ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print("Status: success")
        print("stdout:\n", result.stdout)
        if result.stderr:
            print("stderr:\n", result.stderr)
    except subprocess.CalledProcessError as exc:
        print("Status: failure")
        print("stdout:\n", exc.stdout)
        print("stderr:\n", exc.stderr)


if __name__ == "__main__":
    asyncio.run(test_onec_service_mock_mode())
    asyncio.run(test_onec_service_http_call())
    test_fastapi_invoice_endpoint()
    test_fastapi_fulfillment_endpoint()
    test_fastapi_payment_notification_endpoint()
