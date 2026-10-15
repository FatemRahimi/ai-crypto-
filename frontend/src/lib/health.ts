export type LiveHealth = {
  status: "ok";
  service: "ai-crypto-api";
  environment: string;
  phase: 1;
};

export function parseLiveHealth(value: unknown): LiveHealth | null {
  if (typeof value !== "object" || value === null) {
    return null;
  }
  const record = value as Record<string, unknown>;
  if (record.status !== "ok" || record.service !== "ai-crypto-api") {
    return null;
  }
  if (typeof record.environment !== "string" || record.phase !== 1) {
    return null;
  }
  return {
    status: "ok",
    service: "ai-crypto-api",
    environment: record.environment,
    phase: 1,
  };
}

export function apiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
}
