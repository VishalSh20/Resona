export const LANDING_COPY = {
  nav: {
    links: [
      { label: "Product", href: "#evaluate" },
      { label: "Evaluations", href: "#evidence" },
      { label: "How it works", href: "#how-it-works" },
    ],
    signIn: "Sign in",
    start: "Start evaluating",
  },

  hero: {
    headlinePrefix: "Make your",
    headlineEmphasis: "Voice agent",
    headlineAccent: "earn your trust.",
    description:
      "Simulate real conversations. Measure what matters. Ship voice agents with confidence.",
    primaryCta: "Start evaluating",
    secondaryCta: "See how it works",
    signal: "Simulation → Evaluation → Evidence",
    scrollHint: "scroll to explore",
  },

  evaluation: {
    eyebrow: "EVALUATION",
    heading: "Evaluate how your agents actually behave.",
    body: "Go beyond a single quality score. Resona evaluates the conversations that matter — from response quality and task completion to latency, interruptions, language and groundedness.",
  },

  score: {
    eyebrow: "EVIDENCE",
    heading: "Every score should have a reason.",
    body: "A number without context is just a number. Resona connects evaluation results back to the conversation that produced them.",
    metricName: "Relevancy",
    metricValue: 96,
    checks: [
      "Directly addressed the user's request",
      "Followed the cancellation flow",
      "No irrelevant information",
    ],
    viewEvidence: "View evidence",
    callLabel: "Call #382",
    callerLabel: "Caller",
    callerLine: "“I need to cancel my order…”",
    agentLabel: "Agent",
    agentLine: "“Absolutely, I can help you with that…”",
    audioLabel: "Audio",
    evaluationLabel: "Evaluation",
    reasoningLabel: "Reasoning",
    reasoning:
      "“Response directly addressed the request and followed the cancellation flow.”",
  },

  language: {
    eyebrow: "LANGUAGE",
    lead: "Your users don't speak textbook English.",
    serif: "Neither should your evaluations.",
    heading: "Test language understanding the way people actually speak.",
    body: "Evaluate language understanding, code-switching, semantic preservation and language consistency across the languages your callers actually use.",
  },

  simulation: {
    eyebrow: "SIMULATION",
    lead: "Don't test one user.",
    serif: "Test the users you haven't met yet.",
    body: "Resona creates simulated callers with different goals, personalities, language patterns and call environments — so your agent faces more than the happy path.",
    dimensions: "Simulation dimensions",
    personaLabel: "Personas",
    traitLabel: "Traits",
    ambienceLabel: "Call ambience",
    scenarioLabel: "Scenario / goal",
    scenarioExample:
      "Cancel an order, request a refund, resolve a billing dispute…",
  },

  edge: {
    eyebrow: "EDGE CASES",
    heading: "The happy path isn't the test.",
    body: "Real conversations interrupt, change direction, switch languages and go off-script. Your evaluations should too.",
  },

  version: {
    eyebrow: "VERSION COMPARISON",
    lead: "Your agent changed.",
    serif: "Did it actually get better?",
    body: "Compare evaluation results across agent versions and runs — the same suite, the same metrics, side by side.",
    summaryImproved: "metrics improved",
    summaryRegressed: "metric regressed",
    overall: "Overall assessment",
  },

  coverage: {
    eyebrow: "COVERAGE",
    heading: "Coverage doesn't mean quality.",
    body: "Running more conversations doesn't automatically make an evaluation better. What matters is whether the evaluation covers the behaviors that actually matter.",
    coverageLabel: "Evaluation coverage",
    evidenceLabel: "Evidence",
    confidenceLabel: "Confidence",
    objectiveTitle: "Objective signals",
    objectiveBody: "Use objective signals wherever possible.",
    judgmentTitle: "Model judgment",
    judgmentBody: "Use model-based judgment where interpretation is required.",
  },

  provenance: {
    eyebrow: "PROVENANCE",
    heading: "Know where every score came from.",
    body: "Every evaluation should be traceable from result to conversation — with the underlying transcript, audio and evaluator reasoning available as evidence.",
  },

  providers: {
    eyebrow: "INTEGRATIONS",
    heading: "Bring your agent. Keep your stack.",
    body: "Evaluate the voice agents you're already building.",
  },

  cta: {
    lead: "Stop hoping your agent works.",
    serif: "Start measuring it.",
    body: "Turn conversations into evidence with Resona.",
    cta: "Start evaluating",
  },
} as const;
