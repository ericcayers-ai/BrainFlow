import { useEffect, useId, useRef } from "react";
import {
  isFocusNavKey,
  moveFocusId,
  rovingTabIndex,
} from "../graph/focusModel";

type OutlineItem = { id: string; label: string; node_type: string; depth: number };

type Props = {
  items: OutlineItem[];
  focusId: string | null;
  onSelect: (id: string) => void;
  labelledBy?: string;
};

/**
 * Synchronized non-visual outline — mandatory a11y alternative to canvases.
 * Roving tabindex + arrow keys; selection syncs with graph focus.
 */
export default function GraphOutline({ items, focusId, onSelect, labelledBy }: Props) {
  const listId = useId();
  const itemRefs = useRef<Map<string, HTMLButtonElement>>(new Map());

  useEffect(() => {
    if (!focusId) return;
    itemRefs.current.get(focusId)?.focus({ preventScroll: false });
  }, [focusId]);

  return (
    <div
      className="graph-outline"
      role="navigation"
      aria-labelledby={labelledBy}
      aria-describedby={`${listId}-help`}
    >
      <h3 id={`${listId}-title`}>Outline</h3>
      <p id={`${listId}-help`} className="outline-help">
        Arrow keys move focus; Enter or Space selects. Mandatory alternate to the canvas.
      </p>
      <ul
        className="outline-list"
        role="listbox"
        aria-labelledby={`${listId}-title`}
        aria-activedescendant={focusId ? `${listId}-${focusId}` : undefined}
      >
        {items.length === 0 ? (
          <li className="muted" role="option" aria-disabled="true">
            No nodes
          </li>
        ) : null}
        {items.map((item) => (
          <li key={item.id} style={{ paddingLeft: `${item.depth * 0.75}rem` }} role="presentation">
            <button
              id={`${listId}-${item.id}`}
              ref={(el) => {
                if (el) itemRefs.current.set(item.id, el);
                else itemRefs.current.delete(item.id);
              }}
              type="button"
              role="option"
              className={focusId === item.id ? "outline-item active" : "outline-item"}
              aria-selected={focusId === item.id}
              aria-current={focusId === item.id ? "true" : undefined}
              tabIndex={rovingTabIndex(items, item.id, focusId)}
              onClick={() => onSelect(item.id)}
              onKeyDown={(e) => {
                if (isFocusNavKey(e.key)) {
                  e.preventDefault();
                  const next = moveFocusId(items, focusId ?? item.id, e.key);
                  if (next) onSelect(next);
                  return;
                }
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelect(item.id);
                }
              }}
            >
              <span className="outline-type">{item.node_type}</span>
              {item.label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
