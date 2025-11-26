"""Enhanced document control service with file checking and reminders."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.crm_service import crm_service, CRMConfigurationError
from services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)


class DocumentControlService:
    """Service for monitoring document completeness and sending reminders."""

    REQUIRED_DOCUMENTS = [
        "proposal",
        "invoice",
        "contract",
        "waybill",
        "act",
        "invoice_factura",
    ]

    def __init__(self) -> None:
        self.reminder_interval_hours = 24
        self.urgent_threshold_days = 3

    async def check_and_remind(self, lead_id: int) -> Dict[str, Any]:
        """Check document completeness and send reminders if needed."""
        
        try:
            # Check files
            file_check = await crm_service.check_document_files(lead_id)
            
            if file_check.get("complete"):
                return {
                    "lead_id": lead_id,
                    "status": "complete",
                    "message": "Все документы присутствуют",
                }

            # Get missing documents
            checklist = file_check.get("checklist", {})
            missing = [doc for doc, present in checklist.items() if not present]
            
            if not missing:
                return {
                    "lead_id": lead_id,
                    "status": "unknown",
                    "message": "Не удалось определить отсутствующие документы",
                }

            # Check if we've already sent a reminder recently
            last_reminder = await self._get_last_reminder_time(lead_id)
            now = datetime.now(timezone.utc)
            
            if last_reminder:
                hours_since_reminder = (now - last_reminder).total_seconds() / 3600
                if hours_since_reminder < self.reminder_interval_hours:
                    return {
                        "lead_id": lead_id,
                        "status": "reminder_sent_recently",
                        "hours_until_next": self.reminder_interval_hours - hours_since_reminder,
                    }

            # Get lead info
            try:
                lead_response = await crm_service._request("GET", f"/api/v4/leads/{lead_id}")
                lead_name = lead_response.get("name", "Сделка")
            except Exception:
                lead_name = "Сделка"

            # Send WhatsApp reminder to manager
            missing_docs_str = ", ".join(missing)
            message = (
                f"❗ В сделке {lead_name} не хватает документов: {missing_docs_str}.\n"
                f"Прикрепите в CRM."
            )
            
            await whatsapp_service.send_to_manager(message, urgent=False)

            # Create task for missing documents
            await self._create_missing_document_tasks(lead_id, missing)

            # Record reminder time
            await self._record_reminder_time(lead_id, now)

            # Check if urgent (more than 3 days)
            days_since_first_reminder = await self._get_days_since_first_reminder(lead_id)
            if days_since_first_reminder >= self.urgent_threshold_days:
                urgent_message = (
                    f"🚨 СРОЧНО: В сделке {lead_name} не хватает документов более 3 дней: {missing_docs_str}.\n"
                    f"Требуется немедленное внимание!"
                )
                await whatsapp_service.send_to_manager(urgent_message, urgent=True)

            # Update lead status/custom field
            await self._update_document_status(lead_id, complete=False)

            return {
                "lead_id": lead_id,
                "status": "reminder_sent",
                "missing_documents": missing,
                "message": "Напоминание отправлено менеджеру",
            }

        except CRMConfigurationError:
            logger.warning("amoCRM not configured, skipping document check")
            return {"lead_id": lead_id, "status": "error", "error": "CRM not configured"}
        except Exception as exc:
            logger.error("Document check failed: %s", exc)
            return {"lead_id": lead_id, "status": "error", "error": str(exc)}

    async def _create_missing_document_tasks(self, lead_id: int, missing: List[str]) -> None:
        """Create tasks for missing documents."""
        
        doc_names = {
            "proposal": "Коммерческое предложение",
            "invoice": "Счет",
            "contract": "Договор",
            "waybill": "Накладная",
            "act": "Акт",
            "invoice_factura": "Счет-фактура или УПД",
        }

        existing = await crm_service._list_tasks(lead_id)
        existing_texts = {task.get("text") for task in existing}

        tasks_to_create = []
        for doc_key in missing:
            doc_name = doc_names.get(doc_key, doc_key)
            text = f"Прикрепить: {doc_name}"
            if text in existing_texts:
                continue

            due_at = datetime.now(timezone.utc) + timedelta(hours=8)
            tasks_to_create.append(
                {
                    "text": text,
                    "complete_till": int(due_at.timestamp()),
                    "entity_id": lead_id,
                    "entity_type": "leads",
                    "responsible_user_id": crm_service.default_responsible_id,
                }
            )

        if tasks_to_create:
            try:
                await crm_service._request("POST", "/api/v4/tasks", json={"tasks": tasks_to_create})
            except Exception as exc:
                logger.error("Failed to create document tasks: %s", exc)

    async def _get_last_reminder_time(self, lead_id: int) -> Optional[datetime]:
        """Get timestamp of last reminder from lead notes."""
        try:
            response = await crm_service._request("GET", f"/api/v4/leads/{lead_id}/notes")
            notes = response.get("_embedded", {}).get("notes", [])
            
            for note in reversed(notes):
                text = note.get("params", {}).get("text", "")
                if "Напоминание о документах" in text or "не хватает документов" in text:
                    created_at = note.get("created_at")
                    if created_at:
                        try:
                            return datetime.fromtimestamp(created_at, tz=timezone.utc)
                        except (ValueError, TypeError):
                            pass
        except Exception:
            pass
        return None

    async def _get_days_since_first_reminder(self, lead_id: int) -> int:
        """Get days since first reminder was sent."""
        try:
            response = await crm_service._request("GET", f"/api/v4/leads/{lead_id}/notes")
            notes = response.get("_embedded", {}).get("notes", [])
            
            for note in notes:
                text = note.get("params", {}).get("text", "")
                if "не хватает документов" in text:
                    created_at = note.get("created_at")
                    if created_at:
                        try:
                            first_reminder_time = datetime.fromtimestamp(created_at, tz=timezone.utc)
                            now = datetime.now(timezone.utc)
                            days = (now - first_reminder_time).total_seconds() / 86400
                            return int(days)
                        except (ValueError, TypeError):
                            pass
        except Exception:
            pass
        return 0

    async def _record_reminder_time(self, lead_id: int, reminder_time: datetime) -> None:
        """Record reminder time in lead note."""
        try:
            await crm_service.add_lead_note(
                lead_id,
                "Напоминание о документах",
                f"Отправлено напоминание менеджеру о недостающих документах.\nВремя: {reminder_time.isoformat()}",
            )
        except Exception as exc:
            logger.error("Failed to record reminder time: %s", exc)

    async def _update_document_status(self, lead_id: int, complete: bool) -> None:
        """Update document status in lead custom field or note."""
        status_text = "✅ Полный комплект" if complete else "⚠️ Не полный"
        try:
            await crm_service.add_lead_note(
                lead_id,
                "Статус закрывающих документов",
                status_text,
            )
        except Exception as exc:
            logger.error("Failed to update document status: %s", exc)


document_control_service = DocumentControlService()

