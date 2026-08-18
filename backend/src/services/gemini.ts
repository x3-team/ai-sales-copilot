import { GoogleGenerativeAI } from "@google/generative-ai";
import * as dotenv from "dotenv";

dotenv.config();

// Try to grab the API key from common environment variables
const apiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY || "";

let genAI: GoogleGenerativeAI | null = null;

if (apiKey) {
  try {
    genAI = new GoogleGenerativeAI(apiKey);
    console.log("Successfully initialized Google Generative AI (Gemini SDK)");
  } catch (error) {
    console.error("Failed to initialize Google Generative AI SDK:", error);
  }
} else {
  console.warn(
    "WARNING: Neither GEMINI_API_KEY nor GOOGLE_API_KEY environment variables are set. " +
    "The application will run in Simulated Demo Mode. " +
    "Please add your key in the Cursor Dashboard (Cloud Agents > Secrets) or a .env file."
  );
}

/**
 * Check if the Gemini API is configured
 */
export function isGeminiConfigured(): boolean {
  return genAI !== null && apiKey !== "";
}

/**
 * Returns the Gemini model instance or throws an error if not configured
 */
function getModel(modelName: string = "gemini-1.5-flash") {
  if (!genAI) {
    throw new Error("Gemini API is not configured. Please set your API key in the environment variables.");
  }
  return genAI.getGenerativeModel({ model: modelName });
}

/**
 * Roleplay System Prompts
 */
const BUYER_PERSONAS: Record<string, { name: string; title: string; behavior: string; backdrop: string }> = {
  skeptical_cfo: {
    name: "Harold Vance",
    title: "Chief Financial Officer (CFO)",
    backdrop: "Harold is extremely budget-conscious, laser-focused on ROI, and skeptical of new software tools. He hates buzzwords and wants hard numbers, clear payback periods (ideally < 6 months), and proof of cost reduction.",
    behavior: "Short, direct, challenging, demands metrics and logic. Easily annoyed by generic sales pitches."
  },
  busy_cto: {
    name: "Sarah Jenkins",
    title: "Chief Technology Officer (CTO)",
    backdrop: "Sarah's team is already over-allocated. She is highly technical, cares about API stability, security, vendor lock-in, deployment friction, and integration with their current stack (AWS, Kubernetes, PostgreSQL). She is very busy and has zero patience for non-technical sales pitches.",
    behavior: "Direct, technical, questioning engineering trade-offs, security, and onboarding time. She is impatient but will listen to elegant solutions."
  },
  curious_pm: {
    name: "Elena Rostova",
    title: "Head of Product Management",
    backdrop: "Elena wants to improve user retention, accelerate product delivery, and streamline internal workflows. She is open to innovation but wants to know how this will make her product better, how it impacts the end-user experience, and how much team training is required.",
    behavior: "Engaging, focused on features, UX, product metrics (NPS, active users), collaboration, and ease of adoption. Friendly but thorough."
  }
};

/**
 * Starts a roleplay session with introductory message from the buyer
 */
