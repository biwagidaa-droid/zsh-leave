import assert from "node:assert/strict";
import { test } from "node:test";
import { resolveDemoMode } from "../src/api/mode";

test("Demo defaults to development only and can be disabled", () => {
  assert.equal(resolveDemoMode(true), true);
  assert.equal(resolveDemoMode(true, "false"), false);
  assert.equal(resolveDemoMode(false), false);
  assert.equal(resolveDemoMode(false, "false"), false);
});

test("production build rejects explicit Demo mode", () => {
  assert.throws(() => resolveDemoMode(false, "true"), /حالت Demo در build عملیاتی مجاز نیست/);
});
