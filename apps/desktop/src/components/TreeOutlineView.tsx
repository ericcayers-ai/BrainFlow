import { useMemo, useRef, useEffect } from "react";
import type { GraphProjection } from "../graph/model";
import {
  isFocusNavKey,
  moveFocusId,
  rovingTabIndex,
} from "../graph/focusModel";

type Props = {
  projection: GraphProjection;
  focusId: string | null;
  onSelect: (id: string) => void;
};

/** Keyboard-first tree/outline hierarchy with indent + roving tabindex. */
export default function TreeOutlineView({ projection, focusId, onSelect }: Props) {
  const items = projection.outline;
  const refs = useRef<Map<string, HTMLLIElement>>(new Map());

  useEffect(() => {
    if (!focusId) return;
    refs.current.get(focusId)?.focus();
  }, [focusId]);

  const activeId = useMemo(
    () => focusId ?? items[0]?.id ?? null,
    [focusId, items],
  );

  return (
    <div className="tree-view" role="tree" aria-label="Tree outline">
      <ul role="group">
        {items.map((item) => (
          <li
            key={item.id}
            ref={(el) => {
              if (el) refs.current.set(item.id, el);
              else refs.current.delete(item.id);
            }}
            role="treeitem"
            aria-selected={focusId === item.id}
            tabIndex={rovingTabIndex(items, item.id, focusId)}
            style={{ paddingLeft: `${item.depth * 1.1}rem` }}
            onClick={() => onSelect(item.id)}
            onKeyDown={(e) => {
              if (isFocusNavKey(e.key)) {
                e.preventDefault();
                const next = moveFocusId(items, activeId, e.key);
                if (next) onSelect(next);
                return;
              }
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(item.id);
              }
            }}
            className={focusId === item.id ? "tree-item active" : "tree-item"}
          >
            <span className="outline-type">{item.node_type}</span>
            {item.label}
          </li>
        ))}
      </ul>
    </div>
  );
}
