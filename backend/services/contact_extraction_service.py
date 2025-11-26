"""Service for extracting contact information from email content."""

import re
import logging
from typing import Dict, Any, Optional
import os

logger = logging.getLogger(__name__)


class ContactExtractionService:
    """Service for extracting phone numbers and company names from email content."""

    def __init__(self) -> None:
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.groq_base_url = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
        self.groq_model = os.getenv("GROQ_EMAIL_MODEL", "llama-3.1-8b-instant")

    def extract_phone_regex(self, text: str) -> Optional[str]:
        """Extract phone number using regex patterns."""
        if not text:
            return None

        # Russian phone patterns
        patterns = [
            r"\+?7\s?\(?\d{3}\)?\s?\d{3}[\s-]?\d{2}[\s-]?\d{2}",  # +7 (XXX) XXX-XX-XX
            r"\+?7\s?\d{10}",  # +7XXXXXXXXXX
            r"\+?\d{1,3}[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}",  # International
            r"8\s?\(?\d{3}\)?\s?\d{3}[\s-]?\d{2}[\s-]?\d{2}",  # 8 (XXX) XXX-XX-XX
        ]

        for pattern in patterns:
            matches = re.findall(pattern, text)
            if matches:
                # Clean up the phone number
                phone = re.sub(r"[\s().-]", "", matches[0])
                if len(phone) >= 10:
                    return phone

        return None

    def extract_company_regex(self, text: str) -> Optional[str]:
        """Extract company name using regex patterns."""
        if not text:
            return None

        # Company name patterns
        patterns = [
            (r"(?:ООО|ТОО|ИП|АО|ЗАО|ПАО)\s*["«]?([^"»\n,]{2,50})["»]?", 1),
            (r"(?:компания|фирма|организация)\s*["«]?([^"»\n,]{2,50})["»]?", 1),
            (r"["«]([^"»\n,]{3,50})["»]", 1),
            (r"(?:от|от имени)\s+([А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+)", 1),
        ]

        for pattern, group in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match and match.group(group):
                company = match.group(group).strip()
                # Clean up common prefixes
                company = re.sub(r"^(ООО|ТОО|ИП|АО|ЗАО|ПАО)\s+", "", company, flags=re.IGNORECASE)
                if len(company) >= 2:
                    return company

        return None

    async def extract_contact_info_llm(self, subject: str, body: str) -> Dict[str, Optional[str]]:
        """Extract contact information using Groq LLM."""
        if not self.groq_api_key:
            return {"phone": None, "company": None}

        try:
            import httpx

            prompt = f"""Извлеки из следующего письма номер телефона и название компании.

Тема: {subject}
Текст: {body[:1000]}

Ответь ТОЛЬКО в формате JSON:
{{
  "phone": "номер телефона или null",
  "company": "название компании или null"
}}

Если информации нет, верни null."""

            url = f"{self.groq_base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.groq_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
            }

            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(url, json=payload, headers=headers)

            if response.is_error:
                logger.warning("Groq API error for contact extraction: %s", response.status_code)
                return {"phone": None, "company": None}

            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")

            try:
                import json
                result = json.loads(content)
                return {
                    "phone": result.get("phone") if result.get("phone") != "null" else None,
                    "company": result.get("company") if result.get("company") != "null" else None,
                }
            except (json.JSONDecodeError, ValueError):
                logger.warning("Failed to parse Groq contact extraction response")
                return {"phone": None, "company": None}

        except Exception as exc:
            logger.warning("Contact extraction via LLM failed: %s", exc)
            return {"phone": None, "company": None}

    async def extract_contact_info(
        self, subject: str, body: str, sender: str = ""
    ) -> Dict[str, Optional[str]]:
        """Extract phone and company from email content using multiple strategies."""
        full_text = f"{subject} {body} {sender}".strip()

        # Strategy 1: Regex extraction
        phone = self.extract_phone_regex(full_text)
        company = self.extract_company_regex(full_text)

        # Strategy 2: If regex didn't find anything, try LLM
        if not phone or not company:
            llm_result = await self.extract_contact_info_llm(subject, body)
            if not phone:
                phone = llm_result.get("phone")
            if not company:
                company = llm_result.get("company")

        return {"phone": phone, "company": company}


contact_extraction_service = ContactExtractionService()

