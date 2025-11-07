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
        self.imap_username = os.getenv("IMAP_USERNAME", "")
        self.imap_password = os.getenv("IMAP_PASSWORD", "")
        self.imap_folder = os.getenv("IMAP_FOLDER", "INBOX")

        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.groq_base_url = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
        self.groq_email_model = os.getenv("GROQ_EMAIL_MODEL", "llama-3.1-8b-instant")
        self.groq_proposal_model = os.getenv("GROQ_PROPOSAL_MODEL", self.groq_email_model)

        self._nlp = self._load_nlp_model()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch_emails(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch latest emails from the IMAP inbox.

        The result is ordered from newest to oldest.
        """

        if not self.imap_server or not self.imap_username or not self.imap_password:
            raise ValueError("IMAP configuration is incomplete. Check IMAP_* environment variables.")

        mail = imaplib.IMAP4_SSL(self.imap_server, self.imap_port)
        try:
            mail.login(self.imap_username, self.imap_password)
            mail.select(self.imap_folder)

            status, data = mail.search(None, "ALL")
            if status != "OK":
                raise RuntimeError("Failed to search inbox")

            message_ids = data[0].split()
            if not message_ids:
                return []

            last_ids = message_ids[-limit:]
            emails: List[Dict[str, Any]] = []

            for msg_id in reversed(last_ids):
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
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse Groq response as JSON: %s", response_text)
            return {
                "suitable_for_proposal": False,
                "confidence": 0.0,
                "reason": "Ошибка LLM",
                "category": "error",
                "potential_services": [],
            }


email_analysis_service = EmailAnalysisService()


