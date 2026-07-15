/**
 * Pure focus-model helpers for graph outline / tree keyboard navigation.
 * Unit-tested; UI wires these for roving tabindex + live region sync.
 */

export type FocusableItem = { id: string; depth?: number };

export function indexOfFocus(
  items: FocusableItem[],
  focusId: string | null,
): number {
  if (!items.length) return -1;
  if (!focusId) return 0;
  const i = items.findIndex((x) => x.id === focusId);
  return i >= 0 ? i : 0;
}

/** Move outline/list focus for Arrow/Home/End. Returns new index or -1 if empty. */
export function moveFocusIndex(
  items: FocusableItem[],
  currentIndex: number,
  key: string,
): number {
  if (!items.length) return -1;
  const cur = Math.min(Math.max(0, currentIndex), items.length - 1);
  switch (key) {
    case "ArrowDown":
      return Math.min(items.length - 1, cur + 1);
    case "ArrowUp":
      return Math.max(0, cur - 1);
    case "Home":
      return 0;
    case "End":
      return items.length - 1;
    default:
      return cur;
  }
}

export function moveFocusId(
  items: FocusableItem[],
  focusId: string | null,
  key: string,
): string | null {
  const next = moveFocusIndex(items, indexOfFocus(items, focusId), key);
  return next < 0 ? null : items[next]!.id;
}

/** Whether a key is part of the outline focus model. */
export function isFocusNavKey(key: string): boolean {
  return (
    key === "ArrowDown" ||
    key === "ArrowUp" ||
    key === "Home" ||
    key === "End"
  );
}

/**
 * Tabindex for roving focus: only the active item is tabbable (0); others -1.
 */
export function rovingTabIndex(
  items: FocusableItem[],
  itemId: string,
  focusId: string | null,
): 0 | -1 {
  if (!items.length) return -1;
  const idx = indexOfFocus(items, focusId);
  const active = items[idx]!.id;
  return itemId === active ? 0 : -1;
}
