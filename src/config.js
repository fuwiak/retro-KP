// Global API configuration
// Automatically detects API URL from window (set by backend) or environment

export function getApiBaseUrl() {
  // Priority 1: Window variable (set by backend in production)
  if (typeof window !== 'undefined' && window.API_BASE_URL) {
    let apiUrl = window.API_BASE_URL;
    // Force HTTPS if current page is HTTPS (fix Mixed Content)
    if (window.location.protocol === 'https:' && apiUrl.startsWith('http://')) {
      apiUrl = apiUrl.replace('http://', 'https://');
    }
    return apiUrl;
  }
  
  // Priority 2: Environment variable (Vite build-time)
  if (import.meta.env.VITE_API_BASE_URL) {
    let apiUrl = import.meta.env.VITE_API_BASE_URL;
    // Force HTTPS if current page is HTTPS
    if (typeof window !== 'undefined' && window.location.protocol === 'https:' && apiUrl.startsWith('http://')) {
      apiUrl = apiUrl.replace('http://', 'https://');
    }
    return apiUrl;
  }
  
  // Priority 3: Auto-detect from current origin (production)
  if (typeof window !== 'undefined' && window.location) {
    const origin = window.location.origin;
    // Don't use localhost in production
    if (origin && !origin.includes('localhost') && !origin.includes('127.0.0.1')) {
      // Always use HTTPS for production domains (fix Mixed Content error)
      const httpsOrigin = origin.replace(/^http:/, 'https:');
      return `${httpsOrigin}/api`;
    }
  }
  
  // Fallback: localhost for development
  return 'http://localhost:3000/api';
}

export const API_BASE_URL = getApiBaseUrl();

