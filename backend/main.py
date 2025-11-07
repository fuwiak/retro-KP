"""
FastAPI Backend for Retro Drawing Analyzer
Handles OCR, translation, and document export
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import time
from pathlib import Path
from dotenv import load_dotenv

from services.ocr_service import OCRService
from services.translation_service import TranslationService
from services.export_service import ExportService
from services.cloud_service import CloudService
from services.logger import api_logger, log_api_request, log_api_response

# Load environment variables
load_dotenv()

app = FastAPI(
    title="Retro Drawing Analyzer",
    description="PDF drawing analysis with OCR, translation, and export",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
ocr_service = OCRService()
translation_service = TranslationService()
export_service = ExportService()
cloud_service = CloudService()

# Frontend static files configuration
# Check if frontend dist directory exists (for Railway deployment)
FRONTEND_DIR = Path(__file__).parent / "static"
if not FRONTEND_DIR.exists():
    # Try alternative path (if build is in root dist)
    FRONTEND_DIR = Path(__file__).parent.parent / "dist"

# Mount static assets if frontend exists
if FRONTEND_DIR.exists():
    assets_dir = FRONTEND_DIR / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
    api_logger.info(f"Frontend found at {FRONTEND_DIR}")
else:
    api_logger.warning("Frontend not found - serving API only")

@app.get("/api/health")
async def health():
    """Health check with service status"""
    return {
        "status": "ok",
        "services": {
            "ocr": ocr_service.is_available(),
            "translation": translation_service.is_available(),
            "export": export_service.is_available()
        }
    }


# ========== OCR ENDPOINTS ==========

@app.post("/api/ocr/process")
async def process_ocr(
    request: Request,
    file: UploadFile = File(...),
    languages: str = Form("rus+eng")
):
    """
    Process PDF or image file with OCR using intelligent method selection.
    AI agent evaluates file complexity and estimated processing time,
    then selects optimal method (LLM Groq or Tesseract OCR).
    Supports multiple languages (rus+eng, eng, rus, etc.)
    """
    start_time = time.time()
    client_ip = request.client.host if request.client else None
    
    try:
        # Log API request
        log_api_request("POST", "/api/ocr/process", client_ip)
        api_logger.info(f"OCR request received - File: {file.filename}, Languages: {languages}")
        
        # Parse languages
        lang_list = languages.split("+") if "+" in languages else [languages]
        
        # Read file content
        file_content = await file.read()
        file_type = file.content_type
        
        api_logger.info(f"File read - Size: {len(file_content) / 1024:.1f}KB, Type: {file_type}")
        
        # Process with OCR (agent automatically selects best method)
        result = await ocr_service.process_file(
            file_content=file_content,
            file_type=file_type,
            languages=lang_list
        )
        
        # Extract processing info
        processing_info = result.get("processing_info", {})
        
        response_time = time.time() - start_time
        log_api_response("POST", "/api/ocr/process", 200, response_time)
        
        api_logger.info(
            f"OCR request completed - Method: {processing_info.get('method', 'unknown')}, "
            f"Time: {response_time:.2f}s, Text length: {len(result.get('text', ''))} chars"
        )
        
        return {
            "success": True,
            "text": result.get("text", ""),
            "file_type": result.get("file_type", "unknown"),
            "pages": result.get("pages", 1),
            "metadata": result.get("metadata", {}),
            "processing_info": {
                "method_used": processing_info.get("method", "unknown"),
                "estimated_time": processing_info.get("estimated_time", 0),
                "actual_time": processing_info.get("actual_time", 0),
                "reasoning": processing_info.get("reasoning", ""),
                "file_stats": processing_info.get("file_stats", {})
            }
        }
    
    except Exception as e:
        response_time = time.time() - start_time
        log_api_response("POST", "/api/ocr/process", 500, response_time)
        api_logger.error(f"OCR request failed - Error: {str(e)}", exc_info=True)
        
        raise HTTPException(
            status_code=500,
            detail=f"OCR processing failed: {str(e)}"
        )


# ========== TRANSLATION ENDPOINTS ==========

class TranslationRequest(BaseModel):
    text: str
    from_lang: str = "ru"
    to_lang: str = "en"


@app.post("/api/translate")
async def translate_text(request: TranslationRequest):
    """
    Translate text from one language to another
    Uses technical glossary and Groq AI
    """
    try:
        translated = await translation_service.translate(
            text=request.text,
            from_lang=request.from_lang,
            to_lang=request.to_lang
        )
        
        return {
            "success": True,
            "originalText": request.text,
            "translatedText": translated,
            "from": request.from_lang,
            "to": request.to_lang
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Translation failed: {str(e)}"
        )


# ========== EXPORT ENDPOINTS ==========

class ExportData(BaseModel):
    extractedData: dict
    translations: dict
    steelEquivalents: dict = {}


@app.post("/api/export/docx")
async def export_docx(data: ExportData):
    """
    Export data to DOCX format
    """
    try:
        file_path = await export_service.export_to_docx(
            extracted_data=data.extractedData,
            translations=data.translations,
            steel_equivalents=data.steelEquivalents
        )
        
        return FileResponse(
            file_path,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            filename="drawing_analysis.docx"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"DOCX export failed: {str(e)}"
        )


@app.post("/api/export/xlsx")
async def export_xlsx(data: ExportData):
    """
    Export data to XLSX format
    """
    try:
        file_path = await export_service.export_to_xlsx(
            extracted_data=data.extractedData,
            translations=data.translations,
            steel_equivalents=data.steelEquivalents
        )
        
        return FileResponse(
            file_path,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            filename="drawing_analysis.xlsx"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"XLSX export failed: {str(e)}"
        )


# ========== CLOUD FOLDER API ==========
class CloudFolderRequest(BaseModel):
    url: str
    limit: int = 50  # Default: load 50 files at a time
    offset: int = 0  # Pagination offset

class CloudFileRequest(BaseModel):
    url: str
    fileName: str

class CloudFolderFilesRequest(BaseModel):
    folder_url: str
    folder_name: str = ""

@app.post("/api/cloud/folder")
async def get_cloud_folder(request: CloudFolderRequest):
    """Get folder structure from Mail.ru Cloud - LAZY: only structure, no recursive fetching"""
    log_api_request("POST", "/api/cloud/folder", {"url": request.url, "limit": request.limit, "offset": request.offset})
    
    try:
        import asyncio
        import concurrent.futures
        
        # LAZY approach: parse only structure (folders and file names), no recursive fetching
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            folder_data = await asyncio.wait_for(
                loop.run_in_executor(
                    executor, 
                    cloud_service.parse_mailru_folder_structure, 
                    request.url
                ),
                timeout=10.0  # 10 seconds should be enough for structure only
            )
        
        items = folder_data.get('items', [])
        total_items = len(items)
        
        # Apply pagination
        paginated_items = items[request.offset:request.offset + request.limit]
        has_more = (request.offset + request.limit) < total_items
        
        result = {
            'items': paginated_items,
            'folder_url': folder_data.get('folder_url', request.url),
            'pagination': {
                'total': total_items,
                'limit': request.limit,
                'offset': request.offset,
                'has_more': has_more,
                'returned': len(paginated_items)
            }
        }
        
        log_api_response("POST", "/api/cloud/folder", 200, 0.0)
        api_logger.info(f"Folder structure parsed: {len(paginated_items)}/{total_items} items returned (has_more={has_more})")
        return result
    except asyncio.TimeoutError:
        api_logger.error(f"Timeout parsing Mail.ru Cloud folder: {request.url}")
        log_api_response("POST", "/api/cloud/folder", 504, 0.0)
        api_logger.error("Request timeout")
        raise HTTPException(
            status_code=504,
            detail="Request timeout - folder is too large or server is slow. Try reducing the limit parameter."
        )
    except Exception as e:
        api_logger.error(f"Error getting cloud folder: {str(e)}")
        import traceback
        api_logger.error(f"Traceback: {traceback.format_exc()}")
        log_api_response("POST", "/api/cloud/folder", 500, 0.0)
        api_logger.error(f"Error details: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load folder: {str(e)}"
        )

@app.post("/api/cloud/folder/files")
async def get_folder_files(request: CloudFolderFilesRequest):
    """Get files from a specific folder - LAZY: called on demand when user expands folder"""
    log_api_request("POST", "/api/cloud/folder/files", {"folder_url": request.folder_url, "folder_name": request.folder_name})
    
    try:
        import asyncio
        import concurrent.futures
        
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            items = await asyncio.wait_for(
                loop.run_in_executor(
                    executor,
                    cloud_service.fetch_folder_files,
                    request.folder_url,
                    request.folder_name
                ),
                timeout=10.0
            )
        
        log_api_response("POST", "/api/cloud/folder/files", 200, 0.0)
        api_logger.info(f"Folder files fetched: {len(items)} items from {request.folder_name or request.folder_url}")
        return {'items': items, 'folder_url': request.folder_url}
        
    except asyncio.TimeoutError:
        api_logger.error(f"Timeout fetching folder files: {request.folder_url}")
        log_api_response("POST", "/api/cloud/folder/files", 504, 0.0)
        raise HTTPException(status_code=504, detail="Request timeout")
    except Exception as e:
        api_logger.error(f"Error fetching folder files: {str(e)}")
        log_api_response("POST", "/api/cloud/folder/files", 500, 0.0)
        raise HTTPException(status_code=500, detail=f"Failed to fetch folder files: {str(e)}")

@app.post("/api/cloud/file")
async def get_cloud_file(request: CloudFileRequest):
    """Download file from cloud URL"""
    log_api_request("POST", "/api/cloud/file", {"url": request.url, "fileName": request.fileName})
    
    try:
        file_content = cloud_service.download_file(request.url)
        log_api_response("POST", "/api/cloud/file", 200, 0.0)
        api_logger.info(f"File downloaded: {request.fileName} ({len(file_content)} bytes)")
        
        # Handle Unicode filenames properly (RFC 5987)
        import urllib.parse
        # Encode filename for Content-Disposition header
        # Use ASCII fallback and RFC 5987 encoding for Unicode
        safe_filename = request.fileName.encode('ascii', 'ignore').decode('ascii')
        if safe_filename != request.fileName:
            # Contains non-ASCII characters, use RFC 5987 encoding
            encoded_filename = urllib.parse.quote(request.fileName, safe='')
            content_disposition = f"attachment; filename=\"{safe_filename}\"; filename*=UTF-8''{encoded_filename}"
        else:
            content_disposition = f'attachment; filename="{request.fileName}"'
        
        return Response(
            content=file_content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": content_disposition
            }
        )
    except Exception as e:
        api_logger.error(f"Error downloading cloud file: {str(e)}")
        log_api_response("POST", "/api/cloud/file", 500, 0.0)
        api_logger.error(f"Error details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to download file: {str(e)}")

@app.post("/api/export/pdf")
async def export_pdf(
    pdf: UploadFile = File(...),
    data: str = Form(...)
):
    """
    Export PDF with English overlay
    """
    try:
        import json
        data_dict = json.loads(data)
        
        pdf_content = await pdf.read()
        
        file_path = await export_service.export_to_pdf(
            pdf_content=pdf_content,
            extracted_data=data_dict.get("extractedData", {}),
            translations=data_dict.get("translations", {}),
            steel_equivalents=data_dict.get("steelEquivalents", {})
        )
        
        return FileResponse(
            file_path,
            media_type="application/pdf",
            filename="drawing_analysis_with_overlay.pdf"
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"PDF export failed: {str(e)}"
        )


# ========== FRONTEND SERVING (must be last) ==========
# Serve frontend for all non-API routes (SPA routing)
# This must be defined after all API routes
if FRONTEND_DIR.exists():
    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str, request: Request):
        # Don't interfere with API routes and docs
        if (full_path.startswith("api/") or 
            full_path.startswith("docs") or 
            full_path.startswith("openapi.json") or
            full_path.startswith("assets/")):
            raise HTTPException(status_code=404, detail="Not found")
        
        # Serve index.html for all frontend routes
        index_path = FRONTEND_DIR / "index.html"
        if index_path.exists():
            with open(index_path, "r", encoding="utf-8") as f:
                html_content = f.read()
            
            # Auto-detect API URL from request
            # Ensure HTTPS in production (fix Mixed Content error)
            base_url = str(request.base_url).rstrip("/")
            
            # Check if request came via HTTPS (Railway uses proxy with X-Forwarded-Proto)
            is_https = (
                request.url.scheme == 'https' or
                request.headers.get('X-Forwarded-Proto') == 'https' or
                request.headers.get('X-Forwarded-Ssl') == 'on' or
                'railway.app' in str(request.base_url)  # Railway domains should use HTTPS
            )
            
            # Force HTTPS if needed
            if is_https and base_url.startswith('http://'):
                base_url = base_url.replace('http://', 'https://', 1)
            
            api_url = f"{base_url}/api"
            
            # Inject API URL into HTML as window variable
            script_tag = f'<script>window.API_BASE_URL = "{api_url}";</script>'
            # Inject before closing head tag, or at the beginning if no head tag
            if '</head>' in html_content:
                html_content = html_content.replace('</head>', f'{script_tag}</head>')
            elif '<body>' in html_content:
                html_content = html_content.replace('<body>', f'{script_tag}<body>')
            else:
                html_content = script_tag + html_content
            
            return HTMLResponse(content=html_content)
        
        raise HTTPException(status_code=404, detail="Frontend not found")


if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment variable (Railway provides PORT)
    port = int(os.getenv("PORT", 3000))
    host = os.getenv("HOST", "0.0.0.0")
    reload = os.getenv("ENVIRONMENT", "development") == "development"
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload
    )

