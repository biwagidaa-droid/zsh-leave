// اجرای آزمون‌های واحد بدون وابستگی تازه: esbuild (همراه Vite) فایل‌های TS را باندل می‌کند و node:test اجرا می‌شود.
import { build } from "esbuild";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const dir = new URL("../tests/", import.meta.url).pathname;
const entries = readdirSync(dir).filter((f) => f.endsWith(".test.ts")).map((f) => join(dir, f));
if (!entries.length) { console.error("آزمونی یافت نشد"); process.exit(1); }
const out = mkdtempSync(join(tmpdir(), "zsh-tests-"));
await build({
  entryPoints: entries, outdir: out, bundle: true, platform: "node", format: "esm",
  outExtension: { ".js": ".mjs" }, jsx: "automatic", logLevel: "error", target: "node18",
});
const files = readdirSync(out).filter((f) => f.endsWith(".mjs")).map((f) => join(out, f));
const r = spawnSync(process.execPath, ["--test", ...files], { stdio: "inherit" });
process.exit(r.status ?? 1);
