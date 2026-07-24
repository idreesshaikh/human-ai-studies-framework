import type { DesignMove, Grounding, Recommendation, Turn } from "./types.ts";

/* The deterministic design assistant — how the platform behaves with no
 * LLM key configured.
 *
 * This is not throwaway mock data: it's the real fallback path. It maps
 * researcher input to scripted platform turns, design moves, cautions, and
 * paper recommendations. Every citation below is a real corpus paper with a
 * real reason — the assistant only ever cites papers it actually holds.
 * When the backend LLM is wired up, it swaps in behind the same return
 * shape.
 *
 * The scripts cover two showcase flows: juniors over-trusting AI code
 * (surfaces the two most relevant papers), and measuring productivity by
 * self-report alone (draws a caution grounded in the METR study). Matching
 * is keyword-based and order-stable. */

let counter = 0;
const id = (p: string) => `${p}-${++counter}`;

/** Reset the id counter so a replay from a fixed script produces identical
 * ids — used by the determinism check. */
export function resetStub() {
  counter = 0;
}

const G = {
  trust: {
    ref: "corpus:trust-in-ai-code-generation",
    title: "Trust in AI Code Generation",
    year: 2024,
    venue: "corpus",
    why: "Documents over-reliance on AI-generated code — directly motivates a trust/verification measure.",
  },
  insecure: {
    ref: "corpus:insecure-code-with-ai-assistants",
    title: "Do Users Write More Insecure Code with AI Assistants?",
    year: 2023,
    venue: "corpus",
    why: "Shows accepted AI code carries security defects users don't catch — grounds a code-correctness outcome.",
  },
  metr: {
    ref: "corpus:metr-early-2025-dev-productivity",
    title: "Measuring the Impact of Early-2025 AI on Developer Productivity",
    year: 2025,
    venue: "corpus",
    why: "Found developers FELT faster with AI while measurably slower — the perception gap that makes self-report alone unsafe.",
  },
  realhuman: {
    ref: "corpus:realhumaneval",
    title: "RealHumanEval",
    year: 2024,
    venue: "corpus",
    why: "Benchmark score is not human utility — grounds pairing any benchmark measure with a human-task outcome.",
  },
  guidelines: {
    ref: "corpus:guidelines-empirical-llm-se",
    title: "Guidelines for Empirical Studies of LLMs in SE",
    year: 2024,
    venue: "corpus",
    why: "The methodological floor: within-subjects + counterbalancing for small-N developer studies.",
  },
} satisfies Record<string, Grounding>;

function platformTurn(
  text: string,
  moves: DesignMove[] = [],
  recommendations: Recommendation[] = [],
): Turn {
  return {
    turnId: id("turn"),
    role: "platform",
    author: "Platform",
    text,
    moves,
    recommendations,
  };
}

function move(
  kind: DesignMove["kind"],
  target: string,
  proposal: string,
  patch: DesignMove["patch"],
  grounding: Grounding[],
): DesignMove {
  return {
    moveId: id("move"),
    kind,
    target,
    proposal,
    patch,
    grounding,
    status: "proposed",
  };
}

/** The opening turn shown before the researcher types anything. */
export function openingTurn(): Turn {
  return platformTurn(
    "What do you want to find out? Try: “Junior developers over-trust AI-generated code.”",
  );
}

/** Map researcher input → the platform's scripted response. Deterministic:
 * same input (lowercased, trimmed) always yields the same turn. */
