"""Comprehensive tests for CRM automation features."""

import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta, timezone

# Set test environment variables before importing services
os.environ.setdefault("GROQ_API_KEY", "test_key")
os.environ.setdefault("AMO_BASE_URL", "https://test.amocrm.ru")
os.environ.setdefault("AMO_ACCESS_TOKEN", "test_token")

from services.pipeline_service import PipelineService
from services.data_extraction_service import DataExtractionService
from services.whatsapp_service import WhatsAppService
from services.sla_monitor_service import SLAMonitorService
from services.call_transcription_service import CallTranscriptionService
from services.document_control_service import DocumentControlService
from services.crm_service import CRMService, InteractionPayload, ContactPayload, DocumentChecklist


class TestPipelineService(unittest.IsolatedAsyncioTestCase):
    """Test pipeline detection service."""

    async def test_keyword_detection_sales(self):
        """Test keyword-based detection for sales pipeline."""
        service = PipelineService()
        service.groq_api_key = ""  # Disable LLM
        
        result = await service.detect_pipeline(
            "Запрос на оборудование",
            "Нужно купить контактор",
        )
        
        self.assertEqual(result["pipeline_type"], "sales")
        self.assertIn("confidence", result)

    async def test_keyword_detection_nku(self):
        """Test keyword-based detection for НКУ pipeline."""
        service = PipelineService()
        service.groq_api_key = ""
        
        result = await service.detect_pipeline(
            "Изготовление на заказ",
            "Нужно изготовить АВР мощностью 630А, IP54",
        )
        
        self.assertEqual(result["pipeline_type"], "nku")
        self.assertIn("confidence", result)

    async def test_keyword_detection_services(self):
        """Test keyword-based detection for services pipeline."""
        service = PipelineService()
        service.groq_api_key = ""
        
        result = await service.detect_pipeline(
            "Выезд специалиста",
            "Нужен выезд на адрес ул. Ленина 1 для монтажа",
        )
        
        self.assertEqual(result["pipeline_type"], "services")
        self.assertIn("confidence", result)


class TestDataExtractionService(unittest.IsolatedAsyncioTestCase):
    """Test data extraction service."""

    async def test_regex_extraction(self):
        """Test regex-based data extraction."""
        service = DataExtractionService()
        service.groq_api_key = ""  # Disable LLM
        
        result = await service.extract_deal_data(
            "Заказ",
            "Нужно 2 шт контакторов по 5000 тенге, доставка до 15.10.2025",
        )
        
        self.assertIn("products", result)
        self.assertIn("confidence", result)


class TestWhatsAppService(unittest.IsolatedAsyncioTestCase):
    """Test WhatsApp service."""

    async def test_placeholder_mode(self):
        """Test WhatsApp service in placeholder mode."""
        service = WhatsAppService()
        service.dialog360_api_key = ""
        service.cloud_api_token = ""
        
        result = await service.send_notification("+77071234567", "Test message")
        
        self.assertEqual(result["status"], "placeholder")
        self.assertIn("provider", result)

    @patch("httpx.AsyncClient")
    async def test_360dialog_send(self, mock_client):
        """Test sending via 360dialog."""
        service = WhatsAppService()
        service.dialog360_api_key = "test_key"
        service.dialog360_base_url = "https://test.example.com"
        
        mock_response = MagicMock()
        mock_response.is_error = False
        mock_response.status_code = 200
        
        mock_client_instance = AsyncMock()
        mock_client_instance.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        
        result = await service.send_notification("+77071234567", "Test")
        
        # Should attempt to send (may fail in test, but should not crash)
        self.assertIn("status", result)


class TestSLAMonitorService(unittest.IsolatedAsyncioTestCase):
    """Test SLA monitoring service."""

    @patch("services.sla_monitor_service.crm_service")
    async def test_check_overdue_tasks_no_tasks(self, mock_crm):
        """Test SLA check with no tasks."""
        service = SLAMonitorService()
        mock_crm._list_tasks = AsyncMock(return_value=[])
        
        result = await service.check_overdue_tasks(lead_id=123)
        
        self.assertEqual(result["checked"], 0)
        self.assertEqual(result["overdue"], 0)

    @patch("services.sla_monitor_service.crm_service")
    @patch("services.sla_monitor_service.whatsapp_service")
    async def test_check_overdue_task(self, mock_whatsapp, mock_crm):
        """Test SLA check with overdue task."""
        service = SLAMonitorService()
        
        # Create overdue task (2 hours ago)
        overdue_time = int((datetime.now(timezone.utc) - timedelta(hours=2)).timestamp())
        mock_crm._list_tasks = AsyncMock(return_value=[
            {
                "id": 1,
                "text": "Test task",
                "complete_till": overdue_time,
                "is_completed": False,
                "entity_id": 123,
                "responsible_user_id": 456,
            }
        ])
        mock_crm._request = AsyncMock(return_value={"name": "Test Lead"})
        mock_crm.add_lead_note = AsyncMock()
        mock_whatsapp.send_to_manager = AsyncMock(return_value={"status": "sent"})
        
        result = await service.check_overdue_tasks(lead_id=123)
        
        self.assertGreaterEqual(result["overdue"], 1)
        mock_whatsapp.send_to_manager.assert_called()


