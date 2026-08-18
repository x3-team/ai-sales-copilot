import { useState, useEffect, useRef } from "react";
import {
  Sparkles,
  Mail,
  Zap,
  FileText,
  Send,
  RefreshCw,
  Award,
  CheckCircle,
  AlertCircle,
  Info,
  Users,
  Copy,
  Building,
  Briefcase
} from "lucide-react";

// API Base URL (default to localhost 3001, or fallback to current host port 3001)
const API_URL = "http://localhost:3001/api";

type Tab = "roleplay" | "email" | "objection" | "transcript";

interface Persona {
  key: string;
  name: string;
  title: string;
  avatar: string;
  tagline: string;
  behavior: string;
}

const PERSONAS: Persona[] = [
  {
    key: "skeptical_cfo",
    name: "Harold Vance",
    title: "Chief Financial Officer (CFO)",
    avatar: "💼",
    tagline: "ROI-obsessed, budget-conscious, anti-hype",
    behavior: "Challenges pricing, demands quantitative metrics, expects cost reduction or efficiency proof."
  },
  {
    key: "busy_cto",
    name: "Sarah Jenkins",
    title: "Chief Technology Officer (CTO)",
    avatar: "💻",
    tagline: "Tech-savvy, integration-focused, time-starved",
    behavior: "Demands architectural details, security compliance (SOC2), onboarding time, and stack compatibility."
  },
  {
    key: "curious_pm",
    name: "Elena Rostova",
    title: "Head of Product Management",
    avatar: "🚀",
    tagline: "User-centric, adoption-focused, collaborative",
    behavior: "Cares about user experience, product adoption rate, features, training time, and collaborative workflows."
  }
];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("roleplay");
  const [geminiConfigured, setGeminiConfigured] = useState<boolean | null>(null);
  const [healthChecking, setHealthChecking] = useState(true);

  // General Notification State
  const [copiedText, setCopiedText] = useState<string | null>(null);

  // 1. Roleplay State
  const [selectedPersona, setSelectedPersona] = useState<string>("skeptical_cfo");
  const [productDescription, setProductDescription] = useState<string>(
    "A cloud-based AI customer support agent that handles 80% of common queries instantly with 95% satisfaction, reducing customer support costs by 40%."
  );
  const [salesGoal, setSalesGoal] = useState<string>(
    "Secure a 15-minute product demo next week to show integration and personalized ROI."
  );
  const [roleplayActive, setRoleplayActive] = useState<boolean>(false);
  const [roleplayMessages, setRoleplayHistory] = useState<Array<{ role: "user" | "model"; text: string }>>([]);
  const [userInput, setUserInput] = useState<string>("");
  const [roleplayLoading, setRoleplayLoading] = useState<boolean>(false);
  const [evaluation, setEvaluation] = useState<any | null>(null);
  const [evaluating, setEvaluating] = useState<boolean>(false);

  // 2. Email & Lead Enrichment State
  const [emailForm, setEmailForm] = useState({
    productName: "AI Sales Copilot",
    productDesc: "An AI-powered sales training platform that runs instant interactive buyer roleplays, email templates generation, and transcript audits.",
    recipientName: "Иван Иванов",
    recipientTitle: "Коммерческий директор",
    companyName: "Сбербанк",
    painPoint: "Длительный цикл сделки и низкая конверсия новых менеджеров",
    emailGoal: "назначение 15-минутной онлайн-демонстрации",
    tone: "professional"
  });
  const [generatedEmail, setGeneratedEmail] = useState<any | null>(null);
  const [emailLoading, setEmailLoading] = useState<boolean>(false);

  // Integrations (HH.ru & DaData) State
  const [hhSearchQuery, setHhSearchQuery] = useState<string>("Менеджер по продажам");
  const [hhVacancies, setHhVacancies] = useState<any[]>([]);
  const [hhLoading, setHhLoading] = useState<boolean>(false);

  const [dadataQuery, setDadataQuery] = useState<string>("7707083893");
  const [dadataResults, setDadataResults] = useState<any[]>([]);
  const [dadataLoading, setDadataLoading] = useState<boolean>(false);

  // 3. Objection State
  const [objectionForm, setObjectionForm] = useState({
    objection: "We don't have the budget for this right now, we are under a strict software spending freeze.",
    productDesc: "AI-driven customer analytics platform that saves marketing managers 15 hours a week of manual report building and increases conversion by 12%.",
    competitorContext: "They are currently using Google Analytics (free) and manual Excel spreadsheets.",
    strategy: "laer"
  });
  const [objectionResponse, setObjectionResponse] = useState<any | null>(null);
  const [objectionLoading, setObjectionLoading] = useState<boolean>(false);

  // 4. Transcript State
  const [transcriptInput, setTranscriptInput] = useState<string>(
    `Rep: Thanks for hopping on the call, Harold. How's your week going?
Harold (CFO): It's busy. Let's get straight to it. We have a software freeze right now. Why are we talking?
Rep: Absolutely. I know budget is top of mind. Our tool, SalesBoost, helps your reps automate pipeline reports, saving them about 10 hours a week.
Harold (CFO): Saving time is fine, but does it actually bring in revenue? What's the ROI?
Rep: Yes! Reps who use SalesBoost generally close 15% more deals because they spend more time selling.
Harold (CFO): That sounds like standard sales pitch fluff. Can you prove that? Who else in our industry is using you?
Rep: We work with SaaS Corp and GrowthTech. They saw a full return on investment within 4 months.
Harold (CFO): Well, if we wanted to evaluate this, what is the onboarding cost and security setup?
Rep: Onboarding is quite quick, usually taking about 2 weeks. It integrates via OAuth.
Harold (CFO): Send me a case study and security sheet. I'll read it when I can.
Rep: Sounds great. Would you be open to a quick calendar invite for next Thursday to go over it?
Harold (CFO): Sure, send a calendar hold and we'll see.`
  );
  const [transcriptAnalysis, setTranscriptAnalysis] = useState<any | null>(null);
  const [transcriptLoading, setTranscriptLoading] = useState<boolean>(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Check backend health and Gemini config on mount
  useEffect(() => {
    checkHealth();
  }, []);

  // Auto-scroll chat to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [roleplayMessages, roleplayLoading]);

  const checkHealth = async () => {
    setHealthChecking(true);
    try {
      const response = await fetch(`${API_URL}/health`);
      const data = await response.json();
      setGeminiConfigured(data.geminiConfigured);
    } catch (error) {
      console.error("Error contacting backend health endpoint:", error);
      setGeminiConfigured(false);
    } finally {
      setHealthChecking(false);
    }
  };

  const copyToClipboard = (text: string, identifier: string) => {
    navigator.clipboard.writeText(text);
    setCopiedText(identifier);
    setTimeout(() => setCopiedText(null), 2000);
  };

  // 1. Roleplay Functions
  const handleStartRoleplay = async () => {
    setRoleplayLoading(true);
    setEvaluation(null);
    setRoleplayHistory([]);
    try {
      const response = await fetch(`${API_URL}/roleplay/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          personaKey: selectedPersona,
          productDescription,
          salesRepGoal: salesGoal
        })
      });
      const data = await response.json();
      if (data.error) throw new Error(data.error);

      setRoleplayHistory([
        { role: "model", text: data.buyerMessage }
      ]);
      setRoleplayActive(true);
    } catch (err: any) {
      alert("Error starting roleplay: " + err.message);
    } finally {
      setRoleplayLoading(false);
    }
  };

  const handleSendRoleplayMessage = async () => {
    if (!userInput.trim() || roleplayLoading) return;

    const repMessage = userInput;
    setUserInput("");

    // Optimistically update history with rep's message
    const updatedHistory = [...roleplayMessages, { role: "user" as const, text: repMessage }];
    setRoleplayHistory(updatedHistory);
    setRoleplayLoading(true);

    try {
      // Format history for backend
      const formattedHistory = updatedHistory.map(m => ({
        role: m.role,
        parts: [{ text: m.text }]
      }));

      const response = await fetch(`${API_URL}/roleplay/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          personaKey: selectedPersona,
          productDescription,
          salesRepGoal: salesGoal,
          history: formattedHistory,
          newMessage: repMessage
        })
      });
      const data = await response.json();
      if (data.error) throw new Error(data.error);

      setRoleplayHistory([
        ...updatedHistory,
        { role: "model", text: data.buyerMessage }
      ]);
    } catch (err: any) {
      alert("Error sending message: " + err.message);
    } finally {
      setRoleplayLoading(false);
    }
  };

  const handleEvaluateRoleplay = async () => {
    if (roleplayMessages.length < 2) {
      alert("Please exchange at least a few messages before evaluating.");
      return;
    }
    setEvaluating(true);
    try {
      const formattedHistory = roleplayMessages.map(m => ({
        role: m.role,
        parts: [{ text: m.text }]
      }));

      const response = await fetch(`${API_URL}/roleplay/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          personaKey: selectedPersona,
          productDescription,
          salesRepGoal: salesGoal,
          history: formattedHistory
        })
      });
      const data = await response.json();
      if (data.error) throw new Error(data.error);

      setEvaluation(data);
      setRoleplayActive(false);
    } catch (err: any) {
      alert("Error evaluating roleplay: " + err.message);
    } finally {
      setEvaluating(false);
    }
  };

  // 2. Email Functions
  const handleGenerateEmail = async () => {
    setEmailLoading(true);
    setGeneratedEmail(null);
    try {
      const response = await fetch(`${API_URL}/email/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(emailForm)
      });
      const data = await response.json();
      if (data.error) throw new Error(data.error);
      setGeneratedEmail(data);
    } catch (err: any) {
      alert("Error generating email: " + err.message);
    } finally {
      setEmailLoading(false);
    }
  };

  // Integration Functions (HH.ru & DaData)
  const handleHHSearch = async () => {
    if (!hhSearchQuery.trim()) return;
    setHhLoading(true);
    try {
      const response = await fetch(`${API_URL}/hh/vacancies?q=${encodeURIComponent(hhSearchQuery)}`);
      const data = await response.json();
      if (data.error) throw new Error(data.error);
      setHhVacancies(data.vacancies || []);
    } catch (err: any) {
      alert("Error fetching HH vacancies: " + err.message);
    } finally {
      setHhLoading(false);
    }
  };

  const handleDaDataEnrich = async () => {
    if (!dadataQuery.trim()) return;
    setDadataLoading(true);
    try {
      const response = await fetch(`${API_URL}/dadata/company`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ company: dadataQuery })
      });
      const data = await response.json();
      if (data.error) throw new Error(data.error);
      setDadataResults(data.suggestions || []);
    } catch (err: any) {
      alert("Error enriching via DaData: " + err.message);
    } finally {
      setDadataLoading(false);
    }
  };

  // 3. Objection Functions
  const handleObjectionSubmit = async () => {
    setObjectionLoading(true);
    setObjectionResponse(null);
    try {
      const response = await fetch(`${API_URL}/objections/handle`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(objectionForm)
      });
      const data = await response.json();
      if (data.error) throw new Error(data.error);
      setObjectionResponse(data);
    } catch (err: any) {
      alert("Error handling objection: " + err.message);
    } finally {
      setObjectionLoading(false);
    }
  };

  // 4. Transcript Functions
  const handleAnalyzeTranscript = async () => {
    if (!transcriptInput.trim()) return;
    setTranscriptLoading(true);
    setTranscriptAnalysis(null);
    try {
      const response = await fetch(`${API_URL}/transcript/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: transcriptInput })
      });
      const data = await response.json();
      if (data.error) throw new Error(data.error);
      setTranscriptAnalysis(data);
    } catch (err: any) {
      alert("Error analyzing transcript: " + err.message);
    } finally {
      setTranscriptLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col antialiased">
      {/* Top Banner / API Key Status */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="bg-brand-500 text-white p-2 rounded-xl shadow-md shadow-brand-500/20">
              <Sparkles className="h-6 w-6" />
            </div>
            <div>
              <h1 className="font-bold text-lg text-slate-900 leading-none">AI Sales Copilot</h1>
              <p className="text-xs text-slate-500 mt-1">Powering Sales Objections & Roleplay with Gemini 1.5 Flash</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {healthChecking ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-slate-100 text-slate-600 animate-pulse">
                <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Check Connection
              </span>
            ) : geminiConfigured ? (
              <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                <span className="h-2 w-2 rounded-full bg-emerald-500 animate-ping" /> Gemini 1.5 Flash Active
              </span>
            ) : (
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200">
                  <AlertCircle className="h-3.5 w-3.5" /> Demo Sandbox Mode
                </span>
                <button
                  onClick={checkHealth}
                  className="p-1.5 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition"
                  title="Retry connecting to API"
                >
                  <RefreshCw className="h-4 w-4" />
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-7xl mx-auto w-full px-4 sm:px-6 lg:px-8 py-8 flex flex-col gap-8">
        {/* Connection Guidance banner if not configured */}
        {geminiConfigured === false && (
          <div className="bg-amber-50 border border-amber-200 rounded-2xl p-4 sm:p-5 flex flex-col sm:flex-row gap-4 items-start shadow-sm">
            <div className="p-2.5 bg-amber-100 rounded-xl text-amber-700 shrink-0">
              <Info className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <h3 className="font-semibold text-amber-900 text-sm sm:text-base">Connect Google AI Studio API Key</h3>
              <p className="text-amber-800 text-xs sm:text-sm mt-1 leading-relaxed">
                We detected that your Google AI Studio API Key is not loaded in the agent's background environment.
                You are currently running in **Simulated Demo Mode**.
                To unlock true, state-of-the-art Gemini 1.5 Flash intelligence:
              </p>
              <div className="flex flex-col sm:flex-row gap-4 mt-3 pt-3 border-t border-amber-200/50 text-xs text-amber-800">
                <span>
                  <strong>Option A:</strong> Go to the <strong>Cursor Dashboard (Cloud Agents &gt; Secrets)</strong> and add a secret named <code>GEMINI_API_KEY</code> or <code>GOOGLE_API_KEY</code>.
                </span>
                <span>
                  <strong>Option B:</strong> Create a <code>.env</code> file in the <code>/workspace/backend/</code> directory and add <code>GEMINI_API_KEY=your_key_here</code>.
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="flex bg-slate-100 p-1.5 rounded-xl self-start gap-1 w-full sm:w-auto overflow-x-auto shadow-inner">
          <button
            onClick={() => setActiveTab("roleplay")}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition shrink-0 ${
              activeTab === "roleplay"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
            }`}
          >
            <Users className="h-4 w-4 text-brand-500" /> Roleplay Arena
          </button>
          <button
            onClick={() => setActiveTab("email")}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition shrink-0 ${
              activeTab === "email"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
            }`}
          >
            <Mail className="h-4 w-4 text-violet-500" /> Email Outreach Lab
          </button>
          <button
            onClick={() => setActiveTab("objection")}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition shrink-0 ${
              activeTab === "objection"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
            }`}
          >
            <Zap className="h-4 w-4 text-amber-500" /> Objection Coach
          </button>
          <button
            onClick={() => setActiveTab("transcript")}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition shrink-0 ${
              activeTab === "transcript"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-600 hover:text-slate-900 hover:bg-slate-50"
            }`}
          >
            <FileText className="h-4 w-4 text-teal-500" /> Call Analyzer
          </button>
        </div>

        {/* Tab Contents */}
        <div className="flex-1 bg-white rounded-3xl border border-slate-200 shadow-sm overflow-hidden flex flex-col min-h-[600px]">
          
          {/* TAB 1: ROLEPLAY ARENA */}
          {activeTab === "roleplay" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 flex-1 divide-y lg:divide-y-0 lg:divide-x divide-slate-200">
              
              {/* Configuration panel (Left) */}
              <div className="lg:col-span-4 p-6 sm:p-8 flex flex-col gap-6 bg-slate-50/50 overflow-y-auto">
                <div>
                  <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                    <Users className="h-5 w-5 text-brand-500" /> Configure Roleplay
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">Setup your sales scenario and choose the persona you want to pitch to.</p>
                </div>

                <div className="flex flex-col gap-4">
                  {/* Persona Selector */}
                  <label className="text-xs font-semibold text-slate-700 tracking-wider uppercase">1. Buyer Persona</label>
                  <div className="flex flex-col gap-3">
                    {PERSONAS.map(p => (
                      <button
                        key={p.key}
                        onClick={() => !roleplayActive && setSelectedPersona(p.key)}
                        disabled={roleplayActive}
                        className={`p-4 rounded-xl border text-left transition flex gap-3 items-start ${
                          selectedPersona === p.key
                            ? "border-brand-500 bg-brand-50/40 shadow-sm ring-1 ring-brand-500/30"
                            : "border-slate-200 bg-white hover:bg-slate-100/50"
                        } ${roleplayActive ? "opacity-60 cursor-not-allowed" : ""}`}
                      >
                        <span className="text-2xl mt-0.5" role="img" aria-label={p.name}>{p.avatar}</span>
                        <div className="flex-1 min-w-0">
                          <h4 className="font-semibold text-sm text-slate-900">{p.name}</h4>
                          <p className="text-xs font-medium text-brand-600">{p.title}</p>
                          <p className="text-xs text-slate-500 mt-1 leading-snug line-clamp-2">{p.tagline}</p>
                        </div>
                      </button>
                    ))}
                  </div>

                  {/* Product Details */}
                  <div className="flex flex-col gap-1.5 mt-2">
                    <label className="text-xs font-semibold text-slate-700 tracking-wider uppercase">2. What are you selling?</label>
                    <textarea
                      disabled={roleplayActive}
                      value={productDescription}
                      onChange={(e) => setProductDescription(e.target.value)}
                      rows={3}
                      className="w-full text-sm border border-slate-200 rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 disabled:opacity-75 disabled:bg-slate-100"
                      placeholder="e.g. Sales training platform, cloud storage..."
                    />
                  </div>

                  {/* Sales rep goal */}
                  <div className="flex flex-col gap-1.5">
                    <label className="text-xs font-semibold text-slate-700 tracking-wider uppercase">3. Pitch Goal</label>
                    <textarea
                      disabled={roleplayActive}
                      value={salesGoal}
                      onChange={(e) => setSalesGoal(e.target.value)}
                      rows={2}
                      className="w-full text-sm border border-slate-200 rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 disabled:opacity-75 disabled:bg-slate-100"
                      placeholder="e.g. Booking a 15 min calendar invite next week"
                    />
                  </div>

                  {/* Start/Reset Trigger */}
                  {!roleplayActive ? (
                    <button
                      onClick={handleStartRoleplay}
                      disabled={roleplayLoading}
                      className="w-full mt-4 bg-brand-500 hover:bg-brand-600 disabled:bg-brand-400 text-white font-semibold py-3 rounded-xl shadow-lg shadow-brand-500/10 transition flex items-center justify-center gap-2"
                    >
                      {roleplayLoading ? (
                        <>
                          <RefreshCw className="h-4 w-4 animate-spin" /> Dialing executive...
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4 w-4" /> Start Roleplay Meeting
                        </>
                      )}
                    </button>
                  ) : (
                    <div className="flex gap-2 mt-4">
                      <button
                        onClick={handleEvaluateRoleplay}
                        disabled={evaluating}
                        className="flex-1 bg-emerald-600 hover:bg-emerald-700 disabled:bg-emerald-500 text-white font-semibold py-3 rounded-xl transition flex items-center justify-center gap-2 shadow-lg shadow-emerald-500/10"
                      >
                        {evaluating ? (
                          <>
                            <RefreshCw className="h-4 w-4 animate-spin" /> Evaluating...
                          </>
                        ) : (
                          <>
                            <Award className="h-4 w-4" /> End & Evaluate
                          </>
                        )}
                      </button>
                      <button
                        onClick={() => {
                          setRoleplayActive(false);
                          setRoleplayHistory([]);
                          setEvaluation(null);
                        }}
                        className="px-4 bg-slate-200 hover:bg-slate-300 text-slate-700 font-semibold rounded-xl transition"
                      >
                        Reset
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Conversation Area (Right) */}
              <div className="lg:col-span-8 flex flex-col h-[550px] lg:h-auto overflow-hidden">
                {!roleplayActive && !evaluation ? (
                  <div className="flex-1 flex flex-col items-center justify-center p-8 text-center bg-slate-50/20">
                    <div className="bg-brand-50 p-4 rounded-full text-brand-600 mb-4 animate-bounce">
                      <Users className="h-8 w-8" />
                    </div>
                    <h3 className="text-lg font-bold text-slate-900">Roleplay Arena Ready</h3>
                    <p className="text-slate-500 text-sm max-w-md mt-2 leading-relaxed">
                      Select your customer, describe your product, and start a realistic conversation with a demanding buyer persona.
                      After you finish, get detailed evaluation analytics!
                    </p>
                  </div>
                ) : evaluation ? (
                  /* Scorecard/Evaluation Display */
                  <div className="flex-1 overflow-y-auto p-6 sm:p-8 flex flex-col gap-6">
                    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                      {/* Score Banner */}
                      <div className="bg-brand-900 text-white p-6 sm:p-8 flex flex-col sm:flex-row items-center gap-6">
                        <div className="relative flex items-center justify-center shrink-0 h-24 w-24 rounded-full border-4 border-brand-500 bg-brand-950">
                          <span className="text-3xl font-extrabold text-white">{evaluation.score}</span>
                          <span className="text-xs text-brand-300 absolute bottom-3">/100</span>
                        </div>
                        <div className="text-center sm:text-left">
                          <span className="inline-flex px-2.5 py-1 rounded-full text-xs font-semibold bg-brand-800 text-brand-200 uppercase tracking-wider mb-2">Performance Score</span>
                          <h3 className="font-bold text-xl sm:text-2xl leading-none">Roleplay Evaluation Report</h3>
                          <p className="text-xs sm:text-sm text-brand-200 mt-2 leading-relaxed">
                            Simulated Pitch to **{PERSONAS.find(p => p.key === selectedPersona)?.name}** (C-Level Executive)
                          </p>
                        </div>
                      </div>

                      {/* Details Grid */}
                      <div className="p-6 sm:p-8 grid grid-cols-1 md:grid-cols-2 gap-6 divide-y md:divide-y-0 md:divide-x divide-slate-100">
                        {/* Strengths */}
                        <div className="flex flex-col gap-3">
                          <h4 className="font-bold text-slate-900 flex items-center gap-2 text-sm uppercase tracking-wider text-emerald-600">
                            <CheckCircle className="h-4 w-4" /> Notable Strengths
                          </h4>
                          <ul className="flex flex-col gap-2">
                            {evaluation.strengths?.map((s: string, idx: number) => (
                              <li key={idx} className="text-sm text-slate-700 bg-emerald-50/50 p-3 rounded-lg border border-emerald-100 flex gap-2">
                                <span className="text-emerald-500 font-bold shrink-0">✓</span>
                                <span className="leading-snug">{s}</span>
                              </li>
                            ))}
                          </ul>
                        </div>

                        {/* Weaknesses / Improvements */}
                        <div className="flex flex-col gap-3 md:pl-6">
                          <h4 className="font-bold text-slate-900 flex items-center gap-2 text-sm uppercase tracking-wider text-rose-500">
                            <AlertCircle className="h-4 w-4" /> Areas of Improvement
                          </h4>
                          <ul className="flex flex-col gap-2">
                            {evaluation.weaknesses?.map((w: string, idx: number) => (
                              <li key={idx} className="text-sm text-slate-700 bg-rose-50/50 p-3 rounded-lg border border-rose-100 flex gap-2">
                                <span className="text-rose-500 font-bold shrink-0">!</span>
                                <span className="leading-snug">{w}</span>
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>

                      {/* Coach Objections & Next Steps */}
                      <div className="border-t border-slate-100 p-6 sm:p-8 flex flex-col gap-6 bg-slate-50/30">
                        <div>
                          <h4 className="font-bold text-slate-900 text-sm tracking-wide uppercase mb-2">Objection Handling Drilldown</h4>
                          <p className="text-sm text-slate-700 leading-relaxed bg-white border border-slate-200 p-4 rounded-xl shadow-sm">
                            {evaluation.objectionHandling}
                          </p>
                        </div>

                        <div>
                          <h4 className="font-bold text-slate-900 text-sm tracking-wide uppercase mb-2">Closing & Next Steps Coach</h4>
                          <p className="text-sm text-slate-700 leading-relaxed bg-white border border-slate-200 p-4 rounded-xl shadow-sm">
                            {evaluation.nextStepsAdvice}
                          </p>
                        </div>

                        <div>
                          <h4 className="font-bold text-slate-900 text-sm tracking-wide uppercase mb-2">Call Conversation Flow</h4>
                          <p className="text-sm text-slate-600 leading-relaxed">
                            {evaluation.transcriptAnalysis}
                          </p>
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => setEvaluation(null)}
                      className="self-center bg-slate-800 hover:bg-slate-900 text-white font-medium px-6 py-2.5 rounded-xl transition"
                    >
                      Practice Again
                    </button>
                  </div>
                ) : (
                  /* Active Roleplay Conversation */
                  <div className="flex-1 flex flex-col h-full bg-slate-50/20">
                    {/* Buyer identity bar */}
                    <div className="border-b border-slate-200 px-6 py-4 bg-white flex items-center justify-between shadow-sm">
                      <div className="flex items-center gap-3">
                        <span className="text-2xl" role="img" aria-label="Avatar">
                          {PERSONAS.find(p => p.key === selectedPersona)?.avatar}
                        </span>
                        <div>
                          <h3 className="font-bold text-slate-900 text-sm leading-tight">
                            {PERSONAS.find(p => p.key === selectedPersona)?.name}
                          </h3>
                          <p className="text-xs font-semibold text-brand-600">
                            {PERSONAS.find(p => p.key === selectedPersona)?.title}
                          </p>
                        </div>
                      </div>
                      <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-brand-50 border border-brand-200 text-brand-700 rounded-full text-xs font-semibold">
                        <span className="h-1.5 w-1.5 rounded-full bg-brand-500 animate-pulse" /> Meeting In Progress
                      </span>
                    </div>

                    {/* Messages Container */}
                    <div className="flex-1 overflow-y-auto p-6 flex flex-col gap-4">
                      {roleplayMessages.map((m, idx) => (
                        <div
                          key={idx}
                          className={`flex flex-col max-w-[85%] ${
                            m.role === "user" ? "self-end items-end" : "self-start items-start"
                          }`}
                        >
                          <span className="text-[10px] font-bold text-slate-400 mb-1 px-1">
                            {m.role === "user" ? "YOU (SALES REP)" : PERSONAS.find(p => p.key === selectedPersona)?.name.toUpperCase()}
                          </span>
                          <div
                            className={`p-3.5 rounded-2xl text-sm leading-relaxed shadow-sm ${
                              m.role === "user"
                                ? "bg-brand-500 text-white rounded-tr-none"
                                : "bg-white border border-slate-200 text-slate-800 rounded-tl-none"
                            }`}
                          >
                            {m.text}
                          </div>
                        </div>
                      ))}

                      {roleplayLoading && (
                        <div className="self-start flex flex-col max-w-[80%] items-start">
                          <span className="text-[10px] font-bold text-slate-400 mb-1 px-1">
                            {PERSONAS.find(p => p.key === selectedPersona)?.name.toUpperCase()} (CFO) IS THINKING...
                          </span>
                          <div className="bg-white border border-slate-200 text-slate-500 p-4 rounded-2xl rounded-tl-none shadow-sm flex items-center gap-2">
                            <span className="h-1.5 w-1.5 bg-brand-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
                            <span className="h-1.5 w-1.5 bg-brand-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
                            <span className="h-1.5 w-1.5 bg-brand-500 rounded-full animate-bounce" />
                          </div>
                        </div>
                      )}

                      <div ref={messagesEndRef} />
                    </div>

                    {/* Input Bar */}
                    <div className="border-t border-slate-200 p-4 bg-white flex gap-2">
                      <input
                        type="text"
                        value={userInput}
                        onChange={(e) => setUserInput(e.target.value)}
                        onKeyDown={(e) => e.key === "Enter" && handleSendRoleplayMessage()}
                        disabled={roleplayLoading}
                        placeholder={`Pitch to ${PERSONAS.find(p => p.key === selectedPersona)?.name}...`}
                        className="flex-1 border border-slate-200 rounded-xl px-4 py-3 focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 text-sm"
                      />
                      <button
                        onClick={handleSendRoleplayMessage}
                        disabled={roleplayLoading || !userInput.trim()}
                        className="bg-brand-500 hover:bg-brand-600 disabled:bg-slate-200 disabled:text-slate-400 text-white p-3 rounded-xl transition"
                      >
                        <Send className="h-5 w-5" />
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 2: EMAIL OUTREACH LAB */}
          {activeTab === "email" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 flex-1 divide-y lg:divide-y-0 lg:divide-x divide-slate-200">
              
              {/* Form panel (Left) */}
              <div className="lg:col-span-5 p-6 sm:p-8 flex flex-col gap-5 bg-slate-50/50 overflow-y-auto">
                <div>
                  <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                    <Mail className="h-5 w-5 text-violet-500" /> Outreach Campaign Lab
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">Generate high-converting outbound copy for any company and person instantly.</p>
                </div>

                <div className="flex flex-col gap-4">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1">
                      <label className="text-xs font-semibold text-slate-700">Product Name</label>
                      <input
                        type="text"
                        value={emailForm.productName}
                        onChange={(e) => setEmailForm({ ...emailForm, productName: e.target.value })}
                        className="text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-xs font-semibold text-slate-700">Recipient Name</label>
                      <input
                        type="text"
                        value={emailForm.recipientName}
                        onChange={(e) => setEmailForm({ ...emailForm, recipientName: e.target.value })}
                        className="text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500"
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1">
                      <label className="text-xs font-semibold text-slate-700">Recipient Title</label>
                      <input
                        type="text"
                        value={emailForm.recipientTitle}
                        onChange={(e) => setEmailForm({ ...emailForm, recipientTitle: e.target.value })}
                        className="text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500"
                        placeholder="e.g. VP of Sales"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-xs font-semibold text-slate-700">Company Name</label>
                      <input
                        type="text"
                        value={emailForm.companyName}
                        onChange={(e) => setEmailForm({ ...emailForm, companyName: e.target.value })}
                        className="text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500"
                      />
                    </div>
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-semibold text-slate-700">Product / Solution Description</label>
                    <textarea
                      value={emailForm.productDesc}
                      onChange={(e) => setEmailForm({ ...emailForm, productDesc: e.target.value })}
                      rows={3}
                      className="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-semibold text-slate-700">Recipient's Core Pain Point</label>
                    <input
                      type="text"
                      value={emailForm.painPoint}
                      onChange={(e) => setEmailForm({ ...emailForm, painPoint: e.target.value })}
                      className="text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500"
                      placeholder="e.g. high customer churn, slow pipeline speed..."
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3">
                    <div className="flex flex-col gap-1">
                      <label className="text-xs font-semibold text-slate-700">Email Objective / CTA</label>
                      <input
                        type="text"
                        value={emailForm.emailGoal}
                        onChange={(e) => setEmailForm({ ...emailForm, emailGoal: e.target.value })}
                        className="text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500"
                      />
                    </div>
                    <div className="flex flex-col gap-1">
                      <label className="text-xs font-semibold text-slate-700">Tone of Voice</label>
                      <select
                        value={emailForm.tone}
                        onChange={(e) => setEmailForm({ ...emailForm, tone: e.target.value })}
                        className="text-sm border border-slate-200 rounded-xl px-3 py-2 focus:outline-none focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500"
                      >
                        <option value="professional">💼 Professional / Consultative</option>
                        <option value="casual">👋 Casual / Conversational</option>
                        <option value="bold">🔥 Bold / Disruptive</option>
                        <option value="analytical">📊 Analytical / Data-driven</option>
                      </select>
                    </div>
                  </div>

                  <button
                    onClick={handleGenerateEmail}
                    disabled={emailLoading}
                    className="w-full mt-2 bg-violet-600 hover:bg-violet-700 disabled:bg-violet-400 text-white font-semibold py-3 rounded-xl shadow-lg shadow-violet-600/10 transition flex items-center justify-center gap-2"
                  >
                    {emailLoading ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" /> Crafting copy...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" /> Generate Outbound Pitch
                      </>
                    )}
                  </button>

                  {/* HH.ru Lead Discovery Integration */}
                  <div className="border-t border-slate-200 pt-4 flex flex-col gap-2">
                    <label className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                      <Briefcase className="h-4 w-4 text-red-500" /> HH.ru Vacancies Lead Scraper
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={hhSearchQuery}
                        onChange={(e) => setHhSearchQuery(e.target.value)}
                        placeholder="Search HH jobs..."
                        className="flex-1 text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-red-500"
                      />
                      <button
                        onClick={handleHHSearch}
                        disabled={hhLoading}
                        className="bg-red-500 hover:bg-red-600 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition shrink-0"
                      >
                        {hhLoading ? "..." : "Find Leads"}
                      </button>
                    </div>
                  </div>

                  {/* DaData Company Enrichment Integration */}
                  <div className="border-t border-slate-200 pt-3 flex flex-col gap-2">
                    <label className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-1.5">
                      <Building className="h-4 w-4 text-blue-500" /> DaData Company Enrichment
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={dadataQuery}
                        onChange={(e) => setDadataQuery(e.target.value)}
                        placeholder="Enter Company Name or INN..."
                        className="flex-1 text-xs border border-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-blue-500"
                      />
                      <button
                        onClick={handleDaDataEnrich}
                        disabled={dadataLoading}
                        className="bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium px-3 py-1.5 rounded-lg transition shrink-0"
                      >
                        {dadataLoading ? "..." : "Enrich Data"}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Display panel (Right) */}
              <div className="lg:col-span-7 p-6 sm:p-8 flex flex-col gap-6 overflow-y-auto">
                {!generatedEmail ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-center py-16 bg-slate-50/20">
                    <div className="bg-violet-50 p-4 rounded-full text-violet-500 mb-4">
                      <Mail className="h-8 w-8" />
                    </div>
                    <h3 className="text-lg font-bold text-slate-900">Outbound Copy Sandbox</h3>
                    <p className="text-slate-500 text-sm max-w-sm mt-2 leading-relaxed">
                      Fill out the client background and click generate to build a customized outreach email and multi-day sequence.
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-6">
                    {/* Primary Email */}
                    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                      <div className="bg-violet-50 px-5 py-4 border-b border-slate-200 flex justify-between items-center">
                        <div className="flex items-center gap-2">
                          <span className="flex h-5 w-5 rounded-full bg-violet-600 items-center justify-center text-[10px] font-bold text-white">1</span>
                          <span className="text-sm font-semibold text-violet-900">Email #1: Initial Cold Outreach</span>
                        </div>
                        <button
                          onClick={() => copyToClipboard(`Subject: ${generatedEmail.subject}\n\n${generatedEmail.body}`, "email1")}
                          className="flex items-center gap-1.5 text-xs text-violet-700 hover:bg-violet-100/50 px-2.5 py-1.5 rounded-lg transition"
                        >
                          <Copy className="h-3.5 w-3.5" />
                          {copiedText === "email1" ? "Copied!" : "Copy"}
                        </button>
                      </div>
                      <div className="p-5 flex flex-col gap-3">
                        <div className="flex gap-2 items-start text-xs border-b border-slate-100 pb-2 text-slate-500">
                          <span className="font-bold w-12 shrink-0">Subject:</span>
                          <span className="text-slate-800 font-semibold">{generatedEmail.subject}</span>
                        </div>
                        <div className="text-sm text-slate-700 leading-relaxed whitespace-pre-line font-mono py-2 bg-slate-50/50 p-4 rounded-xl border border-slate-100">
                          {generatedEmail.body}
                        </div>
                      </div>
                    </div>

                    {/* Follow Up Email */}
                    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                      <div className="bg-slate-50 px-5 py-4 border-b border-slate-200 flex justify-between items-center">
                        <div className="flex items-center gap-2">
                          <span className="flex h-5 w-5 rounded-full bg-slate-600 items-center justify-center text-[10px] font-bold text-white">2</span>
                          <span className="text-sm font-semibold text-slate-800">Email #2: Dynamic Follow Up (Day 3)</span>
                        </div>
                        <button
                          onClick={() => copyToClipboard(generatedEmail.followUp, "email2")}
                          className="flex items-center gap-1.5 text-xs text-slate-700 hover:bg-slate-200/50 px-2.5 py-1.5 rounded-lg transition"
                        >
                          <Copy className="h-3.5 w-3.5" />
                          {copiedText === "email2" ? "Copied!" : "Copy"}
                        </button>
                      </div>
                      <div className="p-5 flex flex-col gap-3">
                        <div className="text-sm text-slate-700 leading-relaxed whitespace-pre-line font-mono py-2 bg-slate-50/50 p-4 rounded-xl border border-slate-100">
                          {generatedEmail.followUp}
                        </div>
                      </div>
                    </div>

                    {/* HH.ru Scraped Vacancies Results */}
                    {hhVacancies.length > 0 && (
                      <div className="bg-white border border-red-200 rounded-2xl overflow-hidden shadow-sm">
                        <div className="bg-red-50 px-5 py-3 border-b border-red-200 flex justify-between items-center">
                          <span className="text-xs font-bold text-red-900 flex items-center gap-1.5">
                            <Briefcase className="h-4 w-4 text-red-600" /> HH.ru Found Vacancies ({hhVacancies.length})
                          </span>
                        </div>
                        <div className="p-4 flex flex-col gap-3 max-h-60 overflow-y-auto">
                          {hhVacancies.map((v) => (
                            <div key={v.id} className="p-3 bg-red-50/30 rounded-xl border border-red-100 flex flex-col gap-1">
                              <div className="flex justify-between items-start">
                                <span className="font-bold text-xs text-slate-900">{v.name}</span>
                                <span className="text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-md">
                                  {v.salary?.from ? `${v.salary.from} ${v.salary.currency || "RUB"}` : "З/П не указана"}
                                </span>
                              </div>
                              <span className="text-[11px] text-slate-600">{v.employer?.name}</span>
                              {v.snippet?.requirement && (
                                <p className="text-[10px] text-slate-500 line-clamp-2 mt-1">{v.snippet.requirement}</p>
                              )}
                              <button
                                onClick={() => {
                                  setEmailForm({
                                    ...emailForm,
                                    companyName: v.employer?.name || emailForm.companyName,
                                    recipientTitle: v.name || emailForm.recipientTitle,
                                    painPoint: v.snippet?.requirement || emailForm.painPoint,
                                  });
                                }}
                                className="mt-1 self-start text-[10px] text-violet-600 font-bold hover:underline"
                              >
                                ↙️ Use this vacancy as Email target
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* DaData Enriched Company Results */}
                    {dadataResults.length > 0 && (
                      <div className="bg-white border border-blue-200 rounded-2xl overflow-hidden shadow-sm">
                        <div className="bg-blue-50 px-5 py-3 border-b border-blue-200 flex justify-between items-center">
                          <span className="text-xs font-bold text-blue-900 flex items-center gap-1.5">
                            <Building className="h-4 w-4 text-blue-600" /> DaData Verified Company Details
                          </span>
                        </div>
                        <div className="p-4 flex flex-col gap-3">
                          {dadataResults.map((c, idx) => (
                            <div key={idx} className="p-3 bg-blue-50/30 rounded-xl border border-blue-100 flex flex-col gap-1 text-xs text-slate-800">
                              <div className="font-bold text-slate-900">{c.name}</div>
                              {c.inn && <div><strong>ИНН:</strong> {c.inn} {c.ogrn ? `| ОГРН: ${c.ogrn}` : ""}</div>}
                              {c.management?.name && <div><strong>Руководитель:</strong> {c.management.name} ({c.management.post || "Директор"})</div>}
                              {c.address && <div className="text-[11px] text-slate-500"><strong>Адрес:</strong> {c.address}</div>}
                              <button
                                onClick={() => {
                                  setEmailForm({
                                    ...emailForm,
                                    companyName: c.name || emailForm.companyName,
                                    recipientName: c.management?.name || emailForm.recipientName,
                                    recipientTitle: c.management?.post || emailForm.recipientTitle,
                                  });
                                }}
                                className="mt-1 self-start text-[10px] text-violet-600 font-bold hover:underline"
                              >
                                ↙️ Fill Company & Leader into Email Form
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 3: OBJECTION HANDLING COACH */}
          {activeTab === "objection" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 flex-1 divide-y lg:divide-y-0 lg:divide-x divide-slate-200">
              
              {/* Form Panel (Left) */}
              <div className="lg:col-span-5 p-6 sm:p-8 flex flex-col gap-5 bg-slate-50/50 overflow-y-auto">
                <div>
                  <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                    <Zap className="h-5 w-5 text-amber-500" /> Objection Handler Coach
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">Get custom closing scripts and deep objection handling frameworks.</p>
                </div>

                <div className="flex flex-col gap-4">
                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-semibold text-slate-700">Tough Objection Raised</label>
                    <textarea
                      value={objectionForm.objection}
                      onChange={(e) => setObjectionForm({ ...objectionForm, objection: e.target.value })}
                      rows={3}
                      className="w-full text-sm border border-slate-200 rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-semibold text-slate-700">Your Product Value Proposition</label>
                    <textarea
                      value={objectionForm.productDesc}
                      onChange={(e) => setObjectionForm({ ...objectionForm, productDesc: e.target.value })}
                      rows={3}
                      className="w-full text-sm border border-slate-200 rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-semibold text-slate-700">Competitor Context / Current Workaround</label>
                    <input
                      type="text"
                      value={objectionForm.competitorContext}
                      onChange={(e) => setObjectionForm({ ...objectionForm, competitorContext: e.target.value })}
                      className="text-sm border border-slate-200 rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                    />
                  </div>

                  <div className="flex flex-col gap-1">
                    <label className="text-xs font-semibold text-slate-700">Objection Handling Framework</label>
                    <select
                      value={objectionForm.strategy}
                      onChange={(e) => setObjectionForm({ ...objectionForm, strategy: e.target.value })}
                      className="text-sm border border-slate-200 rounded-xl px-3.5 py-2.5 focus:outline-none focus:ring-2 focus:ring-amber-500/20 focus:border-amber-500"
                    >
                      <option value="laer">🗣️ LAER (Listen, Acknowledge, Explore, Respond)</option>
                      <option value="feel_felt_found">👥 Feel-Felt-Found (Social Proof Alignment)</option>
                      <option value="reframing">🔄 Reframing (Negatives to Positive Investments)</option>
                      <option value="case_study">📖 Case Study & Customer Narrative</option>
                    </select>
                  </div>

                  <button
                    onClick={handleObjectionSubmit}
                    disabled={objectionLoading}
                    className="w-full mt-4 bg-amber-500 hover:bg-amber-600 disabled:bg-amber-400 text-white font-semibold py-3 rounded-xl shadow-lg shadow-amber-500/10 transition flex items-center justify-center gap-2"
                  >
                    {objectionLoading ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" /> Calculating psychology...
                      </>
                    ) : (
                      <>
                        <Zap className="h-4 w-4" /> Calculate Perfect Reply
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Display Panel (Right) */}
              <div className="lg:col-span-7 p-6 sm:p-8 flex flex-col gap-6 overflow-y-auto">
                {!objectionResponse ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-center py-16 bg-slate-50/20">
                    <div className="bg-amber-50 p-4 rounded-full text-amber-500 mb-4 animate-pulse">
                      <Zap className="h-8 w-8" />
                    </div>
                    <h3 className="text-lg font-bold text-slate-900">Objection Coaching Board</h3>
                    <p className="text-slate-500 text-sm max-w-sm mt-2 leading-relaxed">
                      Enter the roadblock/objection you are facing and get specific, psych-backed sales answers.
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-6">
                    {/* Perfect Script Response */}
                    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                      <div className="bg-amber-50 px-5 py-4 border-b border-slate-200 flex justify-between items-center">
                        <span className="text-sm font-semibold text-amber-900 flex items-center gap-1.5">
                          <Sparkles className="h-4 w-4 text-amber-600 animate-spin" /> Perfect Response Script
                        </span>
                        <button
                          onClick={() => copyToClipboard(objectionResponse.suggestedResponse, "script")}
                          className="flex items-center gap-1.5 text-xs text-amber-700 hover:bg-amber-100/50 px-2.5 py-1.5 rounded-lg transition"
                        >
                          <Copy className="h-3.5 w-3.5" />
                          {copiedText === "script" ? "Copied!" : "Copy Script"}
                        </button>
                      </div>
                      <div className="p-5">
                        <p className="text-sm text-slate-800 leading-relaxed font-mono bg-amber-50/10 border border-amber-100 p-4 rounded-xl leading-relaxed whitespace-pre-wrap">
                          "{objectionResponse.suggestedResponse}"
                        </p>
                      </div>
                    </div>

                    {/* Probing Discovery Questions */}
                    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                      <div className="bg-slate-50 px-5 py-3 border-b border-slate-200">
                        <span className="text-sm font-semibold text-slate-800">Probing Discovery Questions to Ask</span>
                      </div>
                      <div className="p-5 flex flex-col gap-3">
                        {objectionResponse.probingQuestions?.map((q: string, idx: number) => (
                          <div key={idx} className="flex gap-3 items-start bg-slate-50 p-3 rounded-xl border border-slate-100">
                            <span className="flex h-5 w-5 shrink-0 bg-brand-100 border border-brand-200 text-brand-700 text-xs font-bold rounded-full items-center justify-center">
                              {idx + 1}
                            </span>
                            <span className="text-sm font-semibold text-slate-800 leading-snug">{q}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Behavioral Psychology Insights */}
                    <div className="bg-slate-50 border border-slate-200 rounded-2xl p-5 flex flex-col gap-2">
                      <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-1">
                        <Info className="h-4 w-4 text-slate-400" /> Behavioral Psychology Analysis
                      </h4>
                      <p className="text-sm text-slate-600 leading-relaxed">
                        {objectionResponse.psychologyExplanation}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* TAB 4: CALL TRANSCRIPT ANALYZER */}
          {activeTab === "transcript" && (
            <div className="grid grid-cols-1 lg:grid-cols-12 flex-1 divide-y lg:divide-y-0 lg:divide-x divide-slate-200">
              
              {/* Form Input Panel (Left) */}
              <div className="lg:col-span-5 p-6 sm:p-8 flex flex-col gap-5 bg-slate-50/50 overflow-y-auto">
                <div>
                  <h2 className="text-lg font-bold text-slate-900 flex items-center gap-2">
                    <FileText className="h-5 w-5 text-teal-500" /> Call Transcript Auditor
                  </h2>
                  <p className="text-xs text-slate-500 mt-1">Paste a full conversation or transcript to analyze rep behavior, objections, and next steps.</p>
                </div>

                <div className="flex flex-col gap-4 flex-1">
                  <div className="flex flex-col gap-1.5 flex-1">
                    <label className="text-xs font-semibold text-slate-700">Paste Dialogue Transcript</label>
                    <textarea
                      value={transcriptInput}
                      onChange={(e) => setTranscriptInput(e.target.value)}
                      rows={12}
                      className="w-full text-sm font-mono border border-slate-200 rounded-xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500 flex-1 min-h-[300px]"
                      placeholder="e.g. Rep: Hello...\nProspect: Hi..."
                    />
                  </div>

                  <button
                    onClick={handleAnalyzeTranscript}
                    disabled={transcriptLoading}
                    className="w-full mt-2 bg-teal-600 hover:bg-teal-700 disabled:bg-teal-400 text-white font-semibold py-3 rounded-xl shadow-lg shadow-teal-600/10 transition flex items-center justify-center gap-2"
                  >
                    {transcriptLoading ? (
                      <>
                        <RefreshCw className="h-4 w-4 animate-spin" /> Auditing transcript...
                      </>
                    ) : (
                      <>
                        <Sparkles className="h-4 w-4" /> Audit Conversation
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Display Panel (Right) */}
              <div className="lg:col-span-7 p-6 sm:p-8 flex flex-col gap-6 overflow-y-auto">
                {!transcriptAnalysis ? (
                  <div className="flex-1 flex flex-col items-center justify-center text-center py-16 bg-slate-50/20">
                    <div className="bg-teal-50 p-4 rounded-full text-teal-500 mb-4 animate-pulse">
                      <FileText className="h-8 w-8" />
                    </div>
                    <h3 className="text-lg font-bold text-slate-900">Conversation Evaluation Dashboard</h3>
                    <p className="text-slate-500 text-sm max-w-sm mt-2 leading-relaxed">
                      Upload your meeting transcription and run the auditor to isolate purchase signals, objection responses, and overall rep score.
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-6">
                    {/* Score and Summary banner */}
                    <div className="bg-gradient-to-br from-teal-900 to-slate-900 text-white p-5 rounded-2xl flex flex-col sm:flex-row items-center gap-5 shadow-sm">
                      <div className="h-16 w-16 rounded-full border-2 border-teal-400 bg-teal-950 flex items-center justify-center shrink-0">
                        <span className="font-extrabold text-xl">{transcriptAnalysis.repPerformanceScore}</span>
                        <span className="text-[10px] text-teal-300">/100</span>
                      </div>
                      <div className="text-center sm:text-left">
                        <h4 className="font-bold text-md text-white leading-none">Auditor Evaluation Summary</h4>
                        <p className="text-xs text-teal-100 mt-2 leading-relaxed">
                          {transcriptAnalysis.summary}
                        </p>
                      </div>
                    </div>

                    {/* Detected Objections */}
                    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                      <div className="bg-teal-50/50 px-5 py-3.5 border-b border-slate-200">
                        <span className="text-sm font-semibold text-teal-950">Detected Objections & Responses</span>
                      </div>
                      <div className="p-5 flex flex-col gap-4">
                        {transcriptAnalysis.detectedObjections && transcriptAnalysis.detectedObjections.length > 0 ? (
                          transcriptAnalysis.detectedObjections.map((obj: any, idx: number) => (
                            <div key={idx} className="border border-slate-100 rounded-xl overflow-hidden shadow-sm">
                              <div className="bg-slate-50 px-4 py-2 flex items-center justify-between border-b border-slate-100">
                                <span className="text-xs font-bold text-slate-700">Objection {idx + 1}</span>
                                <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold ${
                                  obj.handledWell ? "bg-emerald-50 text-emerald-700" : "bg-rose-50 text-rose-700"
                                }`}>
                                  {obj.handledWell ? "Handled Well" : "Needs Improvement"}
                                </span>
                              </div>
                              <div className="p-4 flex flex-col gap-2 bg-white">
                                <div className="text-sm text-slate-800 leading-snug">
                                  <strong className="text-xs text-slate-500 uppercase block tracking-wider mb-0.5">Objection Raised:</strong>
                                  "{obj.objection}"
                                </div>
                                <div className="text-sm text-slate-700 leading-snug bg-slate-50/50 p-3 rounded-lg border border-slate-100">
                                  <strong className="text-xs text-brand-600 uppercase block tracking-wider mb-0.5">Recommended Response:</strong>
                                  {obj.recommendedResponse}
                                </div>
                              </div>
                            </div>
                          ))
                        ) : (
                          <p className="text-xs text-slate-500 text-center">No explicit objections identified in the transcript.</p>
                        )}
                      </div>
                    </div>

                    {/* Purchase Signals */}
                    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                      <div className="bg-slate-50 px-5 py-3 border-b border-slate-200">
                        <span className="text-sm font-semibold text-slate-800">Key Purchase Signals Isolated</span>
                      </div>
                      <div className="p-5 flex flex-col gap-2">
                        {transcriptAnalysis.purchaseSignals?.map((sig: string, idx: number) => (
                          <div key={idx} className="flex gap-2.5 items-start text-sm text-slate-700 bg-emerald-50/30 border border-emerald-100/50 p-3 rounded-lg">
                            <span className="text-emerald-500 font-bold shrink-0">📈</span>
                            <span>{sig}</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Recommended Next Steps */}
                    <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
                      <div className="bg-slate-50 px-5 py-3 border-b border-slate-200">
                        <span className="text-sm font-semibold text-slate-800">Actionable Deal Progression Next Steps</span>
                      </div>
                      <div className="p-5 flex flex-col gap-2">
                        {transcriptAnalysis.recommendedNextSteps?.map((step: string, idx: number) => (
                          <div key={idx} className="flex gap-2.5 items-start text-sm text-slate-700 bg-slate-50 border border-slate-100 p-3 rounded-lg">
                            <span className="flex h-5 w-5 shrink-0 bg-brand-500 text-white text-[10px] font-bold rounded-full items-center justify-center mt-0.5">
                              {idx + 1}
                            </span>
                            <span>{step}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white mt-auto py-6">
        <div className="max-w-7xl mx-auto px-4 text-center text-xs text-slate-400">
          AI Sales Copilot &copy; 2026. Built with Vite, React, Express, and Google Gemini 1.5 Flash.
        </div>
      </footer>
    </div>
  );
}
