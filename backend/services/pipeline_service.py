"""Pipeline detection service for automatically routing leads to correct pipeline."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class PipelineService:
    """Service for detecting request type and routing to correct pipeline."""

    PIPELINE_SALES = "sales"
    PIPELINE_NKU = "nku"
    PIPELINE_SERVICES = "services"

    def __init__(self) -> None:
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.groq_base_url = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
        self.groq_model = os.getenv("GROQ_EMAIL_MODEL", "llama-3.1-8b-instant")

        # Pipeline IDs from environment (can be comma-separated for multiple pipelines)
        self.sales_pipeline_id = self._parse_pipeline_id(os.getenv("AMO_PIPELINE_SALES_ID"))
        self.nku_pipeline_id = self._parse_pipeline_id(os.getenv("AMO_PIPELINE_NKU_ID"))
        self.services_pipeline_id = self._parse_pipeline_id(os.getenv("AMO_PIPELINE_SERVICES_ID"))

        # Default fallback
        self.default_pipeline_id = self._parse_pipeline_id(os.getenv("AMO_PIPELINE_ID"))

    @staticmethod
    def _parse_pipeline_id(value: Optional[str]) -> Optional[int]:
        """Parse pipeline ID from environment variable."""
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    async def detect_pipeline(
        self,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Detect which pipeline (Sales/NKU/Services) the request belongs to.

        Returns:
            {
                "pipeline_type": "sales" | "nku" | "services",
                "pipeline_id": int | None,
                "confidence": float,
                "reason": str,
            }
        """
        if not self.groq_api_key:
            # Fallback to keyword-based detection
            return self._keyword_detection(subject, message)

        try:
            return await self._llm_detection(subject, message, metadata)
        except Exception as exc:
            logger.warning("LLM pipeline detection failed, falling back to keywords: %s", exc)
            return self._keyword_detection(subject, message)

    async def _llm_detection(
        self,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Use Groq LLM to detect pipeline type."""

        prompt = f"""Определи тип заявки клиента и выбери правильную воронку:

Воронки:
1. Продажи (sales) - покупка готового оборудования, товаров, запчастей
2. НКУ (nku) - производство, изготовление на заказ, технические параметры (мощность, ввод, IP)
3. Услуги (services) - выезд специалиста, монтаж, ремонт, обслуживание

Тема: {subject}
Сообщение: {message[:1000]}

Ответь ТОЛЬКО в формате JSON:
{{
  "pipeline_type": "sales" | "nku" | "services",
  "confidence": 0.0-1.0,
  "reason": "краткое объяснение"
}}"""

        url = f"{self.groq_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.groq_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3,
            "response_format": {"type": "json_object"},
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(url, json=payload, headers=headers)

        if response.is_error:
            raise RuntimeError(f"Groq API error: {response.status_code}")

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")

        import json

        try:
            result = json.loads(content)
            pipeline_type = result.get("pipeline_type", "sales")
            confidence = float(result.get("confidence", 0.5))
            reason = result.get("reason", "Определено автоматически")

            pipeline_id = self._get_pipeline_id(pipeline_type)

            return {
                "pipeline_type": pipeline_type,
                "pipeline_id": pipeline_id,
                "confidence": confidence,
                "reason": reason,
            }
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning("Failed to parse LLM response: %s", exc)
            return self._keyword_detection(subject, message)

    def _keyword_detection(self, subject: str, message: str) -> Dict[str, Any]:
        """Fallback keyword-based pipeline detection."""

        text = f"{subject} {message}".lower()

        # НКУ keywords
        nku_keywords = [
            "нку",
            "изготовление",
            "производство",
            "на заказ",
            "мощность",
            "ввод",
            "ip54",
            "ip65",
            "технические параметры",
            "спецификация",
        ]

        # Services keywords
        services_keywords = [
            "выезд",
            "монтаж",
            "установка",
            "ремонт",
            "обслуживание",
            "настройка",
            "диагностика",
            "адрес",
            "визит",
        ]

        nku_score = sum(1 for keyword in nku_keywords if keyword in text)
        services_score = sum(1 for keyword in services_keywords if keyword in text)

        if nku_score > services_score and nku_score > 0:
            pipeline_type = self.PIPELINE_NKU
            confidence = min(0.7, 0.4 + nku_score * 0.1)
            reason = f"Найдено {nku_score} ключевых слов НКУ"
        elif services_score > 0:
            pipeline_type = self.PIPELINE_SERVICES
            confidence = min(0.7, 0.4 + services_score * 0.1)
            reason = f"Найдено {services_score} ключевых слов услуг"
        else:
            pipeline_type = self.PIPELINE_SALES
            confidence = 0.5
            reason = "По умолчанию: Продажи"

        pipeline_id = self._get_pipeline_id(pipeline_type)

        return {
            "pipeline_type": pipeline_type,
            "pipeline_id": pipeline_id,
            "confidence": confidence,
            "reason": reason,
        }

    def _get_pipeline_id(self, pipeline_type: str) -> Optional[int]:
        """Get pipeline ID for given type."""
        mapping = {
            self.PIPELINE_SALES: self.sales_pipeline_id,
            self.PIPELINE_NKU: self.nku_pipeline_id,
            self.PIPELINE_SERVICES: self.services_pipeline_id,
        }
        return mapping.get(pipeline_type) or self.default_pipeline_id


pipeline_service = PipelineService()

