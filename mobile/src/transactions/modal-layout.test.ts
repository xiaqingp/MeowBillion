import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import test from "node:test";

const source = readFileSync(join(__dirname, "TransactionsScreen.tsx"), "utf8");

test("transaction editor constrains the ScrollView instead of its content", () => {
  assert.equal(
    source.match(/style=\{s\.modalScroll\}/g)?.length,
    2,
  );
  assert.equal(
    source.match(/contentContainerStyle=\{s\.modalContent\}/g)?.length,
    2,
  );
  assert.match(source, /modalScroll:\s*\{[\s\S]*maxHeight:\s*"94%"/);
});
