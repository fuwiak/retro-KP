"""
Translation Service using Groq AI API
Handles technical translation with glossary support
"""

import os
import httpx
from typing import Dict, Optional

# Groq API configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_BASE = "https://api.groq.com/openai/v1"

# Model priority list
TRANSLATION_MODELS = [
    "llama-3.3-70b-versatile",  # Best quality
    "llama-3.1-8b-instant",     # Fast
    "openai/gpt-oss-20b",       # Fallback
]

# Technical glossary (Russian to English)
TECHNICAL_GLOSSARY = {
    "материал": "material",
    "сталь": "steel",
    "ГОСТ": "GOST",
    "ОСТ": "OST",
    "ТУ": "TU",
    "посадка": "fit",
    "термообработка": "heat treatment",
    "шероховатость": "roughness",
    "Ra": "Ra",
    "точность": "accuracy",
    "допуск": "tolerance",
    "размер": "size",
    "диаметр": "diameter",
    "длина": "length",
    "ширина": "width",
    "высота": "height",
    "толщина": "thickness",
}


class TranslationService:
    """Service for translation using Groq AI with technical glossary"""
    
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.api_base = GROQ_API_BASE
        self.models = TRANSLATION_MODELS
        self.glossary = TECHNICAL_GLOSSARY
    
    def is_available(self) -> bool:
        """Check if translation service is available"""
        return bool(self.api_key)
    
    def _apply_glossary(self, text: str) -> str:
        """Apply technical glossary before AI translation"""
        translated = text
        for ru_term, en_term in self.glossary.items():
            # Use word boundaries for better matching
            import re
            pattern = re.compile(r'\b' + re.escape(ru_term) + r'\b', re.IGNORECASE)
            translated = pattern.sub(en_term, translated)
        return translated
    
    async def _call_groq_api(
        self,
        model: str,
        messages: list,
        options: Optional[Dict] = None
    ) -> str:
        """Call Groq API with a specific model"""
        if not self.api_key:
            raise ValueError("Groq API key not configured")
        
        request_body = {
            "model": model,
            "messages": messages,
            "temperature": options.get("temperature", 0.3) if options else 0.3,
            "max_tokens": options.get("max_tokens", 4096) if options else 4096,
        }
        
        if options:
            request_body.update({k: v for k, v in options.items() if k not in ["temperature", "max_tokens"]})
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
                timeout=60.0
            )
            
            if not response.is_success:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get("error", {}).get("message", f"HTTP {response.status_code}")
                raise Exception(f"Groq API error: {error_msg}")
            
            data = response.json()
            if data.get("choices") and data["choices"][0].get("message"):
                return data["choices"][0]["message"]["content"]
            else:
                raise Exception("Invalid response format from Groq API")
    
    async def _translate_with_fallback(
        self,
        messages: list,
        options: Optional[Dict] = None
    ) -> str:
        """Try multiple models with fallback"""
        last_error = None
        
        for i, model in enumerate(self.models):
            try:
                return await self._call_groq_api(model, messages, options)
            except Exception as e:
                last_error = e
                if i < len(self.models) - 1:
                    continue  # Try next model
                else:
                    raise last_error
        
        raise Exception("All translation models failed")
    
    async def translate(
        self,
        text: str,
        from_lang: str = "ru",
        to_lang: str = "en",
        use_glossary: bool = True
    ) -> str:
        """
        Translate text using Groq AI with technical glossary
        """
        if not self.api_key:
            raise ValueError("Groq API key not configured. Set GROQ_API_KEY in .env")
        
        # Apply glossary first if Russian to English
        if use_glossary and from_lang.lower() in ["ru", "rus", "russian"] and to_lang.lower() in ["en", "eng", "english"]:
            text = self._apply_glossary(text)
        
        # Create translation prompt
        lang_names = {
            "ru": "Russian",
            "rus": "Russian",
            "russian": "Russian",
            "en": "English",
            "eng": "English",
            "english": "English"
        }
        
        from_lang_name = lang_names.get(from_lang.lower(), from_lang)
        to_lang_name = lang_names.get(to_lang.lower(), to_lang)
        
        prompt = f"""Translate the following technical text from {from_lang_name} to {to_lang_name}.
Preserve technical terms, abbreviations, and formatting.
Return ONLY the translation, without explanations.

Text to translate:
{text}"""
        
        messages = [
            {
                "role": "system",
                "content": "You are an expert technical translator specializing in engineering and manufacturing documents."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        try:
            translated = await self._translate_with_fallback(messages)
            return translated.strip()
        except Exception as e:
            # Fallback: return glossary-translated text if available
            if use_glossary:
                return text
            raise Exception(f"Translation failed: {str(e)}")