export async function startRoleplay(personaKey: string, productDescription: string, salesRepGoal: string): Promise<{
  buyerMessage: string;
  history: Array<{ role: "user" | "model"; parts: { text: string }[] }>;
}> {
  const persona = BUYER_PERSONAS[personaKey] || BUYER_PERSONAS.curious_pm;
  
  if (!isGeminiConfigured()) {
    // Return simulated/fallback start
    return {
      buyerMessage: `[SIMULATED DEMO - API KEY NOT CONFIGURED]\n\nHello, I'm ${persona.name}, the ${persona.title}. I understand you wanted to talk to me about your product. Can you briefly tell me what your tool does and why I should care? Keep in mind, I'm ${persona.behavior.toLowerCase()}`,
      history: [
        {
          role: "model",
          parts: [{ text: `[SIMULATED DEMO] Hello, I'm ${persona.name}, the ${persona.title}.` }]
        }
      ]
    };
  }

  const model = getModel("gemini-1.5-flash");

  const systemInstruction = `
    You are a professional B2B buyer participating in a sales roleplay with a sales representative.
    Your name is ${persona.name} and your job title is ${persona.title}.
    
    CONTEXT & PERSONALITY:
    ${persona.backdrop}
    
    YOUR BEHAVIOR IN CONVERSATION:
    ${persona.behavior}
    
    THE PRODUCT THEY ARE SELLING:
    ${productDescription}
    
    THE SALES REP's GOAL FOR THIS CALL:
    ${salesRepGoal}

    INSTRUCTIONS:
    1. Stay in character at all times. Never break character or refer to yourself as an AI.
    2. Give realistic, concise answers typical of a busy executive (usually 1-3 sentences, occasionally 4 if explaining a deep objection).
    3. Respond naturally to the sales rep's questions, objections, and pitch.
    4. Start the conversation from your perspective as the buyer. Do not be overly aggressive immediately, but bring up realistic objections as the rep pitches.
    5. Start with a brief, natural greeting and a first question to get the conversation going.
  `;

  // Start chat session with system instruction
  const chat = model.startChat({
    history: [],
    generationConfig: {
      temperature: 0.7,
      maxOutputTokens: 300,
    },
  });

  // Since we want the buyer to initiate, we send a prompt to generate the first response in character.
  const prompt = `${systemInstruction}\n\nInitiate the meeting as ${persona.name} (${persona.title}). Welcome the sales rep and ask your opening question to start the sales pitch. Make it sound like we just hopped on a Zoom/Google Meet call.`;
  
  const result = await chat.sendMessage(prompt);
  const responseText = result.response.text();

  // Return the introductory buyer message and setup history
  return {
    buyerMessage: responseText,
    history: [
      { role: "user", parts: [{ text: "Rep joined the meeting." }] },
      { role: "model", parts: [{ text: responseText }] }
    ]
  };
}

/**
 * Sends a message from the sales rep to the simulated buyer and gets a response
 */
export async function continueRoleplay(
  personaKey: string,
  productDescription: string,
  salesRepGoal: string,
  history: Array<{ role: "user" | "model"; parts: { text: string }[] }>,
  newMessage: string
): Promise<{
  buyerMessage: string;
  history: Array<{ role: "user" | "model"; parts: { text: string }[] }>;
}> {
  const persona = BUYER_PERSONAS[personaKey] || BUYER_PERSONAS.curious_pm;

  if (!isGeminiConfigured()) {
    const demoResponses: Record<string, string[]> = {
      skeptical_cfo: [
        "That sounds like an interesting tool, but what is the exact ROI? How quickly does it pay for itself?",
        "We have a strict budget freeze right now. Why shouldn't we just wait until next year?",
        "How much is this going to cost us upfront? I need concrete numbers, not vague pricing ranges."
      ],
      busy_cto: [
        "What does the integration process look like? My engineers don't have time to write 500 lines of custom code.",
        "How do you handle security and data privacy? Are you SOC2 compliant?",
        "I need to know about system latency and uptime SLA. What happens if your servers go down?"
      ],
      curious_pm: [
        "How is this different from competitor X? They seem to have a very similar feature set.",
        "How long does it take for a team to get onboarded and active? If adoption is slow, the project will die.",
        "Can you show me how this improves our daily workflow? What is the user feedback so far?"
      ]
    };
    
    const responses = demoResponses[personaKey] || demoResponses.curious_pm;
    const randomIndex = Math.floor(Math.random() * responses.length);
    const demoResponse = `[SIMULATED DEMO] ${responses[randomIndex]}`;

    const updatedHistory = [
      ...history,
      { role: "user" as const, parts: [{ text: newMessage }] },
      { role: "model" as const, parts: [{ text: demoResponse }] }
    ];

    return {
      buyerMessage: demoResponse,
      history: updatedHistory
    };
  }

  const model = getModel("gemini-1.5-flash");
  const systemInstruction = `
    You are ${persona.name}, the ${persona.title}.
    
    CONTEXT & PERSONALITY:
    ${persona.backdrop}
    
    YOUR BEHAVIOR IN CONVERSATION:
    ${persona.behavior}
    
    THE PRODUCT BEING SOLD:
    ${productDescription}
    
    THE SALES REP's GOAL FOR THIS CALL:
    ${salesRepGoal}

    INSTRUCTIONS:
    1. Continue playing the role of ${persona.name} flawlessly.
    2. Respond to the sales rep's message naturally, realistically, and concisely (1-3 sentences).
    3. Push back with appropriate objections, questions, or concerns based on your character.
    4. Do not offer a 'yes' too easily. Make the rep earn the next meeting or demo by addressing your core concerns (e.g., pricing/ROI for CFO, security/onboarding for CTO, adoption/features for PM).
  `;

  const chat = model.startChat({
    history: history.map(h => ({
      role: h.role,
      parts: h.parts
    })),
    generationConfig: {
      temperature: 0.7,
      maxOutputTokens: 350,
    }
  });

  // Inject system prompt along with the message to ensure it stays in context
  const fullPrompt = `${systemInstruction}\n\nSales Rep says: "${newMessage}"`;
  const result = await chat.sendMessage(fullPrompt);
  const responseText = result.response.text();

  const updatedHistory = [
    ...history,
    { role: "user" as const, parts: [{ text: newMessage }] },
    { role: "model" as const, parts: [{ text: responseText }] }
  ];

  return {
    buyerMessage: responseText,
    history: updatedHistory
  };
}

