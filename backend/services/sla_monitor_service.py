"""SLA monitoring service for tracking overdue tasks and sending notifications."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.crm_service import crm_service, CRMConfigurationError
from services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)


class SLAMonitorService:
    """Service for monitoring task deadlines and sending SLA notifications."""

    def __init__(self) -> None:
        self.overdue_threshold_hours = 1  # Notify manager after 1 hour
        self.urgent_threshold_hours = 4  # Notify manager after 4 hours

    async def check_overdue_tasks(self, lead_id: Optional[int] = None) -> Dict[str, Any]:
        """Check for overdue tasks and send notifications.

        Args:
            lead_id: If provided, check only tasks for this lead. Otherwise check all leads.

        Returns:
            {
                "checked": int,
                "overdue": int,
                "urgent": int,
                "notifications_sent": int,
            }
        """
        try:
            tasks = await self._fetch_tasks(lead_id)
        except CRMConfigurationError:
            logger.warning("amoCRM not configured, skipping SLA check")
            return {"checked": 0, "overdue": 0, "urgent": 0, "notifications_sent": 0}

        now = datetime.now(timezone.utc)
        overdue_count = 0
        urgent_count = 0
        notifications_sent = 0

        for task in tasks:
            if task.get("is_completed"):
                continue

            complete_till = task.get("complete_till")
            if not complete_till:
                continue

            try:
                due_time = datetime.fromtimestamp(complete_till, tz=timezone.utc)
            except (ValueError, TypeError):
                continue

            if due_time >= now:
                continue  # Not overdue yet

            overdue_hours = (now - due_time).total_seconds() / 3600

            if overdue_hours >= self.urgent_threshold_hours:
                urgent_count += 1
                await self._handle_urgent_task(task, overdue_hours)
                notifications_sent += 1
            elif overdue_hours >= self.overdue_threshold_hours:
                overdue_count += 1
                await self._handle_overdue_task(task, overdue_hours)
                notifications_sent += 1

        return {
            "checked": len(tasks),
            "overdue": overdue_count,
            "urgent": urgent_count,
            "notifications_sent": notifications_sent,
        }

    async def _fetch_tasks(self, lead_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch tasks from amoCRM."""
        if lead_id:
            return await crm_service._list_tasks(lead_id)

        # Fetch all open leads and their tasks
        # This is a simplified version - in production, you'd want to paginate
        try:
            params = {"filter[statuses][0][pipeline_id]": crm_service.pipeline_id}
            response = await crm_service._request("GET", "/api/v4/leads", params=params)
            leads = response.get("_embedded", {}).get("leads", [])

            all_tasks = []
            for lead in leads[:50]:  # Limit to 50 leads to avoid timeout
                lead_tasks = await crm_service._list_tasks(int(lead["id"]))
                all_tasks.extend(lead_tasks)

            return all_tasks
        except Exception as exc:
            logger.error("Failed to fetch all tasks: %s", exc)
            return []

    async def _handle_overdue_task(self, task: Dict[str, Any], overdue_hours: float) -> None:
        """Handle task overdue >1 hour: notify manager."""
        task_text = task.get("text", "Задача")
        entity_id = task.get("entity_id")
        responsible_id = task.get("responsible_user_id")

        # Get lead name
        lead_name = "Сделка"
        if entity_id:
            try:
                lead_response = await crm_service._request("GET", f"/api/v4/leads/{entity_id}")
                lead_name = lead_response.get("name", "Сделка")
            except Exception:
                pass

        message = (
            f"⚠️ Просрочена задача по сделке {lead_name} (клиент: {lead_name}).\n"
            f"Нужно: {task_text}\n"
            f"Просрочка: {overdue_hours:.1f} ч"
        )

        await whatsapp_service.send_to_manager(message, urgent=False)

        # Create new task with nearest deadline (next 2 hours)
        new_due_at = datetime.now(timezone.utc) + timedelta(hours=2)
        try:
            await crm_service._request(
                "POST",
                "/api/v4/tasks",
                json={
                    "tasks": [
                        {
                            "text": f"Повтор: {task_text}",
                            "complete_till": int(new_due_at.timestamp()),
                            "entity_id": entity_id,
                            "entity_type": "leads",
                            "responsible_user_id": responsible_id,
                        }
                    ]
                },
            )
        except Exception as exc:
            logger.error("Failed to create reminder task: %s", exc)

        # Add note to lead
        if entity_id:
            try:
                await crm_service.add_lead_note(
                    entity_id,
                    "SLA: Просроченная задача",
                    f"Задача '{task_text}' просрочена на {overdue_hours:.1f} ч. Отправлено уведомление менеджеру.",
                )
            except Exception:
                pass

    async def _handle_urgent_task(self, task: Dict[str, Any], overdue_hours: float) -> None:
        """Handle task overdue >4 hours: notify urgent manager."""
        task_text = task.get("text", "Задача")
        entity_id = task.get("entity_id")

        lead_name = "Сделка"
        if entity_id:
            try:
                lead_response = await crm_service._request("GET", f"/api/v4/leads/{entity_id}")
                lead_name = lead_response.get("name", "Сделка")
            except Exception:
                pass

        message = (
            f"🚨 СРОЧНО: Просрочена задача по сделке {lead_name}.\n"
            f"Нужно: {task_text}\n"
            f"Просрочка: {overdue_hours:.1f} ч\n"
            f"Требуется немедленное внимание!"
        )

        await whatsapp_service.send_to_manager(message, urgent=True)

        # Add note to lead
        if entity_id:
            try:
                await crm_service.add_lead_note(
                    entity_id,
                    "SLA: Критическая просрочка",
                    f"Задача '{task_text}' просрочена на {overdue_hours:.1f} ч. Отправлено срочное уведомление руководителю.",
                )
            except Exception:
                pass


sla_monitor_service = SLAMonitorService()

