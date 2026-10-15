import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const SOURCE_ROOT = path.resolve(__dirname, "..");
const BANNED = [/localStorage/, /sessionStorage/, /NEXT_PUBLIC_[A-Z0-9_]*SECRET/];

function sourceFiles(directory: string): string[] {
  return readdirSync(directory).flatMap((entry) => {
    const fullPath = path.join(directory, entry);
    if (statSync(fullPath).isDirectory()) {
      return sourceFiles(fullPath);
    }
    return /\.(ts|tsx)$/.test(entry) && !entry.endsWith(".test.ts") && !entry.endsWith(".test.tsx")
      ? [fullPath]
      : [];
  });
}

describe("browser secret boundary", () => {
  it("does not persist storage or expose a secret environment variable", () => {
    const files = sourceFiles(SOURCE_ROOT);
    expect(files.length).toBeGreaterThan(0);
    for (const file of files) {
      const text = readFileSync(file, "utf8");
      for (const pattern of BANNED) {
        expect(text, file).not.toMatch(pattern);
      }
    }
  });
});