/**
 * Evaluates the completed roleplay session
 */
export async function evaluateRoleplay(
  personaKey: string,
  productDescription: string,
  salesRepGoal: string,
  history: Array<{ role: "user" | "model"; parts: { text: string }[] }>
): Promise<{
  score: number;
  strengths: string[];
  weaknesses: string[];
  objectionHandling: string;
  nextStepsAdvice: string;
  transcriptAnalysis: string;
}> {
  const persona = BUYER_PERSONAS[personaKey] || BUYER_PERSONAS.curious_pm;

  if (!isGeminiConfigured() || history.length <= 2) {
    return {
      score: 75,
      strengths: [
        "[SIMULATED DEMO] Friendly introduction and open tone",
        "[SIMULATED DEMO] Good initial description of the product"
      ],
      weaknesses: [
        "[SIMULATED DEMO] Did not deeply uncover the CFO's ROI concerns",
        "[SIMULATED DEMO] Could have asked more discovery questions before proposing solutions"
      ],
      objectionHandling: "[SIMULATED DEMO] You responded politely to objections, but should use the LAER method (Listen, Acknowledge, Explore, Respond) to validate the buyer's anxiety, then pivot back to value.",
      nextStepsAdvice: "[SIMULATED DEMO] Secure a specific time and date for a 15-minute technical demo, instead of asking for generic 'next week' interest.",
      transcriptAnalysis: "[SIMULATED DEMO] Roleplay ended early. Add an API key from Google AI Studio to unlock full, deep behavioral analysis of your dialogue."
    };
  }

  const model = getModel("gemini-1.5-flash");

  // Format the dialogue history for the evaluation prompt
  const dialogueText = history
    .filter(h => h.parts[0]?.text !== "Rep joined the meeting.")
    .map(h => `${h.role === "user" ? "SALES REP" : persona.title} (${persona.name}): ${h.parts[0]?.text}`)
    .join("\n\n");

  const prompt = `
    You are an expert sales performance coach and trainer. Analyze the following sales roleplay transcript between a Sales Representative and ${persona.name} (${persona.title}).
    
    THE PRODUCT BEING SOLD:
    ${productDescription}
    
    THE SALES REP's GOAL:
    ${salesRepGoal}
    
    ROLEPLAY DIALOGUE:
    ${dialogueText}
    
    Evaluate the sales rep's performance and output a valid JSON object matching the schema below.
    Be objective, constructive, and highly professional.
    
    Output Format:
    You MUST respond with a single, valid JSON object containing exactly the following keys. No markdown backticks or explanation outside the JSON.
    {
      "score": <number between 0 and 100>,
      "strengths": ["strength 1", "strength 2", ...],
      "weaknesses": ["weakness 1", "weakness 2", ...],
      "objectionHandling": "Detailed analysis of how well the rep handled objections raised by the buyer, referencing specific parts of the conversation.",
      "nextStepsAdvice": "Actionable, concrete suggestions on what the rep should do next or how they could have closed the deal / secured the next meeting.",
      "transcriptAnalysis": "A high-level summary of the overall flow and psychological dynamic of the sales call."
    }
  `;

  const result = await model.generateContent(prompt);
  let responseText = result.response.text().trim();

  // Try to clean up markdown block wrappers if Gemini outputs them
  if (responseText.startsWith("```json")) {
    responseText = responseText.substring(7);
  }
  if (responseText.endsWith("```")) {
    responseText = responseText.substring(0, responseText.length - 3);
  }
  responseText = responseText.trim();

  try {
    const evaluation = JSON.parse(responseText);
    return evaluation;
  } catch (error) {
    console.error("Failed to parse Gemini evaluation JSON. Raw response was:", responseText);
    // Graceful fallback parse
    return {
      score: 80,
      strengths: ["Clear value proposition", "Polite and professional demeanor"],
      weaknesses: ["Could focus more on pain discovery rather than immediate feature pitching"],
      objectionHandling: "You acknowledged concerns, but could have explored them deeper before presenting solutions.",
      nextStepsAdvice: "Always lock down a specific calendar slot for the next session.",
      transcriptAnalysis: "Good conversation flow. The rep showed a helpful attitude, but struggled slightly with executive-level financial objections."
    };
  }
}

