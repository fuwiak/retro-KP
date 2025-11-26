"""Email analysis and proposal generation service."""

from __future__ import annotations

import asyncio
import imaplib
import json
import logging
import os
import re
from email import message_from_bytes
from email.header import decode_header
from typing import Any, Dict, List, Optional

import httpx

try:
    import spacy
except ImportError:  # pragma: no cover - handled via requirements
    spacy = None  # type: ignore


logger = logging.getLogger(__name__)


class EmailAnalysisService:
    """Service responsible for fetching and analysing IMAP emails."""

    def __init__(self) -> None:
        self.imap_server = os.getenv("IMAP_SERVER", "")
        self.imap_port = int(os.getenv("IMAP_PORT", "993") or 993)
        # Support both IMAP_USERNAME and IMAP_USER for backward compatibility
        self.imap_username = os.getenv("IMAP_USERNAME") or os.getenv("IMAP_USER", "")
        self.imap_password = os.getenv("IMAP_PASSWORD", "")
        self.imap_folder = os.getenv("IMAP_FOLDER", "INBOX")

        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.groq_base_url = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
        self.groq_email_model = os.getenv("GROQ_EMAIL_MODEL", "llama-3.1-8b-instant")
        self.groq_proposal_model = os.getenv("GROQ_PROPOSAL_MODEL", self.groq_email_model)

        self._nlp = self._load_nlp_model()
        self._mock_mode = False  # Mock mode flag

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def fetch_emails_async(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch emails (real or mock) asynchronously."""
        if self._mock_mode:
            return await self.generate_mock_emails(limit)
        return await asyncio.to_thread(self.fetch_emails, limit)

    def fetch_emails(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch latest emails from the IMAP inbox.

        The result is ordered from newest to oldest.
        """

        if self._mock_mode:
            # This shouldn't be called in mock mode, but handle it gracefully
            logger.warning("fetch_emails called in mock mode, use fetch_emails_async instead")
            return []

        if not self.imap_server or not self.imap_username or not self.imap_password:
            raise ValueError("IMAP configuration is incomplete. Check IMAP_* environment variables.")

        mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
        try:
            try:
                mail.login(self.imap_username, self.imap_password)
            except imaplib.IMAP4.error as exc:
                error_msg = str(exc)
                # Gmail-specific error handling
                if "Lookup failed" in error_msg or "Invalid credentials" in error_msg:
                    if "gmail.com" in self.imap_server.lower():
                        raise ValueError(
                            "Gmail authentication failed. Gmail requires an App Password instead of regular password. "
                            "Please:\n"
                            "1. Enable 2-Step Verification in your Google Account\n"
                            "2. Generate an App Password: https://myaccount.google.com/apppasswords\n"
                            "3. Use the App Password in IMAP_PASSWORD (not your regular password)"
                        ) from exc
                    else:
                        raise ValueError(
                            f"IMAP authentication failed: {error_msg}. "
                            "Please check IMAP_USERNAME and IMAP_PASSWORD."
                        ) from exc
                else:
                    raise ValueError(f"IMAP login error: {error_msg}") from exc

            try:
                mail.select(self.imap_folder)
            except imaplib.IMAP4.error as exc:
                raise ValueError(
                    f"Failed to select folder '{self.imap_folder}': {exc}. "
                    f"Available folders might be different. Check IMAP_FOLDER setting."
                ) from exc

            status, data = mail.search(None, "ALL")
            if status != "OK":
                raise RuntimeError(f"Failed to search inbox: {status}")

            message_ids = data[0].split()
            if not message_ids:
                return []

            last_ids = message_ids[-limit:]
            emails: List[Dict[str, Any]] = []

            for msg_id in reversed(last_ids):
                try:
                    status, msg_data = mail.fetch(msg_id, "(RFC822)")
                    if status != "OK" or not msg_data or msg_data[0] is None:
                        logger.warning("Failed to fetch message %s", msg_id)
                        continue

                    raw_email = msg_data[0][1]
                    message = message_from_bytes(raw_email)

                    subject = self._clean_subject(message.get("Subject"))
                    sender = message.get("From", "")
                    date = message.get("Date", "")
                    body = self._extract_body(message)

                    nlp_category = self.simple_nlp_filter(subject, sender, body)

                    emails.append(
                        {
                            "id": msg_id.decode() if isinstance(msg_id, bytes) else str(msg_id),
                            "subject": subject,
                            "sender": sender,
                            "date": date,
                            "bodyPreview": body[:300],
                            "fullBody": body,
                            "nlpCategory": nlp_category,
                        }
                    )
                except Exception as exc:
                    logger.warning("Error processing message %s: %s", msg_id, exc)
                    continue

            return emails
        finally:
            try:
                mail.logout()
            except Exception:  # pragma: no cover - best effort cleanup
                pass

    async def classify_email_llm(self, subject: str, sender: str, body: str) -> Dict[str, Any]:
        """Classify email using Groq LLM."""

        if not self.groq_api_key:
            return {
                "suitable_for_proposal": False,
                "confidence": 0.0,
                "reason": "Missing GROQ_API_KEY",
                "category": "error",
                "potential_services": [],
            }

        prompt = self._build_classification_prompt(subject, sender, body)
        response_text = await self._call_groq_chat_completion(
            prompt=prompt,
            model=self.groq_email_model,
            temperature=0.12,
            max_tokens=512,
        )

        return self._parse_json_response(response_text)

    async def generate_proposal(self, subject: str, body: str) -> str:
        """Generate commercial proposal text for the email."""

        if not self.groq_api_key:
            raise RuntimeError("Missing GROQ_API_KEY for proposal generation")

        prompt = self._build_proposal_prompt(subject, body)
        kp_text = await self._call_groq_chat_completion(
            prompt=prompt,
            model=self.groq_proposal_model,
            temperature=0.18,
            max_tokens=512,
        )

        return self.clean_markdown(kp_text)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def simple_nlp_filter(self, subject: str, sender: str, body: str) -> str:
        """Heuristic classifier replicating original Streamlit logic."""

        lower_subj = (subject or "").lower()
        lower_body = (body or "").lower()

        spam_keywords = [
            "unsubscribe",
            "рассылка",
            "не отвечайте на это письмо",
            "спам",
            "уведомление",
            "автоматически",
            "auto reply",
            "no-reply",
            "уведомление о доставке",
            "delivery notification",
        ]

        commercial_keywords = [
            "запрос",
            "расчет",
            "коммерческое предложение",
            "договор",
            "предложение",
            "invoice",
            "прайс",
            "прайс-лист",
            "покупка",
            "цена",
            "quotation",
            "purchase",
            "offer",
        ]

        if any(word in lower_subj or word in lower_body for word in spam_keywords):
            return "spam"

        if any(word in lower_subj or word in lower_body for word in commercial_keywords):
            return "potential"

        if self._nlp:
            doc = self._nlp(f"{subject} {body}")
            for ent in doc.ents:
                if ent.label_ in {"ORG", "PRODUCT", "MONEY", "EVENT"}:
                    return "potential"

        return "other"

    def clean_markdown(self, text: str) -> str:
        """Remove basic Markdown formatting from text."""

        cleaned = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
        cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
        cleaned = cleaned.replace("**", "").replace("##", "").replace("#", "")
        return cleaned.strip()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_nlp_model(self):  # type: ignore[override]
        """Load Russian spaCy model with graceful fallback."""

        if spacy is None:  # pragma: no cover - dependency guard
            logger.warning("spaCy is not installed; NLP filtering will be limited")
            return None

        try:
            return spacy.load("ru_core_news_sm")
        except OSError:
            logger.warning("spaCy model 'ru_core_news_sm' not found. Falling back to blank Russian model.")
            return spacy.blank("ru")
        except Exception as exc:  # pragma: no cover
            logger.error("Failed to load spaCy model: %s", exc)
            return None

    def _extract_body(self, message) -> str:
        """Extract text body from email message."""

        body = ""
        if message.is_multipart():
            for part in message.walk():
                disposition = part.get("Content-Disposition") or ""
                if part.get_content_type() == "text/plain" and "attachment" not in disposition:
                    charset = part.get_content_charset()
                    try:
                        body = part.get_payload(decode=True).decode(charset or "utf-8", errors="replace")
                    except Exception:
                        body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                    break
        else:
            charset = message.get_content_charset()
            try:
                body = message.get_payload(decode=True).decode(charset or "utf-8", errors="replace")
            except Exception:
                payload = message.get_payload(decode=True)
                body = (payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else str(payload))

        return body or ""

    def _clean_subject(self, subject: Optional[str]) -> str:
        if not subject:
            return ""

        decoded, charset = decode_header(subject)[0]
        if isinstance(decoded, bytes):
            try:
                return decoded.decode(charset or "utf-8", errors="replace")
            except Exception:
                return decoded.decode("utf-8", errors="replace")
        return decoded

    def _build_classification_prompt(self, subject: str, sender: str, body: str) -> str:
        return (
            "Проанализируй письмо и определи, подходит ли оно для отправки коммерческого предложения.\n"
            f"Тема письма: {subject}\n"
            f"Отправитель: {sender}\n"
            "Содержание письма:\n"
            f"{body}\n\n"
            "Определи следующие критерии:\n"
            "1. Является ли это потенциальным запросом на услуги/товары?\n"
            "2. Содержит ли письмо признаки коммерческого интереса?\n"
            "3. Не является ли это спамом, рекламой или автоматическим уведомлением?\n"
            "4. Подходит ли тон письма для деловой переписки?\n\n"
            "Ответь в формате JSON:{\n"
            "    \"suitable_for_proposal\": true/false,\n"
            "    \"confidence\": 0.0-1.0,\n"
            "    \"reason\": \"краткое объяснение решения\",\n"
            "    \"category\": \"inquiry/spam/notification/other\",\n"
            "    \"potential_services\": [\"список возможных услуг если подходит\"]\n"
            "}"
        )

    def _build_proposal_prompt(self, subject: str, body: str) -> str:
        return (
            "Составь краткое коммерческое предложение (КП) для ответа на это письмо. \n"
            "ВАЖНО: Пиши обычным текстом БЕЗ markdown-разметки. Не используй символы **, ##, # для форматирования.\n"
            "Используй только простой текст с переносами строк.\n\n"
            f"Тема: {subject}\n"
            f"Текст запроса: {body}\n"
        )

    async def _call_groq_chat_completion(
        self,
        prompt: str,
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{self.groq_base_url}/chat/completions",
                headers=headers,
                json=payload,
            )

        if response.is_error:
            logger.error("Groq API error (%s): %s", response.status_code, response.text)
            raise RuntimeError("Groq API request failed")

        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON response with multiple fallback strategies."""
        
        if not response_text:
            return self._default_classification_response("Пустой ответ LLM")
        
        # Strategy 1: Try direct JSON parse
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # Strategy 2: Extract JSON from markdown code blocks (```json ... ```)
        json_block_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
        matches = re.findall(json_block_pattern, response_text, re.DOTALL)
        if matches:
            for match in matches:
                try:
                    return json.loads(match)
                except json.JSONDecodeError:
                    continue
        
        # Strategy 3: Find JSON object in text (look for {...})
        json_object_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
        matches = re.findall(json_object_pattern, response_text, re.DOTALL)
        for match in matches:
            try:
                parsed = json.loads(match)
                # Validate it has expected structure
                if isinstance(parsed, dict) and "suitable_for_proposal" in parsed:
                    return parsed
            except json.JSONDecodeError:
                continue
        
        # Strategy 4: Try to extract JSON after "json" keyword
        json_after_keyword = re.search(r"(?:json|JSON)[\s:]*(\{.*\})", response_text, re.DOTALL)
        if json_after_keyword:
            try:
                return json.loads(json_after_keyword.group(1))
            except (json.JSONDecodeError, AttributeError):
                pass
        
        # Strategy 5: Try to find and parse the largest JSON-like structure
        # Look for content between first { and last }
        first_brace = response_text.find("{")
        last_brace = response_text.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            json_candidate = response_text[first_brace:last_brace + 1]
            try:
                parsed = json.loads(json_candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        
        # Strategy 6: Try to extract key-value pairs and build JSON manually
        extracted = self._extract_classification_from_text(response_text)
        if extracted:
            return extracted
        
        # All strategies failed
        logger.warning("Failed to parse Groq response as JSON after all fallbacks: %s", response_text[:200])
        return self._default_classification_response("Не удалось распарсить ответ LLM")
    
    def _extract_classification_from_text(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract classification data from unstructured text using regex."""
        result = {
            "suitable_for_proposal": False,
            "confidence": 0.5,
            "reason": "",
            "category": "other",
            "potential_services": [],
        }
        
        # Extract suitable_for_proposal
        if re.search(r'"suitable_for_proposal"\s*:\s*(true|True|TRUE)', text):
            result["suitable_for_proposal"] = True
        elif re.search(r'"suitable_for_proposal"\s*:\s*(false|False|FALSE)', text):
            result["suitable_for_proposal"] = False
        
        # Extract confidence
        confidence_match = re.search(r'"confidence"\s*:\s*([0-9.]+)', text)
        if confidence_match:
            try:
                result["confidence"] = float(confidence_match.group(1))
            except ValueError:
                pass
        
        # Extract reason
        reason_match = re.search(r'"reason"\s*:\s*"([^"]+)"', text)
        if reason_match:
            result["reason"] = reason_match.group(1)
        
        # Extract category
        category_match = re.search(r'"category"\s*:\s*"([^"]+)"', text)
        if category_match:
            result["category"] = category_match.group(1)
        
        # Extract potential_services
        services_match = re.search(r'"potential_services"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if services_match:
            services_text = services_match.group(1)
            services = re.findall(r'"([^"]+)"', services_text)
            result["potential_services"] = services
        
        # Only return if we found at least some useful data
        if result.get("reason") or result.get("category") != "other":
            return result
        
        return None
    
    def _default_classification_response(self, reason: str) -> Dict[str, Any]:
        """Return default classification response."""
        return {
            "suitable_for_proposal": False,
            "confidence": 0.0,
            "reason": reason,
            "category": "error",
            "potential_services": [],
        }

    async def generate_mock_emails(self, count: int = 10) -> List[Dict[str, Any]]:
        """Generate realistic mock emails using Groq LLM."""
        
        if not self.groq_api_key:
            # Fallback to simple mock data
            return self._generate_simple_mock_emails(count)

        try:
            prompt = f"""Создай {count} реалистичных входящих писем от клиентов для CRM системы.

Письма должны быть разнообразными:
- Запросы на оборудование (АВР, контакторы, реле)
- Запросы на услуги (монтаж, ремонт, обслуживание)
- Запросы на изготовление на заказ (НКУ)
- Разные компании и имена
- Разные суммы и сроки

Каждое письмо должно содержать:
- Реалистичное имя отправителя и email
- Тему письма
- Текст запроса с деталями (товары, количество, цены, сроки, адреса)
- Номер телефона в формате +7 (XXX) XXX-XX-XX или +7XXXXXXXXXX
- Название компании (ООО, ТОО, ИП и т.д.)

Ответь ТОЛЬКО в формате JSON объекта с ключом "emails":
{{
  "emails": [
    {{
      "sender": "Имя Фамилия <email@example.com>",
      "subject": "Тема письма",
      "body": "Полный текст письма с деталями запроса. В тексте обязательно должен быть номер телефона и название компании.",
      "date": "2025-11-26 10:30:00",
      "phone": "+7 (XXX) XXX-XX-XX",
      "company": "ООО Название компании"
    }},
    ...
  ]
}}

Важно: письма должны быть реалистичными и разнообразными."""

            url = f"{self.groq_base_url}/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.groq_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": self.groq_email_model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.8,
                "response_format": {"type": "json_object"},
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, json=payload, headers=headers)

            if response.is_error:
                logger.warning("Groq API error for mock generation, using fallback: %s", response.status_code)
                return self._generate_simple_mock_emails(count)

            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "{}")

            try:
                result = json.loads(content)
                # Handle both {"emails": [...]} and [...] formats
                emails_data = result.get("emails", result) if isinstance(result, dict) else result
                
                if not isinstance(emails_data, list):
                    emails_data = [emails_data]

                mock_emails = []
                for idx, email_data in enumerate(emails_data[:count]):
                    subject = email_data.get("subject", f"Запрос #{idx + 1}")
                    body = email_data.get("body", "")
                    sender = email_data.get("sender", f"Клиент {idx + 1} <client{idx + 1}@example.com>")
                    date_str = email_data.get("date", "")
                    phone = email_data.get("phone", "")
                    company = email_data.get("company", "")

                    # Ensure phone and company are in the body if provided
                    if phone and phone not in body:
                        body = f"{body}\n\nКонтактный телефон: {phone}"
                    if company and company not in body:
                        body = f"{body}\n\nКомпания: {company}"

                    nlp_category = self.simple_nlp_filter(subject, sender, body)

                    mock_emails.append({
                        "id": f"mock_{idx + 1}",
                        "subject": subject,
                        "sender": sender,
                        "date": date_str or f"2025-11-26 {10 + idx}:00:00",
                        "bodyPreview": body[:300],
                        "fullBody": body,
                        "nlpCategory": nlp_category,
                        "extractedPhone": phone,
                        "extractedCompany": company,
                    })

                return mock_emails
            except (json.JSONDecodeError, ValueError, KeyError) as exc:
                logger.warning("Failed to parse Groq mock response: %s", exc)
                return self._generate_simple_mock_emails(count)

        except Exception as exc:
            logger.warning("Mock email generation failed: %s", exc)
            return self._generate_simple_mock_emails(count)

    def _generate_simple_mock_emails(self, count: int) -> List[Dict[str, Any]]:
        """Generate simple mock emails without Groq."""
        from datetime import datetime, timedelta

        mock_templates = [
            {
                "sender": "Иван Петров <ivan.petrov@company.kz>",
                "subject": "Запрос на АВР Stalker Electric 630А",
                "body": "Добрый день! Нужен АВР Stalker Electric Т1+Т2, 630А, 400В, IP54. Количество: 2 шт. Срок доставки: до 15.12.2025. Адрес: г. Алматы, ул. Абая 150.",
            },
            {
                "sender": "Мария Смирнова <maria@service.kz>",
                "subject": "Требуется монтаж электрооборудования",
                "body": "Здравствуйте! Нужен выезд специалиста для монтажа АВР на объекте. Адрес: г. Астана, пр. Кабанбай батыра 25. Дата: 20.12.2025. Мощность: 400А.",
            },
            {
                "sender": "ТОО ЭнергоСервис <info@energo.kz>",
                "subject": "Изготовление НКУ на заказ",
                "body": "Добрый день! Требуется изготовление НКУ на заказ. Параметры: мощность 630А, ввод 400В, IP54. Количество: 1 комплект. Срок изготовления: 30 дней.",
            },
            {
                "sender": "Алексей Козлов <alex@tech.kz>",
                "subject": "Запрос на контакторы Siemens",
                "body": "Нужны контакторы Siemens 3RT2026-1AP00 в количестве 5 шт. Цена: 8000 тенге за штуку. Доставка в г. Шымкент.",
            },
            {
                "sender": "ООО ПромЭнерго <sales@promenergo.kz>",
                "subject": "Ремонт АВР на объекте",
                "body": "Требуется срочный ремонт АВР на объекте. Адрес выезда: г. Караганда, ул. Бухар жырау 45. Дата: срочно. Контакт: +7 777 123 4567.",
            },
        ]

        mock_emails = []
        base_date = datetime.now()

        for idx in range(count):
            template = mock_templates[idx % len(mock_templates)]
            email_date = base_date - timedelta(hours=count - idx)

            # Ensure phone and company are in the body
            body = template["body"]
            phone = template.get("phone", "")
            company = template.get("company", "")
            
            if phone and phone not in body:
                body = f"{body}\n\nКонтактный телефон: {phone}"
            if company and company not in body:
                body = f"{body}\n\nКомпания: {company}"

            nlp_category = self.simple_nlp_filter(
                template["subject"],
                template["sender"],
                body
            )

            mock_emails.append({
                "id": f"mock_{idx + 1}",
                "subject": template["subject"],
                "sender": template["sender"],
                "date": email_date.strftime("%Y-%m-%d %H:%M:%S"),
                "bodyPreview": body[:300],
                "fullBody": body,
                "nlpCategory": nlp_category,
                "extractedPhone": phone,
                "extractedCompany": company,
            })

        return mock_emails

    def set_mock_mode(self, enabled: bool) -> None:
        """Enable or disable mock data mode."""
        self._mock_mode = enabled
        logger.info(f"Mock mode {'enabled' if enabled else 'disabled'}")

    def is_mock_mode(self) -> bool:
        """Check if mock mode is enabled."""
        return self._mock_mode


email_analysis_service = EmailAnalysisService()


