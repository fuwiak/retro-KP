"""Integration service for 1C document workflow."""

from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict

import httpx


logger = logging.getLogger(__name__)


class OneCConfigurationError(RuntimeError):
    """Raised when required 1C configuration is missing."""


class OneCService:
    """High-level client for interacting with 1C HTTP endpoints."""

    def __init__(self) -> None:
        self.base_url = os.getenv("ONEC_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("ONEC_API_KEY", "")
        self.timeout_seconds = float(os.getenv("ONEC_TIMEOUT_SECONDS", "15") or 15)
        self.invoice_endpoint = os.getenv("ONEC_INVOICE_ENDPOINT", "/documents/invoice")
        self.fulfillment_endpoint = os.getenv("ONEC_FULFILLMENT_ENDPOINT", "/documents/fulfillment")

        if not self.base_url:
            logger.warning(
                "ONEC_BASE_URL is not configured. Document generation will return mock responses only."
            )

    async def create_invoice(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Request invoice generation in 1C."""

        response = await self._post(
            endpoint=self.invoice_endpoint,
            json_payload=payload,
            mock_document_type="invoice",
        )
        return response

    async def create_fulfillment_documents(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Request waybill/act generation in 1C."""

        response = await self._post(
            endpoint=self.fulfillment_endpoint,
            json_payload=payload,
            mock_document_type="fulfillment",
        )
        return response

    async def _post(
        self,
        *,
        endpoint: str,
        json_payload: Dict[str, Any],
        mock_document_type: str,
    ) -> Dict[str, Any]:
        """Perform POST request to 1C or return mock data if not configured."""

        if not self.base_url:
            return self._mock_response(json_payload, mock_document_type)

        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        timeout = httpx.Timeout(self.timeout_seconds)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=json_payload, headers=headers)

        if response.is_error:
            logger.error("1C API error (%s): %s", response.status_code, response.text)
            raise RuntimeError(f"1C API error {response.status_code}")

        return response.json()

    def _mock_response(self, payload: Dict[str, Any], doc_type: str) -> Dict[str, Any]:
        """Return dummy document data when 1C endpoint is unavailable."""

        mock_number = payload.get("draftNumber") or payload.get("leadId") or "DRAFT-0001"
        pdf_bytes = f"Mock {doc_type.upper()} document for {mock_number}".encode("utf-8")
        encoded_pdf = base64.b64encode(pdf_bytes).decode("ascii")

        if doc_type == "invoice":
            return {
                "invoiceNumber": f"INV-{mock_number}",
                "invoicePdfBase64": encoded_pdf,
            }

        return {
            "waybillNumber": f"WB-{mock_number}",
            "actNumber": f"ACT-{mock_number}",
            "waybillPdfBase64": encoded_pdf,
            "actPdfBase64": encoded_pdf,
        }


onec_service = OneCService()
