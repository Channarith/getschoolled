import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "..", "content", "legal");
const DOCS = ["TERMS_OF_SALE.txt", "REFUND_POLICY.txt", "RECEIPTS_AND_TAXES.txt"];

for (const name of DOCS) {
  test(`${name} exists, is marked as a draft and starts with a title`, () => {
    const text = fs.readFileSync(path.join(dir, name), "utf8");
    assert.match(text.split("\n")[0], /^SALAREEN - /);
    assert.match(text, /DRAFT FOR REVIEW/);
  });
}

test("no sale document claims DMV approval or licensing compliance", () => {
  for (const name of DOCS) {
    const text = fs.readFileSync(path.join(dir, name), "utf8");
    for (const sentence of text.split(/(?<=[.!?])\s+/)) {
      if (/DMV[- ](approved|licensed)|satisf(y|ies) .*licens/i.test(sentence)) {
        assert.match(sentence, /\bnot\b|\bunless\b|\bcheck\b/i, `unqualified claim in ${name}: ${sentence}`);
      }
    }
  }
});

test("the terms say what a course is not, and that payment needs a login", () => {
  const terms = fs.readFileSync(path.join(dir, "TERMS_OF_SALE.txt"), "utf8");
  assert.match(terms, /not a DMV-approved or DMV-licensed driver education course/);
  assert.match(terms, /signed in/);
});

test("the refund policy never promises a silent no", () => {
  const text = fs.readFileSync(path.join(dir, "REFUND_POLICY.txt"), "utf8");
  assert.match(text, /silent "no"/);
  assert.match(text, /Apple and Google handle refunds/);
});

test("the legal hub lists the three sale documents", () => {
  const hub = fs.readFileSync(path.join(dir, "..", "..", "app", "legal", "page.tsx"), "utf8");
  for (const id of ["terms-of-sale", "refund-policy", "receipts-and-taxes"]) assert.ok(hub.includes(`"${id}"`), id);
});
