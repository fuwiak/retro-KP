#!/bin/bash

# Build frontend and copy to backend for Railway deployment

echo "Building frontend..."

# Go to project root
cd "$(dirname "$0")/.."

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install
fi

# Build frontend
echo "Running npm run build..."
export VITE_API_BASE_URL="${VITE_API_BASE_URL:-/api}"
npm run build

# Copy dist to backend/static
if [ -d "dist" ]; then
    echo "Copying dist to backend/static..."
    mkdir -p backend/static
    cp -r dist/* backend/static/
    echo "Frontend built and copied to backend/static/"
else
    echo "Error: dist directory not found!"
    exit 1
fi

