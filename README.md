# CRM & 1C Integration Hub

[![CI](https://github.com/YOUR_USERNAME/retro-sketch/workflows/CI/badge.svg)](https://github.com/YOUR_USERNAME/retro-sketch/actions)
[![Security Scan](https://github.com/YOUR_USERNAME/retro-sketch/workflows/Security%20Scan/badge.svg)](https://github.com/YOUR_USERNAME/retro-sketch/actions)

Платформа автоматизации CRM-процессов с интеграциями почты, amoCRM и 1С. Бот обрабатывает входящие обращения, генерирует КП, синхронизирует документы (счёт, накладная, акт) и уведомляет менеджера об оплатах.

📌 **Этап 1 — CRM-координация и документооборот с 1С**: система агрегирует email/WhatsApp/телефон, ведёт сделки в amoCRM, генерирует КП и связывает CRM с 1С для счетов, накладных и актов.

## 🚀 Szybki Start

### Lokalne uruchomienie

#### Frontend
```bash
npm install
npm run dev
```

#### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download ru_core_news_sm

# Skopiuj env.example do .env i uzupełnij GROQ_API_KEY
cp env.example .env
# Dodaj konfigurację IMAP oraz amoCRM (Etap 1)

# Для интеграции с 1С укажите ONEC_* параметры

python main.py
```

### Docker Compose

```bash
# Ustaw zmienne środowiskowe
cd backend
cp env.example .env
# Edytuj .env i dodaj GROQ_API_KEY

# Uruchom
cd ..
docker-compose up --build
```

## 📋 Funkcje

- **Inbox AI**: Groq LLM фильтрует входящие письма, формирует КП в один клик
- **Интеграция amoCRM**: Создание контактов/сделок, напоминания, чек-листы документов
- **Документооборот 1С**: REST API для запроса счетов, накладных и актов + webhook оплаты от 1С
- **OCR + Перевод**: LLM/Tesseract для технических PDF, авто-перевод RU→EN
- **Экспорт отчётов**: DOCX, XLSX и PDF с оверлеями

## 🐳 Docker

### Build image
```bash
cd backend
docker build -t retro-sketch-backend .
```

### Run container
```bash
docker run -p 3000:3000 \
  -e GROQ_API_KEY=your_key \
  -e PORT=3000 \
  retro-sketch-backend
```

## 🚂 Railway Deployment

Zobacz [DEPLOY.md](./DEPLOY.md) dla szczegółowych instrukcji.

### Quick Deploy

1. Push do GitHub/GitLab
2. Railway → New Project → Deploy from GitHub
3. Ustaw zmienne środowiskowe:
   - `GROQ_API_KEY`
   - `HOST=0.0.0.0`
   - `ENVIRONMENT=production`

## 📁 Struktura projektu

```
retro-sketch/
├── backend/          # FastAPI backend
│   ├── services/     # OCR, перевод, CRM, 1С, email-интеграции
│   ├── logs/         # Logi aplikacji
│   └── Dockerfile    # Docker image
├── src/              # Frontend (Vite + Vanilla JS)
├── docker-compose.yml
└── railway.toml      # Railway config
```

## 🔧 Konfiguracja

### Backend (.env)
```
GROQ_API_KEY=your_groq_api_key
HOST=0.0.0.0
PORT=3000
ENVIRONMENT=development

# IMAP (analiza poczty)
IMAP_SERVER=imap.example.com
IMAP_PORT=993
IMAP_USERNAME=support@example.com
IMAP_PASSWORD=super_secret
IMAP_FOLDER=INBOX

# amoCRM (Etap 1 CRM)
AMO_BASE_URL=https://yourcompany.amocrm.ru
AMO_CLIENT_ID=...
AMO_CLIENT_SECRET=...
AMO_REDIRECT_URI=https://yourapp.example.com/oauth/callback
AMO_ACCESS_TOKEN=...
AMO_REFRESH_TOKEN=...
AMO_PIPELINE_ID=...
AMO_LEAD_STATUS_ID=...
AMO_RESPONSIBLE_USER_ID=...
AMO_TOKEN_FILE=amo_tokens.json

# 1C API
ONEC_BASE_URL=https://onec.example.com/api
ONEC_API_KEY=...
ONEC_TIMEOUT_SECONDS=15
ONEC_INVOICE_ENDPOINT=/documents/invoice
ONEC_FULFILLMENT_ENDPOINT=/documents/fulfillment
```

### Frontend
Ustaw `VITE_API_BASE_URL` w `.env` (lub użyj domyślnego `http://localhost:3000/api`)

## 📝 Logi

Logi zapisywane w `backend/logs/`:
- `ocr.log` - Operacje OCR
- `api.log` - Żądania API
- `translation.log` - Tłumaczenia
- `export.log` - Eksporty
- `general.log` - Ogólne błędy

## 🛠️ Wymagania

- Python 3.11+
- Node.js 18+
- Tesseract OCR (dla klasycznego OCR)
- Groq API key (dla LLM OCR)
- Dostęp do skrzynки IMAP, poświadczenia amoCRM oraz REST API 1С

## 📚 Dokumentacja API

Po uruchomieniu backendu:
- Swagger UI: http://localhost:3000/docs
- Health check: http://localhost:3000/api/health

## 🔄 CI/CD

Projekt używa GitHub Actions dla:
- ✅ **CI**: Automatyczne testy i build przy każdym push/PR
- 🐳 **Docker**: Build i push obrazów do GitHub Container Registry
- 🚂 **Deploy**: Automatyczny deploy na Railway (opcjonalnie)
- 🔒 **Security**: Skanowanie podatności w zależnościach
- 🤖 **Dependabot**: Automatyczne aktualizacje zależności

Zobacz [.github/workflows/README.md](.github/workflows/README.md) dla szczegółów.

