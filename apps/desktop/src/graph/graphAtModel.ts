/**
 * Assistive-tech / keyboard helpers for GraphOutline (ACCESSIBILITY.md §6.1).
 * Pure functions — unit-tested; UI wires these for live regions + focus.
 */

import type { OutlineItem, ViewKind } from "./model.ts";
import type { PathTrace } from "./pathTracing.ts";
import { indexOfFocus, moveFocusId, rovingTabIndex } from "./focusModel.ts";

export type LiveRegionPoliteness = "polite" | "assertive";

export type OutlineAnnounce = {
  text: string;
  politeness: LiveRegionPoliteness;
};

/** Accessible name: type + label (NVDA/keyboard twin wording). */
export function outlineAccessibleName(item: OutlineItem): string {
  return `${item.node_type}: ${item.label}`;
}

/** Live-region text when outline selection changes (step 3–4). */
export function announceOutlineSelection(
  items: OutlineItem[],
  focusId: string | null,
): OutlineAnnounce | null {
  if (!items.length) {
    return { text: "Outline empty", politeness: "polite" };
  }
  const idx = indexOfFocus(items, focusId);
  const item = items[idx];
  if (!item) return null;
  return {
    text: `${outlineAccessibleName(item)}, ${idx + 1} of ${items.length}`,
    politeness: "polite",
  };
}

/** Enter activates selection — assertive for confirmation (step 4). */
export function announceOutlineActivate(item: OutlineItem): OutlineAnnounce {
  return {
    text: `Selected ${outlineAccessibleName(item)}`,
    politeness: "assertive",
  };
}

/** Path status for live region (step 5). */
export function announcePathStatus(trace: PathTrace, fromId: string, toId: string): OutlineAnnounce {
  if (!trace.found) {
    return {
      text: `No path from ${fromId} to ${toId}`,
      politeness: "polite",
    };
  }
  return {
    text: `Path ${trace.nodeIds.length} nodes, ${trace.edgeIds.length} edges`,
    politeness: "polite",
  };
}

/**
 * Only one outline item is in tab order (roving tabindex) — §6.1 step 2.
 */
export function assertSingleTabStop(
  items: OutlineItem[],
  focusId: string | null,
): { ok: true } | { ok: false; error: string } {
  if (!items.length) return { ok: true };
  const activeId = items[indexOfFocus(items, focusId)]!.id;
  const zeros = items.filter((it) => rovingTabIndex(items, it.id, focusId) === 0);
  if (zeros.length !== 1) {
    return { ok: false, error: `expected 1 tab stop, got ${zeros.length}` };
  }
  if (zeros[0]!.id !== activeId) {
    return { ok: false, error: `tab stop ${zeros[0]!.id} != focus ${activeId}` };
  }
  return { ok: true };
}

/** Simulate a sequence of outline nav keys; returns final focus id. */
export function runOutlineKeySequence(
  items: OutlineItem[],
  startId: string | null,
  keys: string[],
): string | null {
  let focus = startId;
  for (const key of keys) {
    if (key === "Enter" || key === "Escape") continue;
    focus = moveFocusId(items, focus, key);
  }
  return focus;
}

/**
 * Canvas application region must not trap: Escape / Tab leave application
 * (§6.1 step 7 model). Pure check: Escape is a leave key; Tab is never a
 * focus-model key for the canvas app role.
 */
export function isCanvasLeaveKey(key: string): boolean {
  return key === "Escape" || key === "Tab";
}

/** Outline remains the twin across view switches (step 6). */
export function outlineIdsForView(outline: OutlineItem[]): string[] {
  return outline.map((o) => o.id);
}

export function outlinesInSync(a: OutlineItem[], b: OutlineItem[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((item, i) => item.id === b[i]!.id && item.label === b[i]!.label);
}

export const GRAPH_AT_VIEWS: ViewKind[] = [
  "workflow_dag",
  "mind_map",
  "tree_outline",
  "knowledge",
  "lineage",
];