export function respondTo(input: string): Turn {
  const q = input.toLowerCase();

  // The over-trust script.
  if (q.includes("trust") || q.includes("over-trust") || q.includes("junior")) {
    return platformTurn(
      "Good starting point. “Over-trust” is a claim about how developers review AI code before accepting it — measurable, not just felt. Here are moves that turn it into a study, each grounded. Two papers in the corpus match closely.",
      [
        move(
          "add-rq",
          "researchQuestions[]",
          "RQ: Do junior developers accept AI-generated code with less review than seniors?",
          { section: "researchQuestions", op: "append", value: "Do junior developers accept AI-generated code with less review than seniors?" },
          [G.trust],
        ),
        move(
          "add-measure",
          "measures[]",
          "Measure: review latency — time an AI suggestion is visible before accept/reject.",
          { section: "measures", op: "append", value: "Review latency (suggestion-visible-to-decision time)" },
          [G.trust],
        ),
        move(
          "add-measure",
          "measures[]",
          "Measure: code-correctness outcome — acceptance tests on the delivered code.",
          { section: "measures", op: "append", value: "Code-correctness outcome (acceptance-test pass rate)" },
          [G.insecure],
        ),
        move(
          "set-parameter",
          "conditions[]",
          "Between-groups factor: experience level (junior / senior).",
          { section: "conditions", op: "append", value: "Experience level: junior vs. senior" },
          [], // unsourced — the researcher's own scoping decision
        ),
      ],
      [
        {
          ref: G.trust.ref,
          title: G.trust.title,
          year: G.trust.year!,
          venue: G.trust.venue!,
          matchReason:
            "Directly studies over-reliance on AI-generated code — your exact construct.",
        },
        {
          ref: G.insecure.ref,
          title: G.insecure.title,
          year: G.insecure.year!,
          venue: G.insecure.venue!,
          matchReason:
            "Shows accepted AI code carries defects users miss — grounds the correctness outcome.",
        },
      ],
    );
  }

  // Self-report-only productivity draws the METR caution.
  if (
    (q.includes("productiv") || q.includes("faster") || q.includes("speed")) &&
    (q.includes("self-report") || q.includes("survey") || q.includes("ask") || q.includes("perceiv"))
  ) {
    return platformTurn(
      "I'd challenge measuring productivity by self-report alone. The corpus has direct evidence against it.",
      [
        move(
          "caution",
          "measures",
          "Caution: self-reported speed diverges from measured speed. Pair it with an objective task-time measure.",
          undefined, // a caution makes no draft change
          [G.metr],
        ),
        move(
          "add-measure",
          "measures[]",
          "Measure: task completion time (objective), alongside the perception item.",
          { section: "measures", op: "append", value: "Task completion time (objective)" },
          [G.metr],
        ),
      ],
    );
  }

  // Design/statistics slot.
  if (q.includes("design") || q.includes("statistic") || q.includes("test") || q.includes("how many")) {
    return platformTurn(
      "For a small-N developer study, the corpus points to a within-subjects design with task counterbalancing, and a paired non-parametric test.",
      [
        move(
          "choose-template",
          "design",
          "Design: within-subjects, counterbalanced task order.",
          { section: "design", op: "set", value: "Within-subjects, counterbalanced task order" },
          [G.guidelines],
        ),
        move(
          "set-parameter",
          "statisticalPlan",
          "Statistical plan: Wilcoxon signed-rank (exact) with matched-pairs rank-biserial effect size; small-N framed as hypothesis-generating.",
          { section: "statisticalPlan", op: "set", value: "Wilcoxon signed-rank (exact) + rank-biserial effect size; small-N = hypothesis-generating" },
          [G.guidelines],
        ),
      ],
    );
  }

  // Benchmark-only evaluation draws the RealHumanEval caution.
  if (q.includes("benchmark") || q.includes("humaneval") || q.includes("pass@")) {
    return platformTurn(
      "Benchmark score isn't human utility. If you use a benchmark, pair it with a real-task outcome.",
      [
        move(
          "caution",
          "measures",
          "Caution: a benchmark measures the model, not your participants' outcomes.",
          undefined,
          [G.realhuman],
        ),
      ],
    );
  }

  // Fallback: ask a follow-up and name the slots still empty — never silent.
  return platformTurn(
    "Tell me more so I can ground a move. What's the population, and is this live-instrumented or curated data? Right now these slots are still empty: participants, conditions, ethics posture.",
  );
}
