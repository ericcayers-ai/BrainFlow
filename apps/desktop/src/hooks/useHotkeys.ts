import { useEffect } from "react";
import type { CommandId } from "../commands";

function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return target.isContentEditable;
}

/**
 * Chord map for main actions. Palette (Ctrl+K) always wins even in inputs;
 * other chords skip when typing in editable fields unless explicitly allowed.
 */
export function useHotkeys(
  handlers: Partial<Record<CommandId, () => void>>,
  enabled = true,
): void {
  useEffect(() => {
    if (!enabled) return;

    function onKeyDown(e: KeyboardEvent) {
      const mod = e.ctrlKey || e.metaKey;
      if (!mod) return;

      const key = e.key.toLowerCase();
      const shift = e.shiftKey;

      let id: CommandId | null = null;
      if (key === "k" && !shift) id = "palette.open";
      else if (key === "p" && !shift) id = "note.switcher";
      else if (key === "f" && shift) id = "note.search";
      else if (key === "o" && !shift) id = "vault.open";
      else if (key === "s" && !shift) id = "note.save";
      else if (key === "enter" && !shift) id = "workflow.generate";
      else if (key === "m" && shift) id = "mode.toggle";
      else if (key === "l" && shift) id = "llm.refresh";
      else if (key === "e" && shift) id = "export.publishStub";
      else if (key === "1" && !shift) id = "view.workflow";
      else if (key === "2" && !shift) id = "view.notes";
      else if (key === "3" && !shift) id = "view.tools";

      if (!id) return;
      if (
        id !== "palette.open" &&
        isEditableTarget(e.target) &&
        id !== "note.save" &&
        id !== "workflow.generate" &&
        id !== "note.switcher" &&
        id !== "note.search" &&
        id !== "view.workflow" &&
        id !== "view.notes" &&
        id !== "view.tools"
      ) {
        return;
      }

      const handler = handlers[id];
      if (!handler) return;
      e.preventDefault();
      handler();
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handlers, enabled]);
}
