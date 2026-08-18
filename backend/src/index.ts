import express from "express";
import cors from "cors";
import * as dotenv from "dotenv";
import {
  isGeminiConfigured,
  startRoleplay,
  continueRoleplay,
  evaluateRoleplay,
  generateEmail,
  handleObjection,
  analyzeTranscript,
} from "./services/gemini";

dotenv.config();

const app = express();
const port = parseInt(process.env.PORT || "3001", 10);

// Configure CORS to allow our frontend to make API calls
app.use(cors());
app.use(express.json());

// Log incoming requests for easier debugging
app.use((req, res, next) => {
  console.log(`[${new Date().toISOString()}] ${req.method} ${req.path}`);
  next();
});

// Health check and config status endpoint
app.get("/api/health", (req, res) => {
  res.json({
    status: "ok",
    timestamp: new Date().toISOString(),
    geminiConfigured: isGeminiConfigured(),
    message: isGeminiConfigured()
      ? "AI Sales Copilot backend is ready with Gemini 1.5 Flash!"
      : "AI Sales Copilot backend is running in SIMULATED DEMO mode. Set GEMINI_API_KEY to unlock AI features.",
  });
});

/**
 * Start roleplay session
 */
app.post("/api/roleplay/start", async (req, res) => {
  try {
    const { personaKey, productDescription, salesRepGoal } = req.body;
    if (!productDescription || !salesRepGoal) {
      return res.status(400).json({ error: "productDescription and salesRepGoal are required" });
    }
    const result = await startRoleplay(personaKey, productDescription, salesRepGoal);
    res.json(result);
  } catch (error: any) {
    console.error("Error starting roleplay:", error);
    res.status(500).json({ error: error.message || "Failed to start roleplay session" });
  }
});

/**
 * Continue roleplay session with a new message
 */
app.post("/api/roleplay/message", async (req, res) => {
  try {
    const { personaKey, productDescription, salesRepGoal, history, newMessage } = req.body;
    if (!newMessage || !history || !productDescription) {
      return res.status(400).json({ error: "newMessage, history, and productDescription are required" });
    }
    const result = await continueRoleplay(personaKey, productDescription, salesRepGoal, history, newMessage);
    res.json(result);
  } catch (error: any) {
    console.error("Error continuing roleplay:", error);
    res.status(500).json({ error: error.message || "Failed to send message" });
  }
});

/**
 * Evaluate completed roleplay
 */
app.post("/api/roleplay/evaluate", async (req, res) => {
  try {
    const { personaKey, productDescription, salesRepGoal, history } = req.body;
    if (!history || !productDescription) {
      return res.status(400).json({ error: "history and productDescription are required" });
    }
    const result = await evaluateRoleplay(personaKey, productDescription, salesRepGoal, history);
    res.json(result);
  } catch (error: any) {
    console.error("Error evaluating roleplay:", error);
    res.status(500).json({ error: error.message || "Failed to evaluate roleplay session" });
  }
});

/**
 * Generate email templates
 */
app.post("/api/email/generate", async (req, res) => {
  try {
    const { productName, productDesc, recipientName, recipientTitle, companyName, painPoint, emailGoal, tone } = req.body;
    if (!productName || !productDesc || !companyName) {
      return res.status(400).json({ error: "productName, productDesc, and companyName are required fields" });
    }
    const result = await generateEmail({
      productName,
      productDesc,
      recipientName: recipientName || "Prospect",
      recipientTitle: recipientTitle || "Decision Maker",
      companyName,
      painPoint: painPoint || "manual processes",
      emailGoal: emailGoal || "booking a short 10 minute call",
      tone: tone || "professional",
    });
    res.json(result);
  } catch (error: any) {
    console.error("Error generating email:", error);
    res.status(500).json({ error: error.message || "Failed to generate outbound emails" });
  }
});

/**
 * Handle objection with dynamic strategy
 */
app.post("/api/objections/handle", async (req, res) => {
  try {
    const { objection, productDesc, competitorContext, strategy } = req.body;
    if (!objection || !productDesc) {
      return res.status(400).json({ error: "objection and productDesc are required" });
    }
    const result = await handleObjection({
      objection,
      productDesc,
      competitorContext,
      strategy: strategy || "laer",
    });
    res.json(result);
  } catch (error: any) {
    console.error("Error handling objection:", error);
    res.status(500).json({ error: error.message || "Failed to generate objection responses" });
  }
});

/**
 * Analyze full transcript of a sales call
 */
app.post("/api/transcript/analyze", async (req, res) => {
  try {
    const { transcript } = req.body;
    if (!transcript) {
      return res.status(400).json({ error: "transcript is required" });
    }
    const result = await analyzeTranscript(transcript);
    res.json(result);
  } catch (error: any) {
    console.error("Error analyzing transcript:", error);
    res.status(500).json({ error: error.message || "Failed to analyze sales transcript" });
  }
});

// Start listening
app.listen(port, "0.0.0.0", () => {
  console.log(`AI Sales Copilot server running on http://0.0.0.0:${port}`);
});
