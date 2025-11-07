# Deployment Guide - Railway

## Prerequisites

1. Railway account: https://railway.app
2. Docker installed locally (for testing)
3. Git repository initialized

## Quick Deploy to Railway

### 1. Initialize Git Repository

```bash
# In project root
git init
git add .
git commit -m "Initial commit - Ready for Railway deployment"
```

### 2. Push to GitHub/GitLab

```bash
# Create repository on GitHub/GitLab, then:
git remote add origin <your-repo-url>
git branch -M main
git push -u origin main
```

### 3. Deploy on Railway

1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo" (choose your repository)
4. Railway will automatically detect the Dockerfile
5. Add environment variables:
   - `GROQ_API_KEY` - Your Groq API key
   - `PORT` - Railway will set this automatically (default: 3000)
   - `HOST` - Set to `0.0.0.0`
   - `ENVIRONMENT` - Set to `production`

### 4. Configure Environment Variables

In Railway dashboard:
- Go to your service → Variables
- Add:
  ```
  GROQ_API_KEY=your_groq_api_key_here
  HOST=0.0.0.0
  ENVIRONMENT=production
  ```

## Local Testing with Docker

### Using Docker Compose

```bash
# Create .env file in backend/
cd backend
cp env.example .env
# Edit .env and add GROQ_API_KEY

# Go back to root
cd ..

# Run with docker-compose
docker-compose up --build
```

### Using Docker directly

```bash
cd backend

# Build image
docker build -t retro-sketch-backend .

# Run container
docker run -p 3000:3000 \
  -e GROQ_API_KEY=your_key_here \
  -e HOST=0.0.0.0 \
  -e PORT=3000 \
  -e ENVIRONMENT=production \
  retro-sketch-backend
```

## Railway Configuration

Railway will automatically:
- Build Docker image from `backend/Dockerfile`
- Expose port 3000
- Run health checks on `/api/health`
- Restart on failure

### Custom Domain (Optional)

1. Go to Railway dashboard → Settings
2. Click "Generate Domain" or add custom domain
3. Update frontend `VITE_API_BASE_URL` to use Railway URL

## Monitoring

### Logs

View logs in Railway dashboard:
- Go to your service → Deployments → Click on deployment → Logs

Or locally:
```bash
# Railway CLI
railway logs

# Or view files
tail -f backend/logs/ocr.log
tail -f backend/logs/api.log
```

### Health Check

Railway automatically checks:
- Endpoint: `/api/health`
- Interval: Every 30 seconds
- Timeout: 10 seconds

## Troubleshooting

### Build fails

1. Check Dockerfile syntax
2. Verify all dependencies in `requirements.txt`
3. Check Railway build logs

### Service won't start

1. Check environment variables are set
2. Verify port is correct (Railway sets PORT automatically)
3. Check logs for errors

### OCR not working

1. Verify Tesseract is installed (handled by Dockerfile)
2. Check GROQ_API_KEY is set
3. View logs: `backend/logs/ocr.log`

## Environment Variables

Required:
- `GROQ_API_KEY` - Groq API key for OCR

Optional:
- `HOST` - Host to bind (default: 0.0.0.0)
- `PORT` - Port to listen (Railway sets automatically)
- `ENVIRONMENT` - development/production (default: development)

## Production Checklist

- [ ] Environment variables configured
- [ ] GROQ_API_KEY set
- [ ] Health check working
- [ ] Logs accessible
- [ ] Frontend API URL updated
- [ ] Custom domain configured (if needed)

