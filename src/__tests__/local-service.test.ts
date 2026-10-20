import { describe, it, expect } from "vitest";
import { createLocalIdentity, localServiceConfig } from "../local-service.js";
describe("unattended local service", () => {
  it("has no signing capability", async () => {
    const identity = createLocalIdentity();
    await expect(identity.chainIdentity.signMessage("test")).rejects.toThrow("Signing disabled");
    for (const method of ["sign", "signMessage", "signTransaction", "signTypedData"]) {
      await expect((identity.account as any)[method]({})).rejects.toThrow("Signing disabled");
    }
  });
  it("ignores cloud credentials and constrains its runtime", () => {
    const config = localServiceConfig();
    expect(config.localMode).toBe(true);
    expect(config.conwayApiKey).toBe("");
    expect(config.socialRelayUrl).toBeUndefined();
    expect(config.ollamaBaseUrl).toBe("http://127.0.0.1:11434");
    expect(config.maxTurnsPerCycle).toBe(1);
    expect(config.dbPath).toBe("/var/lib/automaton-local/.automaton/state.db");
  });
});
