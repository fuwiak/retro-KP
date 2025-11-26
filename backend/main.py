"""
FastAPI backend for CRM & 1C Integration Hub.
Coordinates OCR, translation, CRM automation, and document workflows.
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import io
from datetime import date, datetime
import asyncio
import os
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables FIRST, before importing services
# Try to find .env file in backend directory (works regardless of CWD)
backend_dir = Path(__file__).parent
env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
    print(f"✅ Loaded .env from {env_path}")
else:
    # Fallback: try current directory and parent directory
    load_dotenv()  # Current directory
    load_dotenv(dotenv_path=backend_dir.parent / ".env")  # Parent directory
    print("✅ Loaded .env from default locations (or using system env vars)")

# Now import services (they will use the loaded env vars)
from services.ocr_service import OCRService
from services.translation_service import TranslationService
from services.export_service import ExportService
from services.cloud_service import CloudService
from services.email_service import email_analysis_service
from services.logger import api_logger, log_api_request, log_api_response
from services.onec_service import onec_service
from services.crm_service import (
    crm_service,
    ContactPayload,
    InteractionPayload,
    DocumentChecklist,
    CRMConfigurationError,
)
from services.sla_monitor_service import sla_monitor_service
from services.call_transcription_service import call_transcription_service
from services.document_control_service import document_control_service

app = FastAPI(
    title="CRM & 1C Integration Hub",
    description="Automated inbox triage, CRM workflows, and 1C document exchange",
    version="1.1.0"
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


# ========== EMAIL ANALYSIS ENDPOINTS ==========


class EmailItem(BaseModel):
    id: str
    subject: str
    sender: str
    date: str
    bodyPreview: str
    fullBody: str
    nlpCategory: str


class EmailClassificationRequest(BaseModel):
    subject: str
    sender: str
    body: str


class EmailProposalRequest(BaseModel):
    subject: str
    body: str


@app.get("/api/emails", response_model=List[EmailItem])
async def get_emails(limit: int = 20, relevant_only: bool = True):
    """Fetch recent emails from IMAP inbox or generate mock data."""

    try:
        emails = await email_analysis_service.fetch_emails_async(limit)
    except Exception as exc:
        api_logger.error(f"Failed to fetch emails: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    if relevant_only:
        emails = [email for email in emails if email.get("nlpCategory") == "potential"]

    return emails


@app.post("/api/emails/mock-mode")
async def toggle_mock_mode(enabled: bool):
    """Enable or disable mock data mode."""
    email_analysis_service.set_mock_mode(enabled)
    return {
        "mock_mode": email_analysis_service.is_mock_mode(),
        "message": f"Mock mode {'enabled' if enabled else 'disabled'}",
    }


@app.get("/api/emails/mock-mode")
async def get_mock_mode_status():
    """Get current mock mode status."""
    return {
        "mock_mode": email_analysis_service.is_mock_mode(),
    }


@app.post("/api/emails/classify")
async def classify_email(request: EmailClassificationRequest):
    """Classify email using Groq LLM."""

    try:
        result = await email_analysis_service.classify_email_llm(
            request.subject,
            request.sender,
            request.body,
        )
        return {"classification": result}
    except Exception as exc:
        api_logger.error(f"Email classification failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/api/emails/proposal")
async def generate_email_proposal(request: EmailProposalRequest):
    """Generate commercial proposal text for email."""

    try:
        text = await email_analysis_service.generate_proposal(
            request.subject,
            request.body,
        )
        return {"proposal": text}
    except Exception as exc:
        api_logger.error(f"Proposal generation failed: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


# ========== CRM AUTOMATION ENDPOINTS ==========


class CRMContact(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None


class CRMDocumentChecklistModel(BaseModel):
    proposal_sent: bool = False
    invoice_sent: bool = False
    contract_signed: bool = False
    closing_documents_ready: bool = False


class CRMInteractionRequest(BaseModel):
    channel: str
    subject: str
    message: str
    contact: CRMContact
    source_id: Optional[str] = None
    direction: str = "incoming"
    metadata: Optional[Dict[str, Any]] = None
    documents: Optional[CRMDocumentChecklistModel] = None
    responsible_user_id: Optional[int] = None
    follow_up_hours: int = 4


@app.post("/api/crm/interactions")
async def register_crm_interaction(request: CRMInteractionRequest):
    """Register customer interaction and automate amoCRM routines."""

    try:
        result = await crm_service.register_interaction(
            InteractionPayload(
                channel=request.channel,
                subject=request.subject,
                message=request.message,
                contact=ContactPayload(**request.contact.model_dump()),
                source_id=request.source_id,
                direction=request.direction,
                metadata=request.metadata,
                documents=(
                    DocumentChecklist(**request.documents.model_dump())
                    if request.documents
                    else None
                ),
                responsible_user_id=request.responsible_user_id,
                follow_up_hours=request.follow_up_hours,
            )
        )
        return result
    except CRMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        api_logger.error(f"CRM interaction failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to register interaction")


class CRMDocumentControlRequest(BaseModel):
    documents: CRMDocumentChecklistModel
    responsible_user_id: Optional[int] = None


@app.post("/api/crm/leads/{lead_id}/documents")
async def ensure_lead_documents(lead_id: int, request: CRMDocumentControlRequest):
    """Ensure document delivery tasks exist for the lead."""

    try:
        result = await crm_service.ensure_document_completeness(
            lead_id,
            DocumentChecklist(**request.documents.model_dump()),
            responsible_user_id=request.responsible_user_id,
        )
        return result
    except CRMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        api_logger.error(f"CRM document control failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to ensure document tasks")


class CRMProposalSentRequest(BaseModel):
    proposal_amount: Optional[float] = None
    proposal_text: Optional[str] = None
    responsible_user_id: Optional[int] = None


@app.post("/api/crm/leads/{lead_id}/proposal-sent")
async def handle_proposal_sent(lead_id: int, request: CRMProposalSentRequest):
    """Handle commercial proposal sent: move to stage, set amount, create follow-up task."""

    try:
        result = await crm_service.handle_proposal_sent(
            lead_id,
            proposal_amount=request.proposal_amount,
            proposal_text=request.proposal_text,
            responsible_user_id=request.responsible_user_id,
        )
        return result
    except CRMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        api_logger.error(f"CP control failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to handle proposal sent")


@app.get("/api/crm/leads/{lead_id}/documents/check")
async def check_lead_documents(lead_id: int):
    """Check which document files are attached to the lead."""

    try:
        result = await crm_service.check_document_files(lead_id)
        return result
    except CRMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        api_logger.error(f"Document check failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to check documents")


@app.post("/api/crm/sla/check")
async def check_sla(lead_id: Optional[int] = None):
    """Check for overdue tasks and send notifications."""

    try:
        result = await sla_monitor_service.check_overdue_tasks(lead_id)
        return result
    except Exception as exc:
        api_logger.error(f"SLA check failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to check SLA")


class CallProcessingRequest(BaseModel):
    recording_url: Optional[str] = None
    transcription_text: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@app.post("/api/crm/calls/process")
async def process_call(request: CallProcessingRequest):
    """Process call recording and generate summary."""

    try:
        result = await call_transcription_service.process_call(
            recording_url=request.recording_url,
            transcription_text=request.transcription_text,
            metadata=request.metadata,
        )
        return result
    except Exception as exc:
        api_logger.error(f"Call processing failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process call")


@app.post("/api/crm/leads/{lead_id}/documents/remind")
async def remind_about_documents(lead_id: int):
    """Check document completeness and send reminder if needed."""

    try:
        result = await document_control_service.check_and_remind(lead_id)
        return result
    except Exception as exc:
        api_logger.error(f"Document reminder failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to send reminder")


class OneCInvoiceItem(BaseModel):
    sku: Optional[str] = None
    description: str
    quantity: float = Field(gt=0)
    unit: Optional[str] = None
    price: float = Field(gt=0)
    vat_rate: Optional[float] = None


class OneCInvoiceRequest(BaseModel):
    lead_id: int
    crm_contact_id: Optional[int] = None
    customer_name: str
    customer_bin: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    due_date: Optional[date] = None
    currency: str = "KZT"
    items: List[OneCInvoiceItem]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OneCFulfillmentRequest(BaseModel):
    lead_id: int
    crm_contact_id: Optional[int] = None
    customer_name: str
    customer_bin: Optional[str] = None
    delivery_address: Optional[str] = None
    documents: Dict[str, Any] = Field(default_factory=dict)
    items: List[OneCInvoiceItem]


class OneCPaymentNotification(BaseModel):
    lead_id: int
    invoice_number: str
    amount: Optional[float] = None
    currency: Optional[str] = None
    paid_at: Optional[datetime] = None
    payer_name: Optional[str] = None
    comment: Optional[str] = None


class OneCRealizationRequest(BaseModel):
    invoice_uuid: str
    lead_id: int


# ========== 1C INTEGRATION ENDPOINTS ==========


def _cleanup_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


@app.post("/api/integrations/1c/invoices")
async def create_invoice_via_onec(request: OneCInvoiceRequest):
    try:
        payload = {
            "leadId": request.lead_id,
            "crmContactId": request.crm_contact_id,
            "customer": _cleanup_payload(
                {
                    "name": request.customer_name,
                    "bin": request.customer_bin,
                    "email": request.customer_email,
                    "phone": request.customer_phone,
                }
            ),
            "currency": request.currency,
            "dueDate": request.due_date.isoformat() if request.due_date else None,
            "items": [item.model_dump(exclude_none=True) for item in request.items],
            "metadata": request.metadata,
        }

        result = await onec_service.create_invoice(_cleanup_payload(payload))
        invoice_number = result.get("invoiceNumber") or result.get("number")
        if invoice_number:
            await crm_service.record_generated_document(
                lead_id=request.lead_id,
                document_type="Счёт",
                document_number=str(invoice_number),
                extra={"Источник": "1C", "Валюта": request.currency},
            )
        pdf_ref = onec_service.extract_ref_from_pdf_url(result.get("pdfUrl", ""))
        return {"invoice": result, "pdfRef": pdf_ref}
    except Exception as exc:
        api_logger.error(f"1C invoice generation failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Invoice creation failed: {exc}")


@app.post("/api/integrations/1c/fulfillment")
async def create_fulfillment_via_onec(request: OneCFulfillmentRequest):
    try:
        payload = {
            "leadId": request.lead_id,
            "crmContactId": request.crm_contact_id,
            "customer": _cleanup_payload(
                {
                    "name": request.customer_name,
                    "bin": request.customer_bin,
                }
            ),
            "deliveryAddress": request.delivery_address,
            "documents": request.documents,
            "items": [item.model_dump(exclude_none=True) for item in request.items],
        }

        result = await onec_service.create_fulfillment_documents(_cleanup_payload(payload))

        waybill_number = result.get("waybillNumber")
        act_number = result.get("actNumber")

        if waybill_number:
            await crm_service.record_generated_document(
                lead_id=request.lead_id,
                document_type="Накладная",
                document_number=str(waybill_number),
            )
        if act_number:
            await crm_service.record_generated_document(
                lead_id=request.lead_id,
                document_type="Акт",
                document_number=str(act_number),
            )

        return {"documents": result}
    except Exception as exc:
        api_logger.error(f"1C fulfillment generation failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Fulfillment creation failed: {exc}")


@app.post("/api/integrations/1c/payment-notification")
async def onec_payment_notification(notification: OneCPaymentNotification):
    try:
        await crm_service.record_payment_notification(
            lead_id=notification.lead_id,
            invoice_number=notification.invoice_number,
            amount=notification.amount,
            currency=notification.currency,
            payer=notification.payer_name,
        )

        details = {
            "invoice": notification.invoice_number,
            "amount": notification.amount,
            "currency": notification.currency,
            "paid_at": notification.paid_at.isoformat() if notification.paid_at else None,
        }
        return {"status": "ok", "details": _cleanup_payload(details)}
    except Exception as exc:
        api_logger.error(f"Processing payment notification failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process payment notification")


@app.post("/api/integrations/1c/realizations")
async def create_realization(request: OneCRealizationRequest):
    try:
        result = await onec_service.create_realization(request.invoice_uuid)
        doc_number = result.get("docNumber") or result.get("waybillNumber")
        if doc_number:
            await crm_service.record_generated_document(
                lead_id=request.lead_id,
                document_type="Реализация",
                document_number=str(doc_number),
            )
        pdf_ref = onec_service.extract_ref_from_pdf_url(result.get("pdfUrl", ""))
        return {"realization": result, "pdfRef": pdf_ref}
    except Exception as exc:
        api_logger.error(f"1C realization creation failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Realization creation failed: {exc}")


@app.get("/api/integrations/1c/invoices/{ref}/pdf")
async def download_invoice_pdf(ref: str):
    try:
        pdf_bytes = await onec_service.fetch_invoice_pdf(ref)
        if not pdf_bytes:
            raise HTTPException(status_code=404, detail="Invoice PDF not found")
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=invoice_{ref}.pdf"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        api_logger.error(f"Downloading invoice PDF failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to download invoice PDF")


@app.get("/api/integrations/1c/realizations/{ref}/pdf")
async def download_realization_pdf(ref: str):
    try:
        pdf_bytes = await onec_service.fetch_realization_pdf(ref)
        if not pdf_bytes:
            raise HTTPException(status_code=404, detail="Realization PDF not found")
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=realization_{ref}.pdf"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        api_logger.error(f"Downloading realization PDF failed: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to download realization PDF")


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

