# Retro Drawing Analyzer - Backend API

FastAPI backend for PDF drawing analysis with OCR, translation, and document export.

## Features

- **Intelligent OCR Processing**: AI agent evaluates file complexity and estimated processing time, then automatically selects optimal method:
  - **Groq LLM**: High-quality OCR for complex documents, multiple languages, technical drawings
  - **Tesseract OCR**: Fast processing for large files, many pages, simple documents
  - Automatic fallback if primary method fails
- **Translation**: Translate technical text (Russian to English) with glossary support
- **Document Export**: Generate DOCX, XLSX, and PDF files with analysis results

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

### 4. Run the Server

```bash
python main.py
```

Or using uvicorn directly:

```bash
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
  - Form data: `file` (PDF/image), `languages` (e.g., "rus+eng")

### Translation
- `POST /api/translate` - Translate text
  - JSON body: `{"text": "...", "from_lang": "ru", "to_lang": "en"}`

### Export
- `POST /api/export/docx` - Export to DOCX
- `POST /api/export/xlsx` - Export to XLSX
- `POST /api/export/pdf` - Export PDF with overlay

## Development

### Project Structure

```
backend/
├── main.py                 # FastAPI application
├── services/
│   ├── ocr_service.py     # OCR processing with Groq AI
│   ├── translation_service.py  # Translation with glossary
│   └── export_service.py   # Document export (DOCX, XLSX, PDF)
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

