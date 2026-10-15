import { afterEach, describe, expect, it, vi } from "vitest";
import { apiBaseUrl, parseLiveHealth } from "@/lib/health";

describe("parseLiveHealth", () => {
  it("accepts the phase 1 live payload", () => {
    expect(
      parseLiveHealth({
        status: "ok",
        service: "ai-crypto-api",
        environment: "local",
        phase: 1,
      }),
    ).toEqual({
      status: "ok",
      service: "ai-crypto-api",
      environment: "local",
      phase: 1,
    });
  });

  it("rejects anything that is not the known health shape", () => {
    expect(parseLiveHealth({ status: "ok", price: 100 })).toBeNull();
    expect(parseLiveHealth(null)).toBeNull();
  });
});

describe("apiBaseUrl", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("follows NEXT_PUBLIC_API_URL", () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "http://127.0.0.1:8001");
    expect(apiBaseUrl()).toBe("http://127.0.0.1:8001");
  });
});
