import assert from "node:assert/strict";
import test from "node:test";
import {
  indexOfFocus,
  isFocusNavKey,
  moveFocusId,
  moveFocusIndex,
  rovingTabIndex,
} from "./focusModel.ts";

const items = [
  { id: "a", depth: 0 },
  { id: "b", depth: 1 },
  { id: "c", depth: 1 },
  { id: "d", depth: 0 },
];

test("moveFocusIndex ArrowDown/Up/Home/End", () => {
  assert.equal(moveFocusIndex(items, 0, "ArrowDown"), 1);
  assert.equal(moveFocusIndex(items, 1, "ArrowUp"), 0);
  assert.equal(moveFocusIndex(items, 2, "Home"), 0);
  assert.equal(moveFocusIndex(items, 0, "End"), 3);
  assert.equal(moveFocusIndex(items, 3, "ArrowDown"), 3);
  assert.equal(moveFocusIndex([], 0, "ArrowDown"), -1);
});

test("moveFocusId syncs with focusId", () => {
  assert.equal(moveFocusId(items, "b", "ArrowDown"), "c");
  assert.equal(moveFocusId(items, null, "ArrowDown"), "b");
});

test("rovingTabIndex only active is 0", () => {
  assert.equal(rovingTabIndex(items, "a", "a"), 0);
  assert.equal(rovingTabIndex(items, "b", "a"), -1);
  assert.equal(rovingTabIndex(items, "a", null), 0);
});

test("indexOfFocus defaults", () => {
  assert.equal(indexOfFocus(items, null), 0);
  assert.equal(indexOfFocus(items, "c"), 2);
  assert.equal(indexOfFocus(items, "missing"), 0);
});

test("isFocusNavKey", () => {
  assert.equal(isFocusNavKey("ArrowDown"), true);
  assert.equal(isFocusNavKey("Enter"), false);
});
