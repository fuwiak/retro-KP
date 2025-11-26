"""Call transcription service for processing call recordings and creating summaries."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class CallTranscriptionService:
    """Service for transcribing call recordings and generating summaries."""

    def __init__(self) -> None:
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.groq_base_url = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")
        self.groq_model = os.getenv("GROQ_EMAIL_MODEL", "llama-3.1-8b-instant")

        # STT service configuration (placeholder - can be integrated with actual STT service)
        self.stt_service_url = os.getenv("STT_SERVICE_URL", "")
        self.stt_api_key = os.getenv("STT_API_KEY", "")

    async def process_call(
        self,
        recording_url: Optional[str] = None,
        transcription_text: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Process call recording and generate summary.

        Args:
            recording_url: URL to call recording audio file
            transcription_text: Pre-transcribed text (if available)
            metadata: Additional metadata (caller, duration, etc.)

        Returns:
            {
                "transcription": str,
                "summary": str,  # 3-5 line summary
                "topics": List[str],
                "numbers": Dict[str, Any],  # Extracted numbers (prices, quantities, etc.)
                "agreements": List[str],
                "action_items": List[str],
            }
        """
        # If transcription not provided, try to transcribe from recording
        if not transcription_text and recording_url:
            transcription_text = await self._transcribe_audio(recording_url)

        if not transcription_text:
            return {
                "transcription": "",
                "summary": "Транскрипция недоступна",
                "topics": [],
                "numbers": {},
                "agreements": [],
                "action_items": [],
            }

        # Generate summary using LLM
        if self.groq_api_key:
            try:
                return await self._generate_summary_llm(transcription_text, metadata)
            except Exception as exc:
                logger.warning("LLM summary generation failed: %s", exc)

        # Fallback to simple extraction
        return self._extract_summary_simple(transcription_text)

    async def _transcribe_audio(self, recording_url: str) -> Optional[str]:
        """Transcribe audio file to text (placeholder implementation)."""
        if not self.stt_service_url:
            logger.info("STT service not configured, skipping transcription")
            return None

        try:
            # Download audio file
            async with httpx.AsyncClient(timeout=60.0) as client:
                audio_response = await client.get(recording_url)
                if audio_response.is_error:
                    logger.error("Failed to download audio: %s", audio_response.status_code)
                    return None

                # Send to STT service
                stt_response = await client.post(
                    self.stt_service_url,
                    files={"audio": audio_response.content},
                    headers={"Authorization": f"Bearer {self.stt_api_key}"} if self.stt_api_key else {},
                )

                if stt_response.is_error:
                    logger.error("STT service error: %s", stt_response.status_code)
                    return None

                data = stt_response.json()
                return data.get("transcription", "")

        except Exception as exc:
            logger.error("Transcription failed: %s", exc)
            return None

    async def _generate_summary_llm(
        self,
        transcription: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate call summary using Groq LLM."""

        prompt = f"""Создай краткое резюме телефонного разговора (3-5 строк):

Транскрипция:
{transcription[:3000]}

Извлеки:
1. Основная тема разговора
2. Упомянутые цифры (цены, количества, сроки)
3. Договорённости
4. Задачи/действия

Ответь ТОЛЬКО в формате JSON:
{{
  "summary": "краткое резюме 3-5 строк",
  "topics": ["тема1", "тема2"],
  "numbers": {{"price": число, "quantity": число, "deadline": "дата"}},
  "agreements": ["договорённость1"],
  "action_items": ["действие1", "действие2"]
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
            return {
                "transcription": transcription,
                "summary": result.get("summary", "Резюме недоступно"),
                "topics": result.get("topics", []),
                "numbers": result.get("numbers", {}),
                "agreements": result.get("agreements", []),
                "action_items": result.get("action_items", []),
            }
        except (json.JSONDecodeError, ValueError, KeyError) as exc:
            logger.warning("Failed to parse LLM summary: %s", exc)
            return self._extract_summary_simple(transcription)

    def _extract_summary_simple(self, transcription: str) -> Dict[str, Any]:
        """Simple fallback extraction."""
        lines = transcription.split("\n")[:5]
        summary = " ".join(lines[:3])

        return {
            "transcription": transcription,
            "summary": summary[:200],
            "topics": [],
            "numbers": {},
            "agreements": [],
            "action_items": [],
        }


call_transcription_service = CallTranscriptionService()

