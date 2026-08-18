# Cursor Cloud Agent Instructions

This repository is configured for an Express backend and a Vite React frontend utilizing Google Gemini 1.5 Flash models.

## 🛠️ Dev Environment details

- **Backend Location**: `/workspace/backend`
- **Frontend Location**: `/workspace/frontend`
- **Port mapping**:
  - Express Backend: `0.0.0.0:3001`
  - Vite Frontend: `0.0.0.0:5173`
- **Core Scripts**:
  - `npm run install:all` - Installs backend and frontend dependencies.
  - `npm run dev` - Launches backend and frontend concurrently in development mode.
  - `npm run build:all` - Generates production-ready builds.

## 🔑 AI Key & Credentials

The Google AI Studio API Key is expected as `GEMINI_API_KEY` or `GOOGLE_API_KEY` in environment variables. If missing, the backend runs in a graceful **Simulated Demo Mode** using realistic pre-coded responses so that linting, compilation, manual clicks, and general testing never break.

To configure the API Key:
- Local: Create `backend/.env` containing `GEMINI_API_KEY=your_key`
- Cloud: Go to **Cursor Dashboard > Cloud Agents > Secrets** and save `GEMINI_API_KEY`.
