/**
 * Persona presets change terminology, starter templates, default artifacts,
 * and explanation depth — not core capabilities (see docs/UX_PRINCIPLES.md).
 */

export type PersonaId =
  | "student"
  | "researcher"
  | "educator"
  | "pm"
  | "ops"
  | "engineer"
  | "analyst"
  | "creative";

export interface PersonaPreset {
  id: PersonaId;
  label: string;
  /** Friendly synonym for “workflow” in Guided chrome */
  workflowTerm: string;
  /** Friendly synonym for “artifact” */
  artifactTerm: string;
  explanationDepth: "plain" | "balanced" | "technical";
  defaultGoalPrompt: string;
  starterNoteBody: string;
  defaultArtifacts: string[];
  templateIds: string[];
}

export const PERSONAS: PersonaPreset[] = [
  {
    id: "student",
    label: "Student",
    workflowTerm: "study plan",
    artifactTerm: "study notes",
    explanationDepth: "plain",
    defaultGoalPrompt:
      "Create a short study workflow that summarizes this note and writes Markdown flashcards.",
    starterNoteBody: `# Lecture capture

## Key ideas
-
## Questions
-
`,
    defaultArtifacts: ["summary.md", "flashcards.md"],
    templateIds: ["study.summary", "study.flashcards"],
  },
  {
    id: "researcher",
    label: "Researcher",
    workflowTerm: "synthesis pipeline",
    artifactTerm: "evidence memo",
    explanationDepth: "technical",
    defaultGoalPrompt:
      "Synthesize claims from this note into a literature-style memo with provenance placeholders.",
    starterNoteBody: `# Research notebook

## Sources
-
## Claims
-
## Open questions
-
`,
    defaultArtifacts: ["synthesis.md", "bib.md"],
    templateIds: ["research.synthesis", "research.contradictions"],
  },
  {
    id: "educator",
    label: "Educator",
    workflowTerm: "lesson design",
    artifactTerm: "lesson plan",
    explanationDepth: "balanced",
    defaultGoalPrompt:
      "Turn this note into a lesson plan with objectives, activities, and assessment checkpoints.",
    starterNoteBody: `# Course unit

## Learning objectives
-
## Materials
-
`,
    defaultArtifacts: ["lesson-plan.md", "rubric.md"],
    templateIds: ["teach.lesson", "teach.rubric"],
  },
  {
    id: "pm",
    label: "Project manager",
    workflowTerm: "delivery plan",
    artifactTerm: "project brief",
    explanationDepth: "balanced",
    defaultGoalPrompt:
      "Produce a project plan with milestones, risks, and a decision log from this brief.",
    starterNoteBody: `# Project brief

## Outcome
-
## Constraints
-
## Stakeholders
-
`,
    defaultArtifacts: ["plan.md", "risks.md", "decisions.md"],
    templateIds: ["pm.plan", "pm.risks"],
  },
  {
    id: "ops",
    label: "Operations",
    workflowTerm: "SOP draft",
    artifactTerm: "runbook",
    explanationDepth: "balanced",
    defaultGoalPrompt:
      "Draft an operations runbook with checklists and escalation paths from this note.",
    starterNoteBody: `# Process notes

## Trigger
-
## Steps
-
## Escalation
-
`,
    defaultArtifacts: ["runbook.md", "checklist.md"],
    templateIds: ["ops.sop", "ops.checklist"],
  },
  {
    id: "engineer",
    label: "Engineer",
    workflowTerm: "tech plan",
    artifactTerm: "design note",
    explanationDepth: "technical",
    defaultGoalPrompt:
      "Turn this note into an implementation plan with tasks, interfaces, and test gates.",
    starterNoteBody: `# Spec scratchpad

## Problem
-
## Constraints
-
## Interfaces
-
`,
    defaultArtifacts: ["design.md", "tasks.md"],
    templateIds: ["eng.design", "eng.tasks"],
  },
  {
    id: "analyst",
    label: "Analyst",
    workflowTerm: "analysis pipeline",
    artifactTerm: "report",
    explanationDepth: "technical",
    defaultGoalPrompt:
      "Structure an analysis report with hypotheses, metrics, and findings from this note.",
    starterNoteBody: `# Analysis brief

## Question
-
## Data
-
## Metrics
-
`,
    defaultArtifacts: ["report.md", "metrics.md"],
    templateIds: ["analyst.report", "analyst.metrics"],
  },
  {
    id: "creative",
    label: "Creative",
    workflowTerm: "creative board",
    artifactTerm: "draft",
    explanationDepth: "plain",
    defaultGoalPrompt:
      "Expand this note into a creative outline with variations and a short first draft.",
    starterNoteBody: `# Creative seed

## Mood
-
## Audience
-
## Constraints
-
`,
    defaultArtifacts: ["outline.md", "draft.md"],
    templateIds: ["creative.outline", "creative.draft"],
  },
];

export function personaById(id: PersonaId): PersonaPreset {
  return PERSONAS.find((p) => p.id === id) ?? PERSONAS[0];
}
