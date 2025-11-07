# Retro Drawing Analyzer

[![CI](https://github.com/YOUR_USERNAME/retro-sketch/workflows/CI/badge.svg)](https://github.com/YOUR_USERNAME/retro-sketch/actions)
[![Security Scan](https://github.com/YOUR_USERNAME/retro-sketch/workflows/Security%20Scan/badge.svg)](https://github.com/YOUR_USERNAME/retro-sketch/actions)

Aplikacja do analizy PDF-ów z rysunkami technicznymi z OCR, tłumaczeniem i eksportem.

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

# Skopiuj env.example do .env i uzupełnij GROQ_API_KEY
cp env.example .env

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

- **Inteligentny OCR**: AI agent wybiera optymalną metodę (Groq LLM lub Tesseract)
- **Tłumaczenie**: Automatyczne tłumaczenie tekstu technicznego (RU → EN)
- **Eksport**: Generowanie dokumentów DOCX, XLSX, PDF
- **Selekcja obszarów**: Zaznaczanie prostokątne i wielokątne w PDF
- **Ekwiwalenty stali**: Wyszukiwanie odpowiedników w standardach ASTM, ISO, GB/T

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
│   ├── services/     # Serwisy (OCR, translation, export)
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

