import type { PrivateKeyAccount } from "viem";
import type { AutomatonConfig } from "./types.js";
import { DEFAULT_CONFIG } from "./types.js";

// No configuration, key store or wallet is read by the unattended service.
export function createLocalIdentity() {
  const address = "0x0000000000000000000000000000000000000000" as const;
  const deny = async (): Promise<never> => { throw new Error("Signing disabled in local mode"); };
  const account = { address, publicKey: "0x", source: "custom", type: "local",
    sign: deny, signMessage: deny, signTransaction: deny, signTypedData: deny } as unknown as PrivateKeyAccount;
  return { account, chainType: "evm" as const,
    chainIdentity: { address, chainType: "evm" as const, signMessage: deny } };
}

export function localServiceConfig(): AutomatonConfig {
  return { ...DEFAULT_CONFIG, name: "Atlas", localMode: true,
    genesisPrompt: "Tu es Atlas. Reste strictement local, sans finance ni acces aux secrets.",
    creatorAddress: "", walletAddress: createLocalIdentity().chainIdentity.address,
    sandboxId: "atlas-local", conwayApiKey: "", conwayApiUrl: "http://127.0.0.1:9",
    socialRelayUrl: undefined, inferenceModel: "qwen2.5:1.5b", maxTokensPerTurn: 256,
    ollamaBaseUrl: "http://127.0.0.1:11434", maxTurnsPerCycle: 1,
    skillsDir: "/var/lib/automaton-local/.automaton/skills",
    dbPath: "/var/lib/automaton-local/.automaton/state.db",
    heartbeatConfigPath: "/var/lib/automaton-local/.automaton/heartbeat.yml",
  } as AutomatonConfig;
}
