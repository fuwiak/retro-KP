"""Data extraction service for extracting product, quantity, price, deadlines from correspondence."""

from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


class DataExtractionService:
    """Service for extracting structured data from customer correspondence."""

    def __init__(self) -> None:
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.groq_base_url = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
        self.groq_model = os.getenv("GROQ_EMAIL_MODEL", "llama-3.1-8b-instant")

    async def extract_deal_data(
        self,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Extract structured data from correspondence.

        Returns:
            {
                "products": [{"name": str, "quantity": float, "price": float, "unit": str}],
                "total_amount": float | None,
                "deadline": str | None,
                "delivery_address": str | None,
                "technical_params": Dict[str, Any] | None,
                "confidence": float,
            }
        """
        if not self.groq_api_key:
            return self._regex_extraction(message)

        try:
            return await self._llm_extraction(subject, message, metadata)
        except Exception as exc:
            logger.warning("LLM extraction failed, falling back to regex: %s", exc)
            return self._regex_extraction(message)

    async def _llm_extraction(
        self,
        subject: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Use Groq LLM to extract structured data."""

        prompt = f"""Извлеки структурированные данные из запроса клиента:

Тема: {subject}
Сообщение: {message[:2000]}

Извлеки:
- Товары/услуги (название, количество, цена за единицу, единица измерения)
- Общая сумма (если указана)
- Сроки/дедлайн (дата или описание)
- Адрес доставки/выполнения работ
- Технические параметры (мощность, напряжение, IP, размеры и т.д.)

Ответь ТОЛЬКО в формате JSON:
{{
  "products": [
    {{"name": "название", "quantity": число, "price": число, "unit": "шт/м/кг"}}
  ],
  "total_amount": число или null,
  "deadline": "дата или описание" или null,
  "delivery_address": "адрес" или null,
  "technical_params": {{"key": "value"}} или null,
  "confidence": 0.0-1.0
}}"""

        url = f"{self.groq_base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.groq_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
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
            return {
                "products": result.get("products", []),
                "total_amount": result.get("total_amount"),
                "deadline": result.get("deadline"),
                "delivery_address": result.get("delivery_address"),
                "technical_params": result.get("technical_params"),
                "confidence": float(result.get("confidence", 0.5)),
            }
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning("Failed to parse LLM extraction: %s", exc)
            return self._regex_extraction(message)

    def _regex_extraction(self, message: str) -> Dict[str, Any]:
        """Fallback regex-based extraction."""

        products = []
        total_amount = None
        deadline = None
        delivery_address = None

        # Extract amounts (KZT, тенге, рубль, etc.)
        amount_pattern = r"(\d+(?:[.,]\d+)?)\s*(?:тенге|тг|kzt|рубл|₽|₸)"
        amounts = re.findall(amount_pattern, message, re.IGNORECASE)
        if amounts:
            try:
                total_amount = float(amounts[-1].replace(",", "."))
            except ValueError:
                pass

        # Extract quantities
        qty_pattern = r"(\d+)\s*(?:шт|штук|единиц|м|метров|кг|килограмм)"
        quantities = re.findall(qty_pattern, message, re.IGNORECASE)
        if quantities:
            try:
                qty = float(quantities[0])
                products.append({"name": "Товар", "quantity": qty, "price": None, "unit": "шт"})
            except ValueError:
                pass

        # Extract dates (simple patterns)
        date_pattern = r"(\d{1,2}[./-]\d{1,2}[./-]\d{2,4})|(до\s+\d{1,2}[./-]\d{1,2})"
        dates = re.findall(date_pattern, message, re.IGNORECASE)
        if dates:
            deadline = dates[0][0] if dates[0][0] else dates[0][1]

        return {
            "products": products,
            "total_amount": total_amount,
            "deadline": deadline,
            "delivery_address": delivery_address,
            "technical_params": None,
            "confidence": 0.3,
        }


data_extraction_service = DataExtractionService()

