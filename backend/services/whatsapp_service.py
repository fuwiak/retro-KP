"""WhatsApp integration service for sending notifications to managers."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class WhatsAppService:
    """Service for sending WhatsApp messages via 360dialog or Cloud API."""

    def __init__(self) -> None:
        # 360dialog configuration
        self.dialog360_api_key = os.getenv("WHATSAPP_360DIALOG_API_KEY", "")
        self.dialog360_base_url = os.getenv("WHATSAPP_360DIALOG_BASE_URL", "https://waba-api.360dialog.io/v1")

        # WhatsApp Cloud API configuration
        self.cloud_api_token = os.getenv("WHATSAPP_CLOUD_API_TOKEN", "")
        self.cloud_api_phone_id = os.getenv("WHATSAPP_CLOUD_API_PHONE_ID", "")
        self.cloud_api_base_url = os.getenv("WHATSAPP_CLOUD_API_BASE_URL", "https://graph.facebook.com/v18.0")

        # Manager phone numbers (comma-separated)
        manager_phones = os.getenv("WHATSAPP_MANAGER_PHONES", "")
        self.manager_phones = [p.strip() for p in manager_phones.split(",") if p.strip()]

        # Manager phone for urgent notifications
        self.manager_urgent_phone = os.getenv("WHATSAPP_MANAGER_URGENT_PHONE", "")

    async def send_notification(
        self,
        phone: str,
        message: str,
        urgent: bool = False,
    ) -> Dict[str, Any]:
        """Send WhatsApp notification to a phone number.

        Args:
            phone: Phone number in international format (e.g., +77071234567)
            message: Message text
            urgent: If True, use urgent notification channel

        Returns:
            {"status": "sent" | "failed", "provider": str, "error": str | None}
        """
        if not phone:
            return {"status": "failed", "provider": "none", "error": "Phone number is empty"}

        # Try 360dialog first
        if self.dialog360_api_key:
            try:
                result = await self._send_via_360dialog(phone, message)
                if result["status"] == "sent":
                    return result
            except Exception as exc:
                logger.warning("360dialog send failed: %s", exc)

        # Fallback to Cloud API
        if self.cloud_api_token and self.cloud_api_phone_id:
            try:
                result = await self._send_via_cloud_api(phone, message)
                if result["status"] == "sent":
                    return result
            except Exception as exc:
                logger.warning("WhatsApp Cloud API send failed: %s", exc)

        # If no provider configured, log and return placeholder
        logger.info("WhatsApp notification (placeholder): %s -> %s", phone, message[:50])
        return {"status": "placeholder", "provider": "none", "error": "No WhatsApp provider configured"}

    async def send_to_manager(
        self,
        message: str,
        urgent: bool = False,
    ) -> Dict[str, Any]:
        """Send notification to manager(s).

        Args:
            message: Message text
            urgent: If True, send to urgent manager phone

        Returns:
            List of send results
        """
        phones = [self.manager_urgent_phone] if urgent and self.manager_urgent_phone else self.manager_phones

        if not phones:
            logger.info("WhatsApp manager notification (placeholder): %s", message[:50])
            return {"status": "placeholder", "phones": [], "error": "No manager phones configured"}

        results = []
        for phone in phones:
            result = await self.send_notification(phone, message, urgent=urgent)
            results.append(result)

        return {"status": "sent" if any(r.get("status") == "sent" for r in results) else "failed", "results": results}

    async def _send_via_360dialog(self, phone: str, message: str) -> Dict[str, Any]:
        """Send via 360dialog API."""
        url = f"{self.dialog360_base_url}/messages"
        headers = {
            "D360-API-KEY": self.dialog360_api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "recipient_type": "individual",
            "to": phone,
            "type": "text",
            "text": {"body": message},
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.is_error:
            logger.error("360dialog API error (%s): %s", response.status_code, response.text)
            return {"status": "failed", "provider": "360dialog", "error": response.text}

        return {"status": "sent", "provider": "360dialog", "error": None}

    async def _send_via_cloud_api(self, phone: str, message: str) -> Dict[str, Any]:
        """Send via WhatsApp Cloud API."""
        url = f"{self.cloud_api_base_url}/{self.cloud_api_phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.cloud_api_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "messaging_product": "whatsapp",
            "to": phone,
            "type": "text",
            "text": {"body": message},
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.is_error:
            logger.error("WhatsApp Cloud API error (%s): %s", response.status_code, response.text)
            return {"status": "failed", "provider": "cloud_api", "error": response.text}

        return {"status": "sent", "provider": "cloud_api", "error": None}


whatsapp_service = WhatsAppService()

