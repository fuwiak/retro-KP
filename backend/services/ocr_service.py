"""
OCR Service using Groq AI API and Tesseract
Handles PDF and image OCR with intelligent method selection
"""

import os
import base64
import httpx
from typing import List, Dict, Optional
import io
import time

try:
    import pytesseract
    from PIL import Image
    try:
        from pdf2image import convert_from_bytes
        PDF2IMAGE_AVAILABLE = True
    except ImportError:
        PDF2IMAGE_AVAILABLE = False
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    PDF2IMAGE_AVAILABLE = False

from services.ocr_agent import OCREvaluationAgent, ProcessingMethod
from services.logger import ocr_logger, log_ocr_request, log_ocr_result

# Groq API configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_BASE = "https://api.groq.com/openai/v1"

# Model priority list with fallbacks
OCR_MODELS = [
    "groq/compound",           # Best for complex tasks
    "llama-3.3-70b-versatile", # High quality
    "llama-3.1-8b-instant",    # Fast fallback
]


class OCRService:
    """Service for OCR processing using Groq AI"""
    
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.api_base = GROQ_API_BASE
        self.models = OCR_MODELS
        self.agent = OCREvaluationAgent()
        self.tesseract_available = TESSERACT_AVAILABLE
        self.pdf2image_available = PDF2IMAGE_AVAILABLE
    
    def is_available(self) -> bool:
        """Check if OCR service is available"""
        return bool(self.api_key) or self.tesseract_available
    
    async def _call_groq_api(
        self,
        model: str,
        messages: List[Dict],
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
    
    async def _process_with_fallback(
        self,
        messages: List[Dict],
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
        
        raise Exception("All models failed")
    
    def _file_to_base64(self, file_content: bytes) -> str:
        """Convert file content to base64 string"""
        return base64.b64encode(file_content).decode("utf-8")
    
    async def _process_with_tesseract(
        self,
        file_content: bytes,
        file_type: str,
        languages: List[str]
    ) -> str:
        """Process file with Tesseract OCR"""
        if not self.tesseract_available:
            raise ValueError("Tesseract OCR not available")
        
        is_image = file_type.startswith("image/")
        
        # Map language codes to Tesseract format
        lang_map = {
            "rus": "rus",
            "ru": "rus",
            "russian": "rus",
            "eng": "eng",
            "en": "eng",
            "english": "eng"
        }
        tesseract_langs = "+".join([lang_map.get(lang.lower(), "eng") for lang in languages])
        
        if is_image:
            # Process image directly
            image = Image.open(io.BytesIO(file_content))
            text = pytesseract.image_to_string(image, lang=tesseract_langs)
            return text
        else:
            # Process PDF - convert to images first
            if not self.pdf2image_available:
                raise ValueError("pdf2image not available for PDF processing")
            
            images = convert_from_bytes(file_content)
            all_text = []
            
            for img in images:
                text = pytesseract.image_to_string(img, lang=tesseract_langs)
                all_text.append(text)
            
            return "\n\n--- Page Break ---\n\n".join(all_text)
    
    async def _process_with_llm(
        self,
        file_content: bytes,
        file_type: str,
        languages: List[str]
    ) -> str:
        """Process file with Groq LLM"""
        if not self.api_key:
            raise ValueError("Groq API key not configured")
        
        file_b64 = self._file_to_base64(file_content)
        is_image = file_type.startswith("image/")
        
        lang_names = {
            "rus": "Russian",
            "eng": "English",
            "ru": "Russian",
            "en": "English"
        }
        lang_list = ", ".join([lang_names.get(lang.lower(), lang) for lang in languages])
        
        if is_image:
            prompt = f"""You are an expert OCR system. Extract all text from this image.
Languages to recognize: {lang_list}
Return ONLY the extracted text, preserving line breaks and structure.
Do not add any explanations or comments.

Image data (base64): {file_b64[:5000]}..."""
        else:
            prompt = f"""You are an expert OCR system. Extract all text from this PDF document.
Languages to recognize: {lang_list}
Return ONLY the extracted text, preserving line breaks and structure.
Do not add any explanations or comments.

PDF data (base64): {file_b64[:5000]}..."""
        
        messages = [
            {
                "role": "system",
                "content": "You are an expert OCR system that extracts text from documents and images."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        return await self._process_with_fallback(messages)
    
    async def process_file(
        self,
        file_content: bytes,
        file_type: str,
        languages: List[str] = ["rus", "eng"]
    ) -> Dict:
        """
        Process file with OCR using intelligent method selection
        Returns: {
            "text": str,
            "file_type": str,
            "pages": int,
            "metadata": dict,
            "processing_info": dict
        }
        """
        start_time = time.time()
        
        # Log request
        log_ocr_request(
            file_size=len(file_content),
            file_type=file_type,
            languages=languages
        )
        
        ocr_logger.info(f"Starting OCR processing - File size: {len(file_content) / 1024:.1f}KB")
        
        # Step 1: Evaluate and select optimal method
        ocr_logger.info("Evaluating processing requirements...")
        evaluation = await self.agent.evaluate_processing_requirements(
            file_content=file_content,
            file_type=file_type,
            languages=languages
        )
        
        recommended_method = evaluation["recommended_method"]
        estimated_time = evaluation["estimated_time"]
        
        ocr_logger.info(
            f"Method selected: {recommended_method.value} - "
            f"Estimated time: {estimated_time:.2f}s - "
            f"Reasoning: {evaluation['reasoning']}"
        )
        
        # Step 2: Process with selected method
        processing_info = {
            "method": recommended_method.value,
            "estimated_time": estimated_time,
            "reasoning": evaluation["reasoning"],
            "file_stats": evaluation["file_stats"],
            "method_estimates": evaluation["method_estimates"]
        }
        
        try:
            ocr_logger.info(f"Processing with method: {recommended_method.value}")
            
            if recommended_method == ProcessingMethod.TESSERACT:
                ocr_logger.info("Using Tesseract OCR...")
                ocr_text = await self._process_with_tesseract(file_content, file_type, languages)
            elif recommended_method == ProcessingMethod.LLM_GROQ:
                ocr_logger.info("Using Groq LLM...")
                ocr_text = await self._process_with_llm(file_content, file_type, languages)
            else:
                # Hybrid: try Tesseract first, fallback to LLM
                ocr_logger.info("Using Hybrid method...")
                try:
                    ocr_text = await self._process_with_tesseract(file_content, file_type, languages)
                    processing_info["method"] = "tesseract_hybrid"
                    ocr_logger.info("Hybrid: Tesseract succeeded")
                except Exception as hybrid_error:
                    ocr_logger.warning(f"Hybrid: Tesseract failed, falling back to LLM: {str(hybrid_error)}")
                    ocr_text = await self._process_with_llm(file_content, file_type, languages)
                    processing_info["method"] = "llm_hybrid_fallback"
                    ocr_logger.info("Hybrid: LLM fallback succeeded")
            
            actual_time = time.time() - start_time
            processing_info["actual_time"] = actual_time
            processing_info["time_difference"] = actual_time - estimated_time
            
            # Determine pages BEFORE logging
            is_image = file_type.startswith("image/")
            if is_image:
                pages = 1
            else:
                pages = evaluation["file_stats"]["pages"]
            
            ocr_logger.info(
                f"OCR completed - Method: {processing_info['method']}, "
                f"Time: {actual_time:.2f}s, "
                f"Text length: {len(ocr_text)} chars, "
                f"Pages: {pages}"
            )
            
            # Log success
            log_ocr_result(
                method=processing_info["method"],
                success=True,
                time_taken=actual_time,
                pages=pages
            )
            
            return {
                "text": ocr_text,
                "file_type": "image" if is_image else "pdf",
                "pages": pages,
                "metadata": {
                    "languages": languages,
                    "file_type": file_type,
                    "method_used": processing_info["method"]
                },
                "processing_info": processing_info
            }
        
        except Exception as e:
            # Fallback: try alternative method
            ocr_logger.error(f"Primary method failed: {str(e)}")
            ocr_logger.info("Attempting fallback method...")
            
            processing_info["error"] = str(e)
            processing_info["fallback_used"] = True
            
            try:
                if recommended_method == ProcessingMethod.TESSERACT:
                    # Fallback to LLM
                    ocr_logger.info("Fallback: Trying LLM...")
                    ocr_text = await self._process_with_llm(file_content, file_type, languages)
                    processing_info["method"] = "llm_fallback"
                else:
                    # Fallback to Tesseract
                    ocr_logger.info("Fallback: Trying Tesseract...")
                    ocr_text = await self._process_with_tesseract(file_content, file_type, languages)
                    processing_info["method"] = "tesseract_fallback"
                
                actual_time = time.time() - start_time
                processing_info["actual_time"] = actual_time
                
                # Determine pages for fallback
                is_image = file_type.startswith("image/")
                if is_image:
                    pages = 1
                else:
                    pages = evaluation["file_stats"]["pages"]
                
                ocr_logger.info(f"Fallback succeeded - Method: {processing_info['method']}, Time: {actual_time:.2f}s")
                
                # Log fallback success
                log_ocr_result(
                    method=processing_info["method"],
                    success=True,
                    time_taken=actual_time,
                    pages=pages
                )
                
                return {
                    "text": ocr_text,
                    "file_type": "image" if is_image else "pdf",
                    "pages": pages,
                    "metadata": {
                        "languages": languages,
                        "file_type": file_type,
                        "method_used": processing_info["method"]
                    },
                    "processing_info": processing_info
                }
            except Exception as fallback_error:
                ocr_logger.error(f"Fallback also failed: {str(fallback_error)}")
                # Log failure
                log_ocr_result(
                    method=recommended_method.value,
                    success=False,
                    time_taken=time.time() - start_time,
                    error=f"{str(e)} | {str(fallback_error)}"
                )
                raise Exception(f"OCR processing failed with both methods: {str(e)} | {str(fallback_error)}")
    
    async def process_image(
        self,
        image_content: bytes,
        languages: List[str] = ["rus", "eng"]
    ) -> str:
        """Process image with OCR"""
        result = await self.process_file(
            file_content=image_content,
            file_type="image/png",
            languages=languages
        )
        return result["text"]
    
    async def process_pdf(
        self,
        pdf_content: bytes,
        languages: List[str] = ["rus", "eng"]
    ) -> str:
        """Process PDF with OCR"""
        result = await self.process_file(
            file_content=pdf_content,
            file_type="application/pdf",
            languages=languages
        )
        return result["text"]

