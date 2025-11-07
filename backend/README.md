# CRM & 1C Integration Hub — Backend API

FastAPI backend for CRM inbox automation, amoCRM workflows, 1С документооборота и технического OCR.

## Features

- **Inbox AI**: Groq основанный анализ писем, фильтр спама, генерация коммерческих предложений
- **CRM Automation**: Создание контактов/сделок в amoCRM, постановка задач и чек-листы документов
- **1С Bridge**: REST API для создания счёта, накладной и акта, а также webhook оплат из 1С
- **Intelligent OCR**: Автовыбор LLM/Tesseract для технической документации
- **Translation & Export**: Перевод текстов и экспорт в DOCX, XLSX, PDF

## Setup

### 1. Install System Dependencies (for Tesseract OCR)

**macOS:**
```bash
brew install tesseract tesseract-lang
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng
```

**Windows:**
Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

### 2. Install Python Dependencies

```bash
cd backend
pip install -r requirements.txt

# Install Russian spaCy model for email analysis
python -m spacy download ru_core_news_sm
```

### 3. Configure Environment

Copy `env.example` to `.env` and fill in your API key:

```bash
cp env.example .env
```

Edit `.env` and add your Groq API key:

```
GROQ_API_KEY=your_groq_api_key_here
```

Get your Groq API key from: https://console.groq.com/

**Note**: Groq API key is optional if you only want to use Tesseract OCR.

### 4. Configure IMAP Inbox (Email Analysis)

The email analysis feature reads messages from your IMAP inbox. Update `.env` with your mailbox settings:

```
IMAP_SERVER=imap.example.com
IMAP_PORT=993
IMAP_USERNAME=support@example.com
IMAP_PASSWORD=your_password
IMAP_FOLDER=INBOX
```

### 5. Configure amoCRM & 1C integration

```
AMO_BASE_URL=https://yourcompany.amocrm.ru
AMO_CLIENT_ID=...
AMO_CLIENT_SECRET=...
AMO_REDIRECT_URI=https://yourapp.example.com/oauth/callback
AMO_ACCESS_TOKEN=...
AMO_REFRESH_TOKEN=...
AMO_PIPELINE_ID=...
AMO_LEAD_STATUS_ID=...
AMO_RESPONSIBLE_USER_ID=...
ONEC_BASE_URL=https://onec.example.com/api
ONEC_API_KEY=...
ONEC_TIMEOUT_SECONDS=15
ONEC_INVOICE_ENDPOINT=/documents/invoice
ONEC_FULFILLMENT_ENDPOINT=/documents/fulfillment
```

### 6. Run the Server

```bash
python main.py
```

Or using uvicorn directly:

```

uvicorn main:app --host 0.0.0.0 --port 3000 --reload
```

The API will be available at: `http://localhost:3000`

API documentation (Swagger UI): `http://localhost:3000/docs`

## API Endpoints

### Health Check
- `GET /` - Root endpoint
- `GET /api/health` - Health check with service status

### OCR
- `POST /api/ocr/process` - Process PDF/image with OCR
  - Form data: `file` (PDF/image), `languages` (например, "rus+eng")

### Translation
- `POST /api/translate` - Translate text
- `POST /api/export/docx|xlsx|pdf` - Export data with overlays

### Email Intelligence
- `GET /api/emails` - List recent IMAP messages
- `POST /api/emails/classify` - Groq-based classification of a letter
- `POST /api/emails/proposal` - Generate plain-text commercial proposal

### CRM Automation
- `POST /api/crm/interactions` - Register inbound interaction and automate amoCRM routines
- `POST /api/crm/leads/{lead_id}/documents` - Manage document checklist tasks

### 1C Integration
- `POST /api/integrations/1c/invoices` - Создание счёта в 1С и возврат PDF + номера
- `POST /api/integrations/1c/fulfillment` - Создание накладной и акта (PDF + номера)
- `POST /api/integrations/1c/payment-notification` - Webhook от 1С с подтверждением оплаты

## Development

### Project Structure

```
backend/
├── main.py                 # FastAPI application
├── services/
│   ├── ocr_service.py          # OCR processing with Groq AI
│   ├── translation_service.py  # Translation with glossary
│   ├── export_service.py       # Document export (DOCX, XLSX, PDF)
│   ├── email_service.py        # IMAP inbox intelligence + KP generation
│   └── crm_service.py          # amoCRM Stage 1 automation core
├── requirements.txt        # Python dependencies
├── .env.example          # Environment variables template
└── README.md             # This file
```

## Notes

### OCR Method Selection

The AI agent automatically selects the best OCR method based on:

1. **File size**: Large files (>10MB) → Tesseract (faster)
2. **Page count**: Many pages (>20) → Tesseract (faster batch processing)
3. **Complexity**: High complexity documents → LLM (better quality)
4. **Processing time**: Estimated time comparison between methods
5. **Languages**: Multiple languages → LLM (better multilingual support)

### Processing Methods

- **Groq LLM**: Best for complex documents, technical drawings, multiple languages. Higher quality but slower.
- **Tesseract OCR**: Best for large files, many pages, simple documents. Faster but lower accuracy.
- **Automatic Fallback**: If primary method fails, automatically tries alternative method.

### Other Notes

- All exports are saved to temporary files and served as downloads
- CORS is enabled for all origins (configure in production)
- Tesseract OCR requires system installation (see Setup section)

## Troubleshooting

1. **Import errors**: Make sure all dependencies are installed: `pip install -r requirements.txt`
2. **Groq API errors**: Check that `GROQ_API_KEY` is set correctly in `.env`
3. **Port already in use**: Change the port in `main.py` or use a different port with uvicorn

