import type { Turn } from "./types";

/* A real design conversation, captured once from the actual backend
 * (design_assistant.respond, with a configured Mistral provider) against
 * the real corpus. Not scripted, not written by hand — every move,
 * citation, and recommendation below is genuine model output from one
 * real session. Replayed read-only for the showcase; nothing here is
 * regenerated per visitor. */
export const DEMO_TRANSCRIPT: Turn[] = [
  {
    "turnId": "r1",
    "role": "researcher",
    "author": "Researcher",
    "text": "I think junior developers over-trust AI-generated code and accept it with less scrutiny than seniors.",
    "moves": [],
    "recommendations": []
  },
  {
    "turnId": "p1",
    "role": "platform",
    "author": "Platform",
    "text": "Let’s sharpen this intuition into a testable design. I’ll suggest a few concrete moves that keep the focus on trust-as-scrutiny while allowing you to isolate junior vs. senior behavior. Pick the ones you like and we’ll iterate.",
    "moves": [
      {
        "moveId": "t1-m1",
        "kind": "add-rq",
        "target": "protocol.research_questions",
        "proposal": "Quantify the difference in scrutiny time junior vs. senior developers allocate to AI-generated code snippets before acceptance.",
        "grounding": [
          {
            "ref": "corpus:trust-in-ai-code-generation",
            "tier": "A",
            "title": "Investigating and Designing for Trust in AI-powered Code Generation Tools",
            "year": 2023,
            "venue": "corpus (Tier A seed)",
            "why": "Trust as a measurable construct in dev-AI interaction"
          }
        ],
        "status": "proposed"
      },
      {
        "moveId": "t1-m2",
        "kind": "add-measure",
        "target": "protocol.measures.primary",
        "proposal": "Add a behavioral measure of scrutiny: dwell time on the diff view of AI-generated code before the developer accepts or rejects it.",
        "grounding": [
          {
            "ref": "corpus:grounded-copilot",
            "tier": "A",
            "title": "Grounded Copilot: How Programmers Interact with Code-Generating Models",
            "year": 2022,
            "venue": "corpus (Tier A seed)",
            "why": "Foundational acceleration-vs-exploration interaction taxonomy"
          }
        ],
        "status": "proposed"
      },
      {
        "moveId": "t1-m3",
        "kind": "add-measure",
        "target": "protocol.measures.secondary",
        "proposal": "Add a self-report measure of perceived trust in the AI snippet immediately after each acceptance/rejection.",
        "grounding": [
          {
            "ref": "corpus:trust-in-ai-code-generation",
            "tier": "A",
            "title": "Investigating and Designing for Trust in AI-powered Code Generation Tools",
            "year": 2023,
            "venue": "corpus (Tier A seed)",
            "why": "Trust as a measurable construct in dev-AI interaction"
          }
        ],
        "status": "proposed"
      },
      {
        "moveId": "t1-m4",
        "kind": "set-parameter",
        "target": "protocol.population.stratification",
        "proposal": "Stratify participants by experience: juniors (0–2 yrs) and seniors (5+ yrs), excluding intermediates to sharpen contrast.",
        "grounding": [],
        "status": "proposed"
      },
      {
        "moveId": "t1-m5",
        "kind": "choose-template",
        "target": "protocol.template",
        "proposal": "Use the observational-field-v1 template to capture real-world IDE behavior without priming participants about trust.",
        "grounding": [],
        "status": "proposed"
      },
      {
        "moveId": "t1-m6",
        "kind": "add-instrument",
        "target": "protocol.instruments.ide_plugin",
        "proposal": "Deploy a lightweight IDE plugin that logs diff-view events and injects the post-snippet trust question without disrupting workflow.",
        "grounding": [
          {
            "ref": "corpus:grounded-copilot",
            "tier": "A",
            "title": "Grounded Copilot: How Programmers Interact with Code-Generating Models",
            "year": 2022,
            "venue": "corpus (Tier A seed)",
            "why": "Foundational acceleration-vs-exploration interaction taxonomy"
          }
        ],
        "status": "proposed"
      },
      {
        "moveId": "t1-m7",
        "kind": "set-parameter",
        "target": "protocol.instruments.ide_plugin.survey",
        "proposal": "Delay the trust question by 5 seconds after the decision to reduce recency bias from the just-completed action.",
        "grounding": [],
        "status": "proposed"
      },
      {
        "moveId": "t1-m8",
        "kind": "caution",
        "target": "protocol.analysis.threats",
        "proposal": "Note that dwell time may conflate scrutiny with distraction; plan a sensitivity analysis that excludes outliers > 2 standard deviations.",
        "grounding": [],
        "status": "proposed"
      }
    ],
    "recommendations": [
      {
        "ref": "corpus:insecure-code-with-ai-assistants",
        "tier": "A",
        "title": "Do Users Write More Insecure Code with AI Assistants?",
        "year": 2022,
        "venue": "corpus",
        "matchReason": "Matches your terms: over-trust, code, than."
      },
      {
        "ref": "corpus:more-code-less-understanding",
        "tier": "A",
        "title": "More Code, Less Understanding? AI Assistants, Productivity and Code Ownership",
        "year": 2026,
        "venue": "corpus",
        "matchReason": "Matches your terms: developers, code, less."
      },
      {
        "ref": "corpus:trust-in-ai-code-generation",
        "tier": "A",
        "title": "Investigating and Designing for Trust in AI-powered Code Generation Tools",
        "year": 2023,
        "venue": "corpus",
        "matchReason": "Matches your terms: think, developers, code."
      },
      {
        "ref": "doi:10.1145/3672608.3707778",
        "tier": "B",
        "title": "My Code Is Less Secure with Gen AI: Surveying Developers' Perceptions of the Impact of Code Generation Tools on Security",
        "year": 2025,
        "venue": "ACM Symposium on Applied Computing",
        "matchReason": "Matches your terms: developers, code, less."
      },
      {
        "ref": "corpus:ai-code-authoring-at-scale",
        "tier": "A",
        "title": "AI-assisted Code Authoring at Scale (CodeCompose)",
        "year": 2023,
        "venue": "corpus",
        "matchReason": "Matches your terms: developers, code, accept."
      },
      {
        "ref": "corpus:grounded-copilot",
        "tier": "A",
        "title": "Grounded Copilot: How Programmers Interact with Code-Generating Models",
        "year": 2022,
        "venue": "corpus",
        "matchReason": "Matches your terms: code."
      },
      {
        "ref": "corpus:sharp-tools-agentic-ai",
        "tier": "A",
        "title": "Sharp Tools: How Developers Wield Agentic AI in Real SE Tasks",
        "year": 2025,
        "venue": "corpus",
        "matchReason": "Matches your terms: developers."
      },
      {
        "ref": "corpus:metr-early-2025-dev-productivity",
        "tier": "A",
        "title": "Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity",
        "year": 2025,
        "venue": "corpus",
        "matchReason": "Matches your terms: developers, code."
      }
    ],
    "source": "llm"
  },
  {
    "turnId": "r2",
    "role": "researcher",
    "author": "Researcher",
    "text": "It would be a live study with real developers using an in-IDE assistant, not a survey.",
    "moves": [],
    "recommendations": []
  },
  {
    "turnId": "p2",
    "role": "platform",
    "author": "Platform",
    "text": "Great—live, in-IDE studies with real developers give us ecological validity that surveys can’t. Let’s lock in the core design. I’ll suggest a few concrete moves to shape the protocol. Accept or reject each one individually, and we’ll iterate from there.",
    "moves": [
      {
        "moveId": "t2-m1",
        "kind": "choose-template",
        "target": "protocol.template",
        "proposal": "Adopt the METR-style RCT template for measuring real-task impact.",
        "grounding": [],
        "status": "proposed"
      },
      {
        "moveId": "t2-m2",
        "kind": "set-parameter",
        "target": "protocol.ide_integration",
        "proposal": "Instrument the IDE to log every interaction with the assistant (prompt, response, edit, acceptance/rejection).",
        "grounding": [
          {
            "ref": "corpus:programmers-assistant",
            "tier": "A",
            "title": "The Programmer's Assistant: Conversational Interaction with an LLM",
            "year": 2023,
            "venue": "corpus (Tier A seed)",
            "why": "Early conversational-assistant user study (42 participants)"
          },
          {
            "ref": "corpus:ai-code-authoring-at-scale",
            "tier": "A",
            "title": "AI-assisted Code Authoring at Scale (CodeCompose)",
            "year": 2023,
            "venue": "corpus (Tier A seed)",
            "why": "Mixed-methods evaluation of an assistant deployed to thousands of devs"
          }
        ],
        "status": "proposed"
      },
      {
        "moveId": "t2-m3",
        "kind": "add-rq",
        "target": "protocol.research_questions",
        "proposal": "Add a research question on whether developers produce more insecure code when using the assistant.",
        "grounding": [
          {
            "ref": "corpus:insecure-code-with-ai-assistants",
            "tier": "A",
            "title": "Do Users Write More Insecure Code with AI Assistants?",
            "year": 2022,
            "venue": "corpus (Tier A seed)",
            "why": "Classic controlled user study; also shows over-trust measurement"
          }
        ],
        "status": "proposed"
      },
      {
        "moveId": "t2-m4",
        "kind": "add-measure",
        "target": "protocol.measures.security",
        "proposal": "Add a static-analysis pass on every saved file to flag common vulnerabilities (OWASP Top 10).",
        "grounding": [
          {
            "ref": "corpus:insecure-code-with-ai-assistants",
            "tier": "A",
            "title": "Do Users Write More Insecure Code with AI Assistants?",
            "year": 2022,
            "venue": "corpus (Tier A seed)",
            "why": "Classic controlled user study; also shows over-trust measurement"
          }
        ],
        "status": "proposed"
      },
      {
        "moveId": "t2-m5",
        "kind": "add-instrument",
        "target": "protocol.instruments.post_task",
        "proposal": "Add a short post-task interview to capture developers’ perceived trust in the assistant’s suggestions.",
        "grounding": [
          {
            "ref": "corpus:ai-assistants-in-practice",
            "tier": "A",
            "title": "Using AI-Based Coding Assistants in Practice",
            "year": 2024,
            "venue": "corpus (Tier A seed)",
            "why": "481-developer survey of adoption per SE activity"
          }
        ],
        "status": "proposed"
      },
      {
        "moveId": "t2-m6",
        "kind": "caution",
        "target": "protocol.consent",
        "proposal": "Ensure participants know that every keystroke and edit is logged, even if they later delete it.",
        "grounding": [],
        "status": "proposed"
      }
    ],
    "recommendations": [
      {
        "ref": "corpus:sharp-tools-agentic-ai",
        "tier": "A",
        "title": "Sharp Tools: How Developers Wield Agentic AI in Real SE Tasks",
        "year": 2025,
        "venue": "corpus",
        "matchReason": "Matches your terms: real, developers, in-ide."
      },
      {
        "ref": "corpus:programmers-assistant",
        "tier": "A",
        "title": "The Programmer's Assistant: Conversational Interaction with an LLM",
        "year": 2023,
        "venue": "corpus",
        "matchReason": "Matches your terms: assistant, not."
      },
      {
        "ref": "corpus:ai-assistants-in-practice",
        "tier": "A",
        "title": "Using AI-Based Coding Assistants in Practice",
        "year": 2024,
        "venue": "corpus",
        "matchReason": "Matches your terms: assistant, not, survey."
      },
      {
        "ref": "corpus:insecure-code-with-ai-assistants",
        "tier": "A",
        "title": "Do Users Write More Insecure Code with AI Assistants?",
        "year": 2022,
        "venue": "corpus",
        "matchReason": "Matches your terms: real, assistant."
      },
      {
        "ref": "corpus:llm-code-understanding",
        "tier": "A",
        "title": "Using an LLM to Help With Code Understanding",
        "year": 2023,
        "venue": "corpus",
        "matchReason": "Matches your terms: developers, in-ide, not."
      },
      {
        "ref": "corpus:ai-code-authoring-at-scale",
        "tier": "A",
        "title": "AI-assisted Code Authoring at Scale (CodeCompose)",
        "year": 2023,
        "venue": "corpus",
        "matchReason": "Matches your terms: assistant, not."
      },
      {
        "ref": "corpus:realhumaneval",
        "tier": "A",
        "title": "The RealHumanEval: Evaluating LLMs' Abilities to Support Programmers",
        "year": 2024,
        "venue": "corpus",
        "matchReason": "Matches your terms: real."
      },
      {
        "ref": "corpus:metr-early-2025-dev-productivity",
        "tier": "A",
        "title": "Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity",
        "year": 2025,
        "venue": "corpus",
        "matchReason": "Matches your terms: real."
      }
    ],
    "source": "llm"
  },
  {
    "turnId": "r3",
    "role": "researcher",
    "author": "Researcher",
    "text": "What statistics should I use given a small sample of maybe 20 developers?",
    "moves": [],
    "recommendations": []
  },
  {
    "turnId": "p3",
    "role": "platform",
    "author": "Platform",
    "text": "With a small sample of 20 developers, you’ll need statistics that are robust to low power and non-normal distributions. Here are some concrete design moves to consider for your analysis plan:",
    "moves": [
      {
        "moveId": "t3-m1",
        "kind": "set-parameter",
        "target": "analysis.primary_statistic",
        "proposal": "Use non-parametric tests (e.g., Wilcoxon signed-rank for paired data, Mann-Whitney U for independent groups) instead of t-tests or ANOVA.",
        "grounding": [],
        "status": "proposed"
      },
      {
        "moveId": "t3-m2",
        "kind": "add-measure",
        "target": "analysis.effect_size",
        "proposal": "Report effect sizes (e.g., rank-biserial correlation for Mann-Whitney U, or standardized mean differences) alongside p-values to contextualize practical significance.",
        "grounding": [],
        "status": "proposed"
      },
      {
        "moveId": "t3-m3",
        "kind": "add-measure",
        "target": "analysis.descriptive_stats",
        "proposal": "Prioritize medians and interquartile ranges (IQRs) over means and standard deviations for central tendency and dispersion.",
        "grounding": [],
        "status": "proposed"
      },
      {
        "moveId": "t3-m4",
        "kind": "caution",
        "target": "analysis.power",
        "proposal": "Acknowledge the risk of Type II errors (false negatives) due to low statistical power, and avoid overinterpreting null results.",
        "grounding": [],
        "status": "proposed"
      },
      {
        "moveId": "t3-m5",
        "kind": "add-measure",
        "target": "analysis.qualitative_triangulation",
        "proposal": "Complement quantitative findings with qualitative data (e.g., interview quotes, think-aloud transcripts) to enrich interpretation of small-sample trends.",
        "grounding": [
          {
            "ref": "corpus:programmers-assistant",
            "tier": "A",
            "title": "The Programmer's Assistant: Conversational Interaction with an LLM",
            "year": 2023,
            "venue": "corpus (Tier A seed)",
            "why": "Early conversational-assistant user study (42 participants)"
          }
        ],
        "status": "proposed"
      },
      {
        "moveId": "t3-m6",
        "kind": "set-parameter",
        "target": "analysis.multiple_comparisons",
        "proposal": "If conducting multiple comparisons, use a correction method (e.g., Bonferroni, Holm) to control family-wise error rate.",
        "grounding": [],
        "status": "proposed"
      }
    ],
    "recommendations": [
      {
        "ref": "corpus:programmers-assistant",
        "tier": "A",
        "title": "The Programmer's Assistant: Conversational Interaction with an LLM",
        "year": 2023,
        "venue": "corpus",
        "matchReason": "Matches your terms: use."
      },
      {
        "ref": "corpus:metr-early-2025-dev-productivity",
        "tier": "A",
        "title": "Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity",
        "year": 2025,
        "venue": "corpus",
        "matchReason": "Matches your terms: small, developers."
      },
      {
        "ref": "arxiv:2507.21280",
        "tier": "B",
        "title": "\"Maybe We Need Some More Examples:\" Individual and Team Drivers of Developer GenAI Tool Use",
        "year": 2025,
        "venue": "arXiv.org",
        "matchReason": "Matches your terms: use, maybe."
      },
      {
        "ref": "arxiv:2506.05614",
        "tier": "B",
        "title": "Which Prompting Technique Should I Use? An Empirical Investigation of Prompting Techniques for Software Engineering Tasks",
        "year": 2025,
        "venue": "arXiv.org",
        "matchReason": "Matches your terms: should, use."
      },
      {
        "ref": "arxiv:2409.08775",
        "tier": "B",
        "title": "What Should We Engineer in Prompts? Training Humans in Requirement-Driven LLM Use",
        "year": 2024,
        "venue": "ACM Trans. Comput. Hum. Interact.",
        "matchReason": "Matches your terms: should, use."
      },
      {
        "ref": "doi:10.1145/3706598.3713732",
        "tier": "B",
        "title": "\"I Don't Know Why I Should Use This App\": Holistic Analysis on User Engagement Challenges in Mobile Mental Health",
        "year": 2025,
        "venue": "International Conference on Human Factors in Computing Systems",
        "matchReason": "Matches your terms: should, use."
      },
      {
        "ref": "arxiv:2512.17363",
        "tier": "B",
        "title": "What You Trust is Insecure: Demystifying How Developers (Mis)Use Trusted Execution Environments in Practice",
        "year": 2025,
        "venue": "IEEE International Conference on Software Analysis, Evolution, and Reengineering",
        "matchReason": "Matches your terms: use, developers."
      },
      {
        "ref": "corpus:trust-in-ai-code-generation",
        "tier": "A",
        "title": "Investigating and Designing for Trust in AI-powered Code Generation Tools",
        "year": 2023,
        "venue": "corpus",
        "matchReason": "Matches your terms: maybe."
      }
    ],
    "source": "llm"
  }
];