/**
 * Generates personalized outreach emails
 */
export async function generateEmail(params: {
  productName: string;
  productDesc: string;
  recipientName: string;
  recipientTitle: string;
  companyName: string;
  painPoint: string;
  emailGoal: string;
  tone: string;
}): Promise<{
  subject: string;
  body: string;
  followUp: string;
}> {
  if (!isGeminiConfigured()) {
    return {
      subject: `[SIMULATED DEMO] Quick question regarding ${params.painPoint || "efficiency"} at ${params.companyName || "your team"}`,
      body: `Hi ${params.recipientName || "there"},\n\nI noticed you are leading the team as ${params.recipientTitle || "Manager"} at ${params.companyName || "your company"}. Many executives in your position are struggling with ${params.painPoint || "scaling and overhead"}.\n\nWe built ${params.productName || "our solution"} specifically to help with this, allowing companies to ${params.productDesc || "streamline operations and improve results"}.\n\nI'd love to show you how this could work for ${params.companyName}. Do you have 10 minutes for a brief call next Tuesday at 2 PM?\n\nBest regards,\n[Your Name]`,
      followUp: `Hi ${params.recipientName || "there"},\n\nI wanted to follow up on my previous note. I know you're incredibly busy running the team at ${params.companyName}.\n\nGiven the recent trends, I thought this short article on solving ${params.painPoint || "efficiency issues"} might be useful to you. We've helped similar teams boost productivity by 25%.\n\nWould you be open to a quick 5-minute introductory chat?\n\nBest,\n[Your Name]`
    };
  }

  const model = getModel("gemini-1.5-flash");

  const prompt = `
    You are an elite B2B copywriter and outbound sales development expert.
    Write an incredibly compelling, highly personalized cold outreach email and a follow-up email based on the following details:
    
    - Product Name: ${params.productName}
    - Product Description: ${params.productDesc}
    - Recipient Name: ${params.recipientName}
    - Recipient Title: ${params.recipientTitle}
    - Recipient Company: ${params.companyName}
    - Primary Pain Point to Address: ${params.painPoint}
    - Goal of the Email: ${params.emailGoal}
    - Tone of Voice: ${params.tone} (e.g. professional, casual, bold, analytical)
    
    INSTRUCTIONS FOR EMAIL 1 (Outreach Email):
    1. Write a punchy, highly clickable subject line (no clickbait, make it conversational and relevant).
    2. Write a short, highly-personalized email body. Make it less than 150 words.
    3. Hook them with a line showing we understand their role/pain, describe our value proposition, and close with a low-friction call-to-action (CTA).
    
    INSTRUCTIONS FOR EMAIL 2 (Follow-up Email):
    1. Write a short follow-up email to be sent 3-4 days later. Keep it under 80 words.
    2. Focus on adding value, sharing a social proof point or a helpful perspective, and keep the CTA simple.
    
    Output Format:
    You MUST output a valid JSON object matching the schema below. Do not include markdown formatting or explanation outside the JSON.
    {
      "subject": "Email Subject Line",
      "body": "Email Body (use \\n for line breaks, end with '[Your Name]')",
      "followUp": "Follow-up Email Body (use \\n for line breaks, end with '[Your Name]')"
    }
  `;

  const result = await model.generateContent(prompt);
  let responseText = result.response.text().trim();

  if (responseText.startsWith("```json")) {
    responseText = responseText.substring(7);
  }
  if (responseText.endsWith("```")) {
    responseText = responseText.substring(0, responseText.length - 3);
  }
  responseText = responseText.trim();

  try {
    return JSON.parse(responseText);
  } catch (error) {
    console.error("Failed to parse Gemini generated email JSON. Raw response was:", responseText);
    return {
      subject: `Quick discussion on ${params.painPoint} for ${params.companyName}`,
      body: `Hi ${params.recipientName},\n\nI see you are navigating ${params.painPoint} as the ${params.recipientTitle} at ${params.companyName}. We help teams solve this with ${params.productName}.\n\nWould you be open to a 10-minute talk next week?\n\nBest,\n[Your Name]`,
      followUp: `Hi ${params.recipientName},\n\nJust following up on this. Would love to share some insights on how we help with ${params.painPoint}.\n\nBest,\n[Your Name]`
    };
  }
}

