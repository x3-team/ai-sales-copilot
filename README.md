# AI Sales Copilot 🚀

A state-of-the-art B2B sales development and coaching platform powered by **Google Gemini 1.5 Flash**. Practice sales pitches against realistic executive personas, craft high-converting outbound outreach campaigns, get instant tactical responses to tough customer objections, and audit complete call transcripts for deal-closing intelligence.

---

## ✨ Features

1. **Roleplay Arena** 🎭: Live-pitch simulated buyers (Skeptical CFO, Busy CTO, Curious PM) who respond dynamically, raise realistic objections, and demand ROI/technical proof. End the meeting to receive a full professional scorecard with strengths, weaknesses, and coaching analysis.
2. **Email Outreach Lab** ✉️: Generate personalized initial outbound cold emails and multi-step follow-ups tailored to product metrics, buyer titles, and specific company pain points using consultative, casual, bold, or analytical styles.
3. **Objection Coach** ⚡: Input difficult sales roadblocks and immediately output perfect scripted replies using world-class sales frameworks (LAER, Feel-Felt-Found, Reframing, or Case Narrative) along with probing discovery questions and psychological analysis.
4. **Call Transcript Analyzer** 📊: Paste complete transcripts from actual sales meetings. The auditor instantly isolates buyer purchase signals, indexes objection handling performance, scores the rep, and maps actionable deal-progression next steps.

---

## 🔑 API Key Setup (Google AI Studio)

The application uses Gemini 1.5 Flash models. It expects a **Google AI Studio API Key** (available free from [Google AI Studio](https://aistudio.google.com/)).

### In Cursor Cloud Agents (Recommended)
This platform automatically injects credentials as environment variables into Cloud Agent VMs.
1. Open your **Cursor Dashboard**.
2. Go to **Cloud Agents > Secrets**.
3. Create a secret named **`GEMINI_API_KEY`** (or `GOOGLE_API_KEY`) and paste your API key from Google AI Studio.
4. Future runs and agents will automatically pick up and run with full AI features activated!

### Running Locally
Create a `.env` file inside the `backend` folder:
```env
PORT=3001
GEMINI_API_KEY=your_google_ai_studio_api_key_here
```

*Note: If no API key is detected, the application gracefully falls back to a **Simulated Demo Mode** with realistic mockup responses, allowing you to preview and test the complete user experience without any configuration errors!*

---

## 🛠️ Tech Stack & Architecture

- **Frontend**: React (Vite), TypeScript, Tailwind CSS v4, Lucide Icons
- **Backend**: Node.js, Express, Google Gen AI SDK (`@google/generative-ai`)
- **Orchestration**: Structured as independent `backend` and `frontend` environments managed by a root package workspace enabling one-command setup and concurrent development.

---

## 🚀 Getting Started

### 1. Installation
Install all dependencies for root, backend, and frontend with a single command from the project root:
```bash
npm run install:all
```

### 2. Run in Development
Start both the backend API server (`http://localhost:3001`) and the Vite React frontend (`http://localhost:5173` or similar) concurrently:
```bash
npm run dev
```

### 3. Build for Production
To compile clean production builds for both modules:
```bash
npm run build:all
```

---

## 🌐 Deploying to Render

This codebase is configured to comply fully with **Render Platform Constraints**:
- **Port Binding**: The Express server automatically binds to `0.0.0.0:$PORT` (using `process.env.PORT || 3001`).
- **Unified Service**: You can build and deploy as a single Render Web Service by compiling the React frontend to static assets and having Express serve them, or deploy as separate Web and Static Site services.
- **Environment Variables**: Configure `GEMINI_API_KEY` in the Render service Environment Settings to activate production AI logic.
