"""amoCRM integration service for Stage 1 CRM automation."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


logger = logging.getLogger(__name__)


class CRMConfigurationError(RuntimeError):
    """Raised when amoCRM configuration is missing or incomplete."""


@dataclass
class ContactPayload:
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None


@dataclass
class DocumentChecklist:
    proposal_sent: bool = False
    invoice_sent: bool = False
    contract_signed: bool = False
    closing_documents_ready: bool = False


@dataclass
class InteractionPayload:
    channel: str
    subject: str
    message: str
    contact: ContactPayload
    source_id: Optional[str] = None
    direction: str = "incoming"
    metadata: Optional[Dict[str, Any]] = None
    documents: Optional[DocumentChecklist] = None
    responsible_user_id: Optional[int] = None
    follow_up_hours: int = 4


class CRMService:
    """Service coordinating interactions with amoCRM."""

    def __init__(self) -> None:
        self.base_url = os.getenv("AMO_BASE_URL", "").rstrip("/")
        self.client_id = os.getenv("AMO_CLIENT_ID", "")
        self.client_secret = os.getenv("AMO_CLIENT_SECRET", "")
        self.redirect_uri = os.getenv("AMO_REDIRECT_URI", "")

        self.pipeline_id = self._maybe_int(os.getenv("AMO_PIPELINE_ID"))
        self.lead_status_id = self._maybe_int(os.getenv("AMO_LEAD_STATUS_ID"))
        self.default_responsible_id = self._maybe_int(os.getenv("AMO_RESPONSIBLE_USER_ID"))

        self.token_storage = Path(os.getenv("AMO_TOKEN_FILE", "amo_tokens.json"))
        self.access_token = os.getenv("AMO_ACCESS_TOKEN")
        self.refresh_token = os.getenv("AMO_REFRESH_TOKEN")
        self._expires_at: Optional[datetime] = None

        self._token_lock = asyncio.Lock()

        self._load_tokens_from_file()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def register_interaction(self, payload: InteractionPayload) -> Dict[str, Any]:
        """Create/update contact, lead, and tasks based on an interaction."""

        self._validate_config()

        contact_id = await self._upsert_contact(payload.contact)
        lead_id = await self._ensure_open_lead(contact_id, payload)

        await self._attach_interaction_note(lead_id, payload)
        await self._ensure_follow_up_task(lead_id, payload)

        if payload.documents:
            await self._ensure_document_tasks(lead_id, payload)

        return {
            "contact_id": contact_id,
            "lead_id": lead_id,
        }

    async def ensure_document_completeness(
        self,
        lead_id: int,
        documents: DocumentChecklist,
        responsible_user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Check document checklist and create missing tasks."""

        payload = InteractionPayload(
            channel="system",
            subject="Document checklist",
            message="Automated document control",
            contact=ContactPayload(name=""),
            documents=documents,
            responsible_user_id=responsible_user_id,
        )

        await self._ensure_document_tasks(lead_id, payload)
        return {"lead_id": lead_id, "status": "tasks_created"}

    # ------------------------------------------------------------------
    # Contact and Lead helpers
    # ------------------------------------------------------------------
    async def _upsert_contact(self, contact: ContactPayload) -> int:
        """Create or update contact based on email/phone."""

        existing_id = await self._find_contact(contact)
        if existing_id:
            logger.debug("Contact %s exists with id %s", contact.email or contact.phone, existing_id)
            await self._update_contact(existing_id, contact)
            return existing_id

        logger.info("Creating new contact for %s", contact.name)
        data = {
            "name": contact.name or "New contact",
            "first_name": contact.name,
            "custom_fields_values": self._build_custom_fields(contact),
        }

        response = await self._request("POST", "/api/v4/contacts", json={"contacts": [data]})
        embedded = response.get("_embedded", {}).get("contacts", [])
        if not embedded:
            raise RuntimeError("Failed to create contact in amoCRM")

        return int(embedded[0]["id"])

    async def _ensure_open_lead(self, contact_id: int, payload: InteractionPayload) -> int:
        lead = await self._find_open_lead(contact_id)
        if lead:
            logger.debug("Using existing lead %s for contact %s", lead["id"], contact_id)
            lead_id = int(lead["id"])
            await self._sync_lead_context(lead_id, payload)
            return lead_id

        logger.info("Creating new lead for contact %s", contact_id)

        responsible_id = payload.responsible_user_id or self.default_responsible_id
        lead_payload: Dict[str, Any] = {
            "name": payload.subject[:100] if payload.subject else "Incoming request",
            "price": payload.metadata.get("budget") if payload.metadata else None,
            "pipeline_id": self.pipeline_id,
            "status_id": self.lead_status_id,
            "responsible_user_id": responsible_id,
            "_embedded": {
                "contacts": [{"id": contact_id}],
            },
        }

        # Remove None values for amoCRM compatibility
        lead_payload = {k: v for k, v in lead_payload.items() if v is not None}

        response = await self._request("POST", "/api/v4/leads", json={"leads": [lead_payload]})
        embedded = response.get("_embedded", {}).get("leads", [])
        if not embedded:
            raise RuntimeError("Failed to create lead in amoCRM")

        lead_id = int(embedded[0]["id"])
        await self._sync_lead_context(lead_id, payload)
        return lead_id

    async def _sync_lead_context(self, lead_id: int, payload: InteractionPayload) -> None:
        """Update lead summary fields if additional metadata is provided."""

        if not payload.metadata:
            return

        update_fields = {}
        if budget := payload.metadata.get("budget"):
            update_fields["price"] = budget
        if payload.metadata.get("priority"):
            update_fields["custom_fields_values"] = [
                {
                    "field_code": "CUSTOMER_PRIORITY",
                    "values": [{"value": payload.metadata["priority"]}],
                }
            ]

        if not update_fields:
            return

        logger.debug("Updating lead %s with metadata", lead_id)
        await self._request(
            "PATCH",
            f"/api/v4/leads/{lead_id}",
            json={k: v for k, v in update_fields.items() if v is not None},
        )

    # ------------------------------------------------------------------
    # Notes & tasks
    # ------------------------------------------------------------------
    async def _attach_interaction_note(self, lead_id: int, payload: InteractionPayload) -> None:
        note_lines = [
            f"Источник: {payload.channel}",
            f"Направление: {payload.direction}",
        ]

        if payload.subject:
            note_lines.append(f"Тема: {payload.subject}")
        if payload.message:
            note_lines.append("---")
            note_lines.append(payload.message[:4000])

        if payload.metadata:
            note_lines.append("---")
            note_lines.append(f"Метаданные: {json.dumps(payload.metadata, ensure_ascii=False)}")

        text = "\n".join(line for line in note_lines if line)

        note_payload = [
            {
                "note_type": "common",
                "params": {"text": text},
            }
        ]

        await self._request("POST", f"/api/v4/leads/{lead_id}/notes", json=note_payload)

    async def _ensure_follow_up_task(self, lead_id: int, payload: InteractionPayload) -> None:
        existing = await self._list_tasks(lead_id)
        summary = f"Follow-up: {payload.channel}"
        if any(task.get("text") == summary for task in existing):
            return

        due_at = datetime.now(timezone.utc) + timedelta(hours=max(payload.follow_up_hours, 1))

        task_payload = {
            "text": summary,
            "complete_till": int(due_at.timestamp()),
            "entity_id": lead_id,
            "entity_type": "leads",
            "responsible_user_id": payload.responsible_user_id or self.default_responsible_id,
        }

        await self._request("POST", "/api/v4/tasks", json={"tasks": [task_payload]})

    async def _ensure_document_tasks(self, lead_id: int, payload: InteractionPayload) -> None:
        if not payload.documents:
            return

        checklist = {
            "Коммерческое предложение": payload.documents.proposal_sent,
            "Счет": payload.documents.invoice_sent,
            "Договор": payload.documents.contract_signed,
            "Закрывающие документы": payload.documents.closing_documents_ready,
        }

        existing = await self._list_tasks(lead_id)
        existing_texts = {task.get("text") for task in existing}

        tasks_to_create = []
        for name, completed in checklist.items():
            if completed:
                continue
            text = f"Отправить: {name}"
            if text in existing_texts:
                continue
            due_at = datetime.now(timezone.utc) + timedelta(hours=8)
            tasks_to_create.append(
                {
                    "text": text,
                    "complete_till": int(due_at.timestamp()),
                    "entity_id": lead_id,
                    "entity_type": "leads",
                    "responsible_user_id": payload.responsible_user_id or self.default_responsible_id,
                }
            )

        if not tasks_to_create:
            return

        await self._request("POST", "/api/v4/tasks", json={"tasks": tasks_to_create})

    async def _list_tasks(self, lead_id: int) -> List[Dict[str, Any]]:
        response = await self._request(
            "GET",
            "/api/v4/tasks",
            params={
                "filter[entity_id]": lead_id,
                "filter[entity_type]": "leads",
            },
        )

        return response.get("_embedded", {}).get("tasks", [])

    async def add_lead_note(self, lead_id: int, title: str, details: str | None = None) -> None:
        text = title.strip()
        if details:
            text = f"{text}\n---\n{details.strip()}"

        note_payload = [
            {
                "note_type": "common",
                "params": {"text": text},
            }
        ]

        await self._request("POST", f"/api/v4/leads/{lead_id}/notes", json=note_payload)

    async def record_generated_document(
        self,
        lead_id: int,
        document_type: str,
        document_number: str,
        extra: Dict[str, Any] | None = None,
    ) -> None:
        lines = [f"В 1С создан документ: {document_type} №{document_number}"]
        if extra:
            for key, value in extra.items():
                lines.append(f"{key}: {value}")

        await self.add_lead_note(
            lead_id,
            title="Документы из 1С",
            details="\n".join(lines),
        )

    async def record_payment_notification(
        self,
        lead_id: int,
        invoice_number: str,
        amount: float | None = None,
        currency: str | None = None,
        payer: str | None = None,
    ) -> None:
        parts = [f"Оплата по счёту №{invoice_number} получена"]
        if amount is not None:
            parts.append(f"Сумма: {amount:.2f} {currency or ''}".strip())
        if payer:
            parts.append(f"Плательщик: {payer}")

        await self.add_lead_note(
            lead_id,
            title="Поступление оплаты",
            details="\n".join(parts),
        )

    # ------------------------------------------------------------------
    # Contact helpers
    # ------------------------------------------------------------------
    async def _find_contact(self, contact: ContactPayload) -> Optional[int]:
        if not contact.email and not contact.phone:
            return None

        query = contact.email or contact.phone
        params = {"query": query}
        response = await self._request("GET", "/api/v4/contacts", params=params)
        contacts = response.get("_embedded", {}).get("contacts", [])
        if contacts:
            return int(contacts[0]["id"])
        return None

    async def _update_contact(self, contact_id: int, contact: ContactPayload) -> None:
        update_payload = {
            "name": contact.name,
            "custom_fields_values": self._build_custom_fields(contact),
        }

        await self._request(
            "PATCH",
            f"/api/v4/contacts/{contact_id}",
            json={k: v for k, v in update_payload.items() if v},
        )

    def _build_custom_fields(self, contact: ContactPayload) -> List[Dict[str, Any]]:
        custom_fields = []
        if contact.email:
            custom_fields.append(
                {
                    "field_code": "EMAIL",
                    "values": [{"value": contact.email, "enum_code": "WORK"}],
                }
            )
        if contact.phone:
            custom_fields.append(
                {
                    "field_code": "PHONE",
                    "values": [{"value": contact.phone, "enum_code": "WORK"}],
                }
            )
        if contact.company:
            custom_fields.append(
                {
                    "field_code": "COMPANY_NAME",
                    "values": [{"value": contact.company}],
                }
            )
        return custom_fields

    async def _find_open_lead(self, contact_id: int) -> Optional[Dict[str, Any]]:
        params = {
            "filter[contacts][]": contact_id,
            "filter[statuses][0][pipeline_id]": self.pipeline_id,
        }
        response = await self._request("GET", "/api/v4/leads", params=params)
        leads = response.get("_embedded", {}).get("leads", [])
        return leads[0] if leads else None

    # ------------------------------------------------------------------
    # Networking helpers
    # ------------------------------------------------------------------
    async def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        await self._ensure_access_token()

        url = f"{self.base_url}{path}"

        headers = kwargs.pop("headers", {})
        headers.setdefault("Authorization", f"Bearer {self.access_token}")
        headers.setdefault("Content-Type", "application/json")

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.request(method, url, headers=headers, **kwargs)

        if response.status_code == 401:
            logger.info("Access token expired, refreshing...")
            await self._refresh_token()
            headers["Authorization"] = f"Bearer {self.access_token}"
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.request(method, url, headers=headers, **kwargs)

        if response.is_error:
            logger.error("amoCRM API error (%s): %s", response.status_code, response.text)
            raise RuntimeError(f"amoCRM API error {response.status_code}")

        if response.content:
            return response.json()
        return {}

    async def _ensure_access_token(self) -> None:
        if not self.access_token:
            raise CRMConfigurationError("AMO_ACCESS_TOKEN is not configured and no cached token found")

        if self._expires_at and datetime.now(timezone.utc) < self._expires_at - timedelta(minutes=2):
            return

        await self._refresh_token()

    async def _refresh_token(self) -> None:
        async with self._token_lock:
            if self._expires_at and datetime.now(timezone.utc) < self._expires_at - timedelta(minutes=2):
                return

            if not self.refresh_token:
                raise CRMConfigurationError("AMO_REFRESH_TOKEN is missing; cannot refresh token")

            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "redirect_uri": self.redirect_uri,
            }

            token_url = f"{self.base_url}/oauth2/access_token"
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(token_url, json=payload)

            if response.is_error:
                logger.error("Failed to refresh amoCRM token: %s", response.text)
                raise RuntimeError("Failed to refresh amoCRM access token")

            data = response.json()
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token", self.refresh_token)
            expires_in = data.get("expires_in", 3600)
            self._expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

            self._save_tokens_to_file()

    # ------------------------------------------------------------------
    # Token storage helpers
    # ------------------------------------------------------------------
    def _load_tokens_from_file(self) -> None:
        if not self.token_storage.exists():
            return

        try:
            data = json.loads(self.token_storage.read_text())
        except Exception as exc:  # pragma: no cover - config guard
            logger.warning("Failed to read amo token file: %s", exc)
            return

        self.access_token = data.get("access_token", self.access_token)
        self.refresh_token = data.get("refresh_token", self.refresh_token)
        if expires := data.get("expires_at"):
            self._expires_at = datetime.fromisoformat(expires)

    def _save_tokens_to_file(self) -> None:
        data = {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_at": self._expires_at.isoformat() if self._expires_at else None,
        }

        try:
            self.token_storage.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to write amo token file: %s", exc)

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------
    def _validate_config(self) -> None:
        if not self.base_url:
            raise CRMConfigurationError("AMO_BASE_URL is not configured")
        if not self.client_id or not self.client_secret or not self.redirect_uri:
            raise CRMConfigurationError("amoCRM OAuth credentials are incomplete")
        if not self.pipeline_id or not self.lead_status_id:
            raise CRMConfigurationError("Pipeline or status configuration is missing")

    @staticmethod
    def _maybe_int(value: Optional[str]) -> Optional[int]:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except ValueError:
            return None


crm_service = CRMService()


