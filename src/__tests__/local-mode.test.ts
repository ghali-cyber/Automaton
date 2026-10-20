import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import Database from 'better-sqlite3';
import { MIGRATION_V6 } from '../state/schema.js';
import { ModelRegistry } from '../inference/registry.js';
import { InferenceRouter } from '../inference/router.js';
import { InferenceBudgetTracker } from '../inference/budget.js';
import { DEFAULT_MODEL_STRATEGY_CONFIG } from '../inference/types.js';
import { discoverOllamaModels } from '../ollama/discover.js';
import { createInferenceClient } from '../conway/inference.js';

let db: InstanceType<typeof Database>;
beforeEach(() => { db = new Database(':memory:'); db.exec(MIGRATION_V6); });
afterEach(() => { db.close(); vi.unstubAllGlobals(); });

describe('explicit local mode', () => {
  async function setup() {
    const registry = new ModelRegistry(db);
    registry.initialize();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({models:[{name:'qwen2.5:1.5b'}]}))));
    await discoverOllamaModels('http://localhost:11434', db);
    const budget = new InferenceBudgetTracker(db, {...DEFAULT_MODEL_STRATEGY_CONFIG, localOnly:true, inferenceModel:'qwen2.5:1.5b'});
    return {registry, router: new InferenceRouter(db, registry, budget)};
  }
  it('selects Ollama at every tier despite installed cloud defaults', async () => {
    const {router}=await setup();
    for (const tier of ['dead','critical','low_compute','normal','high'] as const) {
      expect(router.selectModel(tier,'agent_turn')?.provider).toBe('ollama');
      expect(router.selectModel(tier,'agent_turn')?.modelId).toBe('qwen2.5:1.5b');
    }
  });
  it('fails closed rather than falling back to paid inference', async () => {
    const {router,registry}=await setup();
    registry.setEnabled('qwen2.5:1.5b',false);
    expect(()=>router.selectModel('normal','agent_turn')).toThrow('local model is unavailable');
  });
  it('routes the request to localhost and records zero cost', async () => {
    const {router,registry}=await setup();
    const fetchMock=vi.fn().mockResolvedValue(new Response(JSON.stringify({choices:[{message:{role:'assistant',content:'Bonjour local'},finish_reason:'stop'}],usage:{prompt_tokens:10,completion_tokens:3,total_tokens:13}})));
    vi.stubGlobal('fetch',fetchMock);
    const inference=createInferenceClient({apiUrl:'https://cloud.invalid',apiKey:'',defaultModel:'qwen2.5:1.5b',maxTokens:64,ollamaBaseUrl:'http://localhost:11434',getModelProvider:id=>registry.get(id)?.provider});
    const result=await router.route({messages:[{role:'user',content:'Bonjour'}],taskType:'agent_turn',tier:'normal',sessionId:'test',maxTokens:64},inference.chat);
    expect(result.content).toBe('Bonjour local');
    expect(result.costCents).toBe(0);
    expect(String(fetchMock.mock.calls[0][0])).toBe('http://localhost:11434/v1/chat/completions');
    expect(JSON.parse(fetchMock.mock.calls[0][1].body).model).toBe('qwen2.5:1.5b');
  });
});
