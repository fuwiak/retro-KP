"""
AI Agent for OCR Method Selection
Evaluates processing time and selects optimal method (LLM vs Classical OCR)
"""

import os
import time
from typing import Dict, List, Optional, Tuple
from enum import Enum

try:
    import pytesseract
    from PIL import Image
    import pdf2image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

import httpx

# Groq API configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_API_BASE = "https://api.groq.com/openai/v1"

# Model for decision making
DECISION_MODEL = "llama-3.1-8b-instant"  # Fast model for quick decisions

# Thresholds (in seconds)
TIME_THRESHOLD_FAST = 5.0  # If estimated < 5s, use LLM
TIME_THRESHOLD_SLOW = 30.0  # If estimated > 30s, use Tesseract
COMPLEXITY_THRESHOLD = 0.7  # Complexity score threshold


class ProcessingMethod(Enum):
    """OCR Processing methods"""
    LLM_GROQ = "llm_groq"  # Groq AI for complex/high-quality
    TESSERACT = "tesseract"  # Classical OCR for speed
    HYBRID = "hybrid"  # Combination of both


class OCREvaluationAgent:
    """
    AI Agent that evaluates PDF processing requirements
    and selects optimal OCR method
    """
    
    def __init__(self):
        self.api_key = GROQ_API_KEY
        self.api_base = GROQ_API_BASE
        self.tesseract_available = TESSERACT_AVAILABLE
    
    def _estimate_file_size_factor(self, file_size: int) -> float:
        """Estimate processing factor based on file size"""
        # Normalize to MB
        size_mb = file_size / (1024 * 1024)
        
        if size_mb < 1:
            return 1.0  # Small files
        elif size_mb < 5:
            return 1.5  # Medium files
        elif size_mb < 10:
            return 2.5  # Large files
        else:
            return 4.0  # Very large files
    
    def _estimate_page_count(self, file_content: bytes, file_type: str) -> int:
        """Estimate number of pages"""
        if file_type.startswith("image/"):
            return 1
        
        # For PDFs, try to extract page count
        try:
            import PyPDF2
            from io import BytesIO
            pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
            return len(pdf_reader.pages)
        except:
            # Estimate based on file size (rough approximation)
            size_mb = len(file_content) / (1024 * 1024)
            return max(1, int(size_mb * 2))  # Rough estimate: 2 pages per MB
    
    async def _estimate_complexity(self, file_content: bytes, file_type: str) -> Tuple[float, str]:
        """
        Estimate document complexity using AI
        Returns: (complexity_score, reasoning)
        """
        if not self.api_key:
            # Default complexity if no API key
            return 0.5, "No API key - using default complexity"
        
        # Quick analysis of file characteristics
        size_mb = len(file_content) / (1024 * 1024)
        pages = self._estimate_page_count(file_content, file_type)
        
        # Simple heuristic-based complexity
        complexity = 0.5  # Base complexity
        
        # Adjust based on file size
        if size_mb > 10:
            complexity += 0.2  # Large files are more complex
        elif size_mb < 1:
            complexity -= 0.1  # Small files are simpler
        
        # Adjust based on page count
        if pages > 20:
            complexity += 0.2
        elif pages > 10:
            complexity += 0.1
        
        # Use AI for more sophisticated analysis if needed
        try:
            # Quick AI evaluation (only if file is not too large)
            if size_mb < 5:
                complexity, reasoning = await self._ai_complexity_analysis(file_content, file_type)
                return complexity, reasoning
        except:
            pass
        
        return complexity, f"Heuristic: size={size_mb:.1f}MB, pages={pages}"
    
    async def _ai_complexity_analysis(
        self,
        file_content: bytes,
        file_type: str
    ) -> Tuple[float, str]:
        """Use AI to analyze document complexity"""
        try:
            import base64
            file_b64 = base64.b64encode(file_content[:50000]).decode("utf-8")  # First 50KB
            
            prompt = f"""Analyze this document sample and estimate processing complexity (0.0-1.0):
- 0.0-0.3: Simple text documents, clear fonts, few pages
- 0.3-0.6: Standard documents, some formatting, moderate pages
- 0.7-1.0: Complex documents, mixed languages, dense text, technical drawings

Document type: {file_type}
Sample (base64): {file_b64[:1000]}...

Return ONLY a JSON object: {{"complexity": 0.5, "reasoning": "brief explanation"}}"""
            
            messages = [
                {
                    "role": "system",
                    "content": "You are a document analysis expert. Analyze document complexity for OCR processing."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.api_base}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": DECISION_MODEL,
                        "messages": messages,
                        "temperature": 0.1,
                        "max_tokens": 200,
                    }
                )
                
                if response.is_success:
                    data = response.json()
                    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    
                    # Try to parse JSON from response
                    import json
                    import re
                    json_match = re.search(r'\{[^}]+\}', content)
                    if json_match:
                        result = json.loads(json_match.group())
                        return result.get("complexity", 0.5), result.get("reasoning", "AI analysis")
        
        except Exception as e:
            pass
        
        return 0.5, "AI analysis unavailable"
    
    async def evaluate_processing_requirements(
        self,
        file_content: bytes,
        file_type: str,
        languages: List[str]
    ) -> Dict:
        """
        Evaluate PDF processing requirements and estimate time
        Returns: {
            "estimated_time": float,
            "complexity": float,
            "recommended_method": ProcessingMethod,
            "reasoning": str,
            "file_stats": dict
        }
        """
        file_size = len(file_content)
        pages = self._estimate_page_count(file_content, file_type)
        complexity, complexity_reasoning = await self._estimate_complexity(file_content, file_type)
        
        # Estimate processing time for each method
        llm_time = self._estimate_llm_time(file_size, pages, complexity)
        tesseract_time = self._estimate_tesseract_time(file_size, pages)
        
        # Determine recommended method
        recommended_method, reasoning = self._select_method(
            llm_time=llm_time,
            tesseract_time=tesseract_time,
            complexity=complexity,
            file_size=file_size,
            pages=pages,
            languages=languages
        )
        
        # Use the time of recommended method
        estimated_time = llm_time if recommended_method == ProcessingMethod.LLM_GROQ else tesseract_time
        
        return {
            "estimated_time": estimated_time,
            "complexity": complexity,
            "recommended_method": recommended_method,
            "reasoning": reasoning,
            "file_stats": {
                "size_mb": file_size / (1024 * 1024),
                "pages": pages,
                "complexity_reasoning": complexity_reasoning
            },
            "method_estimates": {
                "llm_groq": llm_time,
                "tesseract": tesseract_time
            }
        }
    
    def _estimate_llm_time(self, file_size: int, pages: int, complexity: float) -> float:
        """Estimate processing time for LLM method"""
        size_mb = file_size / (1024 * 1024)
        
        # Base time per page for LLM
        base_time_per_page = 2.0  # seconds
        complexity_factor = 1.0 + (complexity * 0.5)  # 1.0-1.5x
        size_factor = 1.0 + (size_mb * 0.1)  # Larger files take longer
        
        estimated = (base_time_per_page * pages * complexity_factor * size_factor)
        return min(estimated, 120.0)  # Cap at 2 minutes
    
    def _estimate_tesseract_time(self, file_size: int, pages: int) -> float:
        """Estimate processing time for Tesseract method"""
        size_mb = file_size / (1024 * 1024)
        
        # Base time per page for Tesseract (faster but less accurate)
        base_time_per_page = 0.5  # seconds
        size_factor = 1.0 + (size_mb * 0.05)
        
        estimated = base_time_per_page * pages * size_factor
        return min(estimated, 60.0)  # Cap at 1 minute
    
    def _select_method(
        self,
        llm_time: float,
        tesseract_time: float,
        complexity: float,
        file_size: int,
        pages: int,
        languages: List[str]
    ) -> Tuple[ProcessingMethod, str]:
        """Select optimal OCR method based on evaluation"""
        
        # Check if Tesseract is available
        if not self.tesseract_available:
            return ProcessingMethod.LLM_GROQ, "Tesseract not available, using LLM"
        
        # Rule 1: Very large files -> Tesseract (faster)
        if file_size > 10 * 1024 * 1024:  # > 10MB
            return ProcessingMethod.TESSERACT, "Large file (>10MB) - Tesseract is faster"
        
        # Rule 2: Many pages -> Tesseract (faster batch processing)
        if pages > 20:
            return ProcessingMethod.TESSERACT, f"Many pages ({pages}) - Tesseract is faster"
        
        # Rule 3: High complexity -> LLM (better quality)
        if complexity > COMPLEXITY_THRESHOLD:
            return ProcessingMethod.LLM_GROQ, f"High complexity ({complexity:.2f}) - LLM provides better quality"
        
        # Rule 4: Time-based decision
        if tesseract_time < TIME_THRESHOLD_FAST and llm_time > TIME_THRESHOLD_SLOW:
            return ProcessingMethod.TESSERACT, f"Tesseract much faster ({tesseract_time:.1f}s vs {llm_time:.1f}s)"
        
        if llm_time < TIME_THRESHOLD_FAST:
            return ProcessingMethod.LLM_GROQ, f"Both methods fast, LLM preferred for quality ({llm_time:.1f}s)"
        
        # Rule 5: Multiple languages -> LLM (better multilingual support)
        if len(languages) > 2:
            return ProcessingMethod.LLM_GROQ, f"Multiple languages ({len(languages)}) - LLM handles better"
        
        # Rule 6: Default to faster method
        if tesseract_time < llm_time * 0.7:  # Tesseract is significantly faster
            return ProcessingMethod.TESSERACT, f"Tesseract faster ({tesseract_time:.1f}s vs {llm_time:.1f}s)"
        else:
            return ProcessingMethod.LLM_GROQ, f"LLM preferred for quality ({llm_time:.1f}s vs {tesseract_time:.1f}s)"
    
    def get_method_info(self, method: ProcessingMethod) -> Dict:
        """Get information about processing method"""
        info = {
            ProcessingMethod.LLM_GROQ: {
                "name": "Groq AI (LLM)",
                "speed": "Medium",
                "accuracy": "High",
                "best_for": "Complex documents, multiple languages, high quality"
            },
            ProcessingMethod.TESSERACT: {
                "name": "Tesseract OCR",
                "speed": "Fast",
                "accuracy": "Medium",
                "best_for": "Large files, many pages, simple documents"
            },
            ProcessingMethod.HYBRID: {
                "name": "Hybrid (LLM + Tesseract)",
                "speed": "Medium",
                "accuracy": "High",
                "best_for": "Balanced approach"
            }
        }
        return info.get(method, {})