/**
 * Generates perfect responses to common sales objections
 */
export async function handleObjection(params: {
  objection: string;
  productDesc: string;
  competitorContext?: string;
  strategy: "laer" | "feel_felt_found" | "reframing" | "case_study";
}): Promise<{
  suggestedResponse: string;
  psychologyExplanation: string;
  probingQuestions: string[];
}> {
  if (!isGeminiConfigured()) {
    return {
      suggestedResponse: `[SIMULATED DEMO] I completely understand your concern regarding "${params.objection}". Many of our clients had the exact same thought initially. However, what they found was that by adopting our solution, they saved over 30% of their manual hours within the first month.`,
      psychologyExplanation: `[SIMULATED DEMO] Using the ${params.strategy.toUpperCase()} framework helps disarm the customer. You validate their initial concern (de-escalation), create alignment, and then offer a soft shift in perspective using social proof.`,
      probingQuestions: [
        `[SIMULATED DEMO] What is your current workaround for this issue?`,
        `[SIMULATED DEMO] If we could solve this, what impact would it have on your quarterly goals?`
      ]
    };
  }

  const model = getModel("gemini-1.5-flash");

  const strategyDescriptions = {
    laer: "LAER Method: Listen (actively hear their concern), Acknowledge (validate their feeling so they feel heard), Explore (ask clarifying questions to uncover the root cause), Respond (deliver a tailored value-focused resolution).",
    feel_felt_found: "Feel-Felt-Found: Empathize ('I understand how you feel'), normalize ('others have felt the same way'), and resolve with proof ('but they found that...').",
    reframing: "Reframing: Changing the focus of the objection from a negative (e.g. cost) into an investment or strategic advantage (e.g. future savings or risk mitigation).",
    case_study: "Case Study & Social Proof: Deflecting the objection by introducing a story of a similar company that overcame the same challenge with exceptional results."
  };

  const prompt = `
    You are a master sales psychologist and head of sales enablement.
    Provide a world-class response and coaching plan for handling the following sales objection:
    
    - Objection Raised: "${params.objection}"
    - Product Description: "${params.productDesc}"
    - Competitor Context (if any): "${params.competitorContext || "none"}"
    - Objection Handling Strategy: ${strategyDescriptions[params.strategy] || strategyDescriptions.laer}
    
    INSTRUCTIONS:
    1. Write a direct, highly-persuasive script for a sales rep to say to the prospect. Keep the tone natural, conversational, empathetic, and confident.
    2. Write a detailed breakdown of the behavioral psychology behind why this response works.
    3. Provide 2-3 deep, open-ended probing questions the rep should ask to explore the objection further and uncover the root problem.
    
    Output Format:
    You MUST output a valid JSON object matching the schema below. Do not include markdown formatting or explanation outside the JSON.
    {
      "suggestedResponse": "The exact script/response for the sales rep",
      "psychologyExplanation": "Coaching tips and behavioral psychology explanation",
      "probingQuestions": ["question 1", "question 2", "question 3"]
    }
  `;

  const result = await model.generateContent(prompt);
  let responseText = result.response.text().trim();

  if (responseText.startsWith("```json")) {
    responseText = responseText.substring(7);
  }
  if (responseText.endsWith("```")) {
    responseText = responseText.substring(0, responseText.length - 3);
  }
  responseText = responseText.trim();

  try {
    return JSON.parse(responseText);
  } catch (error) {
    console.error("Failed to parse objection handling JSON. Raw response was:", responseText);
    return {
      suggestedResponse: `I completely appreciate your perspective. Let's look at how we can address this for you...`,
      psychologyExplanation: "This response lowers their guard by acknowledging their worry directly.",
      probingQuestions: ["Can you tell me more about how you currently handle this?"]
    };
  }
}

