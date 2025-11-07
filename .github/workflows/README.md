# GitHub Actions Workflows

## Available Workflows

### 1. CI (`ci.yml`)
**Triggers:** Push/PR to main/master/develop

Runs:
- ✅ Backend tests and linting
- ✅ Frontend build
- ✅ Docker image build and test
- ✅ Code quality checks

### 2. Deploy to Railway (`deploy-railway.yml`)
**Triggers:** Push to main, Manual dispatch

Deploys backend to Railway (requires `RAILWAY_TOKEN` secret).

### 3. Docker Build & Push (`docker-push.yml`)
**Triggers:** Push to main, Tags (v*), PRs

Builds and pushes Docker image to GitHub Container Registry.

### 4. Release (`release.yml`)
**Triggers:** Tag push (v*.*.*)

Creates GitHub release with Docker image.

### 5. Security Scan (`security.yml`)
**Triggers:** Push to main, PRs, Weekly (Sunday)

Scans for vulnerabilities in:
- Docker images (Trivy)
- Python dependencies (Safety)
- npm dependencies (npm audit)

## Required Secrets

Add these in GitHub Settings → Secrets and variables → Actions:

- `GROQ_API_KEY` - For backend tests (optional)
- `RAILWAY_TOKEN` - For Railway deployment (optional)
- `VITE_API_BASE_URL` - For frontend build (optional)

## Usage

Workflows run automatically on push/PR. To run manually:
1. Go to Actions tab
2. Select workflow
3. Click "Run workflow"

## Status Badges

Add to README.md:

```markdown
![CI](https://github.com/username/retro-sketch/workflows/CI/badge.svg)
![Security Scan](https://github.com/username/retro-sketch/workflows/Security%20Scan/badge.svg)
```

