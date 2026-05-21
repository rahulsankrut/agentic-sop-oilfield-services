/**
 * agentStudio.ts
 *
 * Beat-by-beat storyboard for Persona 5 (Rafael, Citizen Developer) — the
 * Agent Studio scenario. Rafael drops a new "long-deployment alert" skill
 * onto his canvas in low-code, binds an input parameter to the ZHR
 * workforce table, runs a test, and publishes the skill to his team's
 * Gemini Enterprise app.
 *
 * Like Priya's deep-research scenario, Rafael's view has its own state
 * shape because the spatial-canvas ScenarioState from ``demoScenarios.ts``
 * doesn't fit. The Agent Studio is a 2-column builder — visual skill
 * blocks on the left, code preview on the right — with a test-results
 * list and a publish-confirmation card.
 *
 * Target wall-clock: 2 minutes (5 beats × ~25s each).
 */

// ---------------------------------------------------------------------------
// Public types
// ---------------------------------------------------------------------------

/**
 * A single visual block in the skill builder. Blocks chain top-to-bottom
 * in the left pane; the connector arrows are drawn purely from ordering.
 */
export interface SkillBlock {
  /** Stable id for React keys. */
  id: string;
  /** Block kind — drives the badge color and icon. */
  kind: "input" | "query" | "filter" | "output";
  /** Bold title on the block, e.g. "Basin filter". */
  title: string;
  /** Subtitle / description, e.g. "ZHR_WORKFORCE.BASIN". */
  detail: string;
  /**
   * Optional parameter the block exposes to the user. When set, the page
   * renders a small inline pill ("Permian"). v1 is read-only.
   */
  parameterValue?: string;
  /** True once the block has been bound to a concrete data source. */
  bound?: boolean;
}

export interface AgentStudioState {
  /** Display name of the in-progress skill. */
  skillName: string;
  /** The skill's visual blocks (empty in Beat 0). */
  blocks: SkillBlock[];
  /** Test-run results — each string is one line in the result list. */
  testResults: string[];
  /** Confirmation message once published. Null until Beat 4. */
  publishStatus: string | null;
  /**
   * Read-only code preview emitted by the studio. Updates as blocks are
   * added / bound; cleared in Beat 0.
   */
  codePreview: string;
}

export interface Beat {
  id: string;
  narration: string;
  state: AgentStudioState;
}

// ---------------------------------------------------------------------------
// Constants — the canonical skill blocks Rafael composes
// ---------------------------------------------------------------------------

const BLOCKS_SCAFFOLD: SkillBlock[] = [
  {
    id: "block-input",
    kind: "input",
    title: "Basin filter",
    detail: "ZHR_WORKFORCE.BASIN",
  },
  {
    id: "block-query",
    kind: "query",
    title: "Query Maximo workforce deployment",
    detail: "maximo.workforce_deployment",
  },
  {
    id: "block-filter",
    kind: "filter",
    title: "Filter: days deployed > 21",
    detail: "deployment_days > 21",
  },
  {
    id: "block-output",
    kind: "output",
    title: "Alert list",
    detail: "Send to Rafael · email · daily digest",
  },
];

const BLOCKS_BOUND: SkillBlock[] = BLOCKS_SCAFFOLD.map((b) =>
  b.kind === "input"
    ? { ...b, parameterValue: "Permian", bound: true }
    : b,
);

const SKILL_NAME = "long_deployment_alert";

const TEST_RESULTS = [
  "Crew-PRM-014 · deployed 24 days · Midland field",
  "Crew-PRM-007 · deployed 22 days · Reagan County",
  "Crew-PRM-019 · deployed 23 days · Howard County",
];

const PUBLISH_STATUS =
  "Skill published as `permian-long-deployment-alert@v1`. Available to your team's Gemini Enterprise app. Auto-runs every Monday 9am.";

// Code preview snapshots — three stages that match the block buildout.
const CODE_PREVIEW_SCAFFOLD = `# long_deployment_alert.skill.yaml
name: long_deployment_alert
trigger: on_demand
inputs:
  - basin: string
steps:
  - query: maximo.workforce_deployment
  - filter: deployment_days > 21
  - output: alert_list`;

const CODE_PREVIEW_BOUND = `# long_deployment_alert.skill.yaml
name: long_deployment_alert
trigger: on_demand
inputs:
  - basin:
      type: string
      bound_to: ZHR_WORKFORCE.BASIN
      default: Permian
steps:
  - query: maximo.workforce_deployment
    where: basin == \${inputs.basin}
  - filter: deployment_days > 21
  - output: alert_list`;

const CODE_PREVIEW_PUBLISHED = `# Published v1 · permian-long-deployment-alert
name: long_deployment_alert
trigger:
  schedule: "0 9 * * MON"
  on_demand: true
inputs:
  - basin:
      type: string
      bound_to: ZHR_WORKFORCE.BASIN
      default: Permian
steps:
  - query: maximo.workforce_deployment
    where: basin == \${inputs.basin}
  - filter: deployment_days > 21
  - output: alert_list
audience: rafael.team@demo-major.com`;

// ---------------------------------------------------------------------------
// The five beats (0 through 4)
// ---------------------------------------------------------------------------

export const agentStudioBeats: Beat[] = [
  // ---- Beat 0: Rafael's prompt, empty studio ----
  {
    id: "beat-0-prompt",
    narration:
      "Rafael is the citizen developer. He just asked Agent Studio to scaffold a custom alert — anything over 21 continuous deployment days. The studio is empty for a beat while Gemini parses the intent.",
    state: {
      skillName: "",
      blocks: [],
      testResults: [],
      publishStatus: null,
      codePreview: "",
    },
  },

  // ---- Beat 1: skill scaffold ----
  {
    id: "beat-1-scaffold",
    narration:
      "The studio drops in the four blocks — input, query, filter, output. Rafael did not write a line of code; the LLM picked the right Maximo table and the right field name from the catalog.",
    state: {
      skillName: SKILL_NAME,
      blocks: BLOCKS_SCAFFOLD,
      testResults: [],
      publishStatus: null,
      codePreview: CODE_PREVIEW_SCAFFOLD,
    },
  },

  // ---- Beat 2: parameter binding ----
  {
    id: "beat-2-binding",
    narration:
      "Rafael clicks the basin-filter input and binds it to ZHR_WORKFORCE.BASIN. Default value: Permian. The code preview updates inline — that's what gets versioned and shipped.",
    state: {
      skillName: SKILL_NAME,
      blocks: BLOCKS_BOUND,
      testResults: [],
      publishStatus: null,
      codePreview: CODE_PREVIEW_BOUND,
    },
  },

  // ---- Beat 3: test run with three hits ----
  {
    id: "beat-3-test-run",
    narration:
      "He runs it once against today's snapshot. Three crews trip the threshold — PRM-014, PRM-007, PRM-019. The output looks right; Rafael is ready to publish.",
    state: {
      skillName: SKILL_NAME,
      blocks: BLOCKS_BOUND,
      testResults: TEST_RESULTS,
      publishStatus: null,
      codePreview: CODE_PREVIEW_BOUND,
    },
  },

  // ---- Beat 4: publish confirmation ----
  {
    id: "beat-4-published",
    narration:
      "Publish. The skill is versioned v1 and pinned to his team's Gemini Enterprise app. Auto-runs every Monday at 9. From idea to live skill, in under two minutes.",
    state: {
      skillName: SKILL_NAME,
      blocks: BLOCKS_BOUND,
      testResults: TEST_RESULTS,
      publishStatus: PUBLISH_STATUS,
      codePreview: CODE_PREVIEW_PUBLISHED,
    },
  },
];
