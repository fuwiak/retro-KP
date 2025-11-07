"""Integration service for 1C document workflow."""

from __future__ import annotations

import base64
import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlparse

import httpx


logger = logging.getLogger(__name__)


class OneCConfigurationError(RuntimeError):
    """Raised when required 1C configuration is missing."""


class OneCService:
    """High-level client for interacting with 1C HTTP endpoints."""

    def __init__(self) -> None:
        self.base_url = os.getenv("ONEC_BASE_URL", "").rstrip("/")
        self.api_key = os.getenv("ONEC_API_KEY", "")
        self.auth_header = os.getenv("ONEC_AUTH_HEADER")
        self.timeout_seconds = float(os.getenv("ONEC_TIMEOUT_SECONDS", "15") or 15)

        # Endpoints (defaults adapted to PostDataInvoice / PostDataRealization)
        self.invoice_endpoint = os.getenv("ONEC_INVOICE_ENDPOINT", "/PostDataInvoice")
        self.invoice_pdf_endpoint = os.getenv("ONEC_INVOICE_PDF_ENDPOINT", self.invoice_endpoint)
        self.realization_endpoint = os.getenv("ONEC_REALIZATION_ENDPOINT", "/PostDataRealization")
        self.realization_pdf_endpoint = os.getenv("ONEC_REALIZATION_PDF_ENDPOINT", self.realization_endpoint)
        self.fulfillment_endpoint = os.getenv("ONEC_FULFILLMENT_ENDPOINT", "/documents/fulfillment")

        if not self.base_url:
            logger.warning(
                "ONEC_BASE_URL is not configured. Document generation will return mock responses only."
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def create_invoice(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._post(
            endpoint=self.invoice_endpoint,
            json_payload=payload,
            mock_document_type="invoice",
        )

    async def fetch_invoice_pdf(self, ref: str) -> bytes:
        return await self._get_pdf(self.invoice_pdf_endpoint, ref, mock_document_type="invoice")

    async def create_realization(self, invoice_uuid: str) -> Dict[str, Any]:
        payload = {"uuid": invoice_uuid}
        return await self._post(
            endpoint=self.realization_endpoint,
            json_payload=payload,
            mock_document_type="fulfillment",
        )

    async def fetch_realization_pdf(self, ref: str) -> bytes:
        return await self._get_pdf(self.realization_pdf_endpoint, ref, mock_document_type="fulfillment")

    async def create_fulfillment_documents(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return await self._post(
            endpoint=self.fulfillment_endpoint,
            json_payload=payload,
            mock_document_type="fulfillment",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_headers(
        self,
        *,
        content_type: Optional[str] = "application/json",
        accept: Optional[str] = "application/json",
    ) -> Dict[str, str]:
        headers: Dict[str, str] = {}
        if content_type:
            headers["Content-Type"] = content_type
        if accept:
            headers["Accept"] = accept

        if self.auth_header:
            headers["Authorization"] = self.auth_header
        elif self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        return headers

    async def _post(
        self,
        *,
        endpoint: str,
        json_payload: Dict[str, Any],
        mock_document_type: str,
    ) -> Dict[str, Any]:
        if not self.base_url:
            return self._mock_response(json_payload, mock_document_type)

        url = f"{self.base_url}{endpoint}"
        headers = self._build_headers()
        timeout = httpx.Timeout(self.timeout_seconds)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, json=json_payload, headers=headers)

        if response.is_error:
            logger.error("1C API error (%s): %s", response.status_code, response.text)
            raise RuntimeError(f"1C API error {response.status_code}")

        return response.json()

    async def _get_pdf(self, endpoint: str, ref: str, *, mock_document_type: str) -> bytes:
        if not self.base_url:
            mock = self._mock_response({"leadId": ref}, mock_document_type)
            b64 = mock.get("invoicePdfBase64") or mock.get("waybillPdfBase64") or ""
            if not b64:
                return b""
            return base64.b64decode(b64)

        url = f"{self.base_url}{endpoint}"
        # Ensure query string contains format=pdf&ref=...
        if "?" in url:
            full_url = f"{url}&ref={ref}" if "ref=" not in url else url
        else:
            full_url = f"{url}?format=pdf&ref={ref}"

        headers = self._build_headers(content_type=None, accept="application/pdf")
        timeout = httpx.Timeout(self.timeout_seconds)

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(full_url, headers=headers)

        if response.is_error:
            logger.error("1C PDF fetch error (%s): %s", response.status_code, response.text)
            raise RuntimeError(f"1C PDF fetch error {response.status_code}")

        return response.content

    def _mock_response(self, payload: Dict[str, Any], doc_type: str) -> Dict[str, Any]:
        mock_number = payload.get("draftNumber") or payload.get("leadId") or "DRAFT-0001"
        pdf_bytes = f"Mock {doc_type.upper()} document for {mock_number}".encode("utf-8")
        encoded_pdf = base64.b64encode(pdf_bytes).decode("ascii")

        if doc_type == "invoice":
            return {
                "invoiceNumber": f"INV-{mock_number}",
                "invoicePdfBase64": encoded_pdf,
                "pdfUrl": f"{self.invoice_pdf_endpoint}?format=pdf&ref={mock_number}",
            }

        return {
            "waybillNumber": f"WB-{mock_number}",
            "actNumber": f"ACT-{mock_number}",
            "waybillPdfBase64": encoded_pdf,
            "actPdfBase64": encoded_pdf,
            "pdfUrl": f"{self.realization_pdf_endpoint}?format=pdf&ref={mock_number}",
        }

    @staticmethod
    def extract_ref_from_pdf_url(pdf_url: str) -> Optional[str]:
        if not pdf_url:
            return None
        parsed = urlparse(pdf_url if pdf_url.startswith("http") else f"https://dummy/{pdf_url.lstrip('/')}")
        query = parse_qs(parsed.query)
        ref_values = query.get("ref")
        if ref_values:
            return ref_values[0]
        return None


onec_service = OneCService()