/**
 * Analyzes a sales call transcript for key takeaways, objections, and next steps
 */
export async function analyzeTranscript(transcript: string): Promise<{
  summary: string;
  detectedObjections: Array<{ objection: string; timestamp?: string; handledWell: boolean; recommendedResponse: string }>;
  purchaseSignals: string[];
  recommendedNextSteps: string[];
  repPerformanceScore: number;
}> {
  if (!isGeminiConfigured() || transcript.length < 10) {
    return {
      summary: "[SIMULATED DEMO] This is a high-level summary of the sales call. To get deep insight, add a real transcript and configure your Gemini API Key.",
      detectedObjections: [
        {
          objection: "[SIMULATED DEMO] Pricing concern",
          handledWell: false,
          recommendedResponse: "[SIMULATED DEMO] Shift the focus to the cost of inaction."
        }
      ],
      purchaseSignals: ["[SIMULATED DEMO] Prospect asked about implementation timeline"],
      recommendedNextSteps: ["[SIMULATED DEMO] Send case study, schedule engineering demo"],
      repPerformanceScore: 78
    };
  }

  const model = getModel("gemini-1.5-flash");

  const prompt = `
    You are a premium sales analyst and director of sales operations.
    Analyze the following sales call transcript and extract deep sales analytics:
    
    TRANSCRIPT:
    """
    ${transcript}
    """
    
    INSTRUCTIONS:
    1. Write a highly accurate, professional summary of the conversation (max 120 words).
    2. Identify and extract any objections brought up by the prospect. For each objection, indicate whether the sales rep handled it well (boolean) and provide a recommended alternative response.
    3. List 2-4 buyer purchase signals (clues that show high interest, e.g. asking about pricing details, timeline, trial, or integration).
    4. Outline 2-3 specific, high-probability recommended next steps to progress the deal.
    5. Score the sales rep's overall performance on a scale from 0 to 100.
    
    Output Format:
    You MUST output a valid JSON object matching the schema below. Do not include markdown formatting or explanation outside the JSON.
    {
      "summary": "High-level professional summary of the sales call",
      "detectedObjections": [
        {
          "objection": "The objection raised",
          "handledWell": true,
          "recommendedResponse": "A better/alternative way to reply to this"
        }
      ],
      "purchaseSignals": ["signal 1", "signal 2", ...],
      "recommendedNextSteps": ["next step 1", "next step 2", ...],
      "repPerformanceScore": <number between 0 and 100>
    }
  `;

  const result = await model.generateContent(prompt);
  let responseText = result.response.text().trim();

  if (responseText.startsWith("```json")) {
    responseText = responseText.substring(7);
  }
  if (responseText.endsWith("```")) {
    responseText = responseText.substring(0, responseText.length - 3);
  }
  responseText = responseText.trim();

  try {
    return JSON.parse(responseText);
  } catch (error) {
    console.error("Failed to parse transcript analysis JSON. Raw response was:", responseText);
    return {
      summary: "Completed analysis of your transcript.",
      detectedObjections: [],
      purchaseSignals: ["General interest in learning more"],
      recommendedNextSteps: ["Follow up with details"],
      repPerformanceScore: 80
    };
  }
}