class TestCallTranscriptionService(unittest.IsolatedAsyncioTestCase):
    """Test call transcription service."""

    async def test_simple_extraction(self):
        """Test simple transcription extraction."""
        service = CallTranscriptionService()
        service.groq_api_key = ""
        
        result = await service.process_call(
            transcription_text="Клиент хочет купить 2 контактора по 5000 тенге",
        )
        
        self.assertIn("transcription", result)
        self.assertIn("summary", result)
        self.assertIn("action_items", result)


class TestDocumentControlService(unittest.IsolatedAsyncioTestCase):
    """Test document control service."""

    @patch("services.document_control_service.crm_service")
    @patch("services.document_control_service.whatsapp_service")
    async def test_check_complete_documents(self, mock_whatsapp, mock_crm):
        """Test document check with complete set."""
        service = DocumentControlService()
        
        mock_crm.check_document_files = AsyncMock(return_value={
            "checklist": {
                "proposal": True,
                "invoice": True,
                "contract": True,
                "waybill": True,
                "act": True,
                "invoice_factura": True,
            },
            "complete": True,
        })
        
        result = await service.check_and_remind(lead_id=123)
        
        self.assertEqual(result["status"], "complete")
        mock_whatsapp.send_to_manager.assert_not_called()

    @patch("services.document_control_service.crm_service")
    @patch("services.document_control_service.whatsapp_service")
    async def test_check_missing_documents(self, mock_whatsapp, mock_crm):
        """Test document check with missing documents."""
        service = DocumentControlService()
        
        mock_crm.check_document_files = AsyncMock(return_value={
            "checklist": {
                "proposal": True,
                "invoice": False,
                "contract": False,
                "waybill": True,
                "act": True,
                "invoice_factura": True,
            },
            "complete": False,
        })
        mock_crm._request = AsyncMock(return_value={"name": "Test Lead"})
        mock_crm._list_tasks = AsyncMock(return_value=[])
        mock_crm.add_lead_note = AsyncMock()
        mock_whatsapp.send_to_manager = AsyncMock(return_value={"status": "sent"})
        
        result = await service.check_and_remind(lead_id=123)
        
        self.assertEqual(result["status"], "reminder_sent")
        self.assertIn("missing_documents", result)
        mock_whatsapp.send_to_manager.assert_called()


class TestCRMServiceIntegration(unittest.IsolatedAsyncioTestCase):
    """Test CRM service with new features."""

    @patch("services.pipeline_service.pipeline_service.detect_pipeline")
    @patch("services.data_extraction_service.data_extraction_service.extract_deal_data")
    @patch("services.crm_service.CRMService._request")
    @patch("services.crm_service.CRMService._find_contact")
    @patch("services.crm_service.CRMService._find_open_lead")
    @patch("services.crm_service.CRMService._attach_interaction_note")
    @patch("services.crm_service.CRMService._ensure_follow_up_task")
    async def test_register_interaction_with_pipeline_detection(
        self, mock_follow_up, mock_note, mock_find_lead, mock_find_contact, mock_request, mock_extraction, mock_pipeline
    ):
        """Test interaction registration with pipeline detection."""
        service = CRMService()
        service.base_url = "https://test.amocrm.ru"
        service.client_id = "test_client_id"
        service.client_secret = "test_client_secret"
        service.redirect_uri = "https://test.example.com/callback"
        service.access_token = "test_token"
        service.pipeline_id = 1
        service.lead_status_id = 1
        service.default_responsible_id = 1
        
        mock_pipeline.return_value = {
            "pipeline_type": "sales",
            "pipeline_id": 1,
            "confidence": 0.8,
            "reason": "Test",
        }
        mock_extraction.return_value = {
            "products": [],
            "total_amount": 10000,
            "confidence": 0.7,
        }
        
        # Mock contact and lead lookup
        mock_find_contact.return_value = None  # New contact
        mock_find_lead.return_value = None  # New lead
        
        # Mock contact and lead creation
        def mock_request_side_effect(method, path, **kwargs):
            if "contacts" in path:
                return {"_embedded": {"contacts": [{"id": 123}]}}
            elif "leads" in path and method == "POST":
                return {"_embedded": {"leads": [{"id": 456}]}}
            return {}
        
        mock_request.side_effect = mock_request_side_effect
        mock_note.return_value = None
        mock_follow_up.return_value = None
        
        payload = InteractionPayload(
            channel="email",
            subject="Test",
            message="Test message",
            contact=ContactPayload(name="Test Contact", email="test@example.com"),
        )
        
        # Test that the method completes successfully
        result = await service.register_interaction(payload)
        
        # Verify result structure
        self.assertIn("contact_id", result)
        self.assertIn("lead_id", result)
        self.assertIn("pipeline_type", result)
        self.assertIn("extracted_data", result)
        
        # Verify pipeline and extraction services were called
        mock_pipeline.assert_called_once()
        mock_extraction.assert_called_once()


if __name__ == "__main__":
    unittest.main()

