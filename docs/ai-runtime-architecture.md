# JARVIS AI Cognition Runtime Architecture
## Phase 6 -- v0.5

**Status**: Pre-implementation design document
**Author**: JARVIS Engineering
**Prerequisite**: Phase 5.5 (JARVIS Kernel) complete -- 723/723 tests passing

---

## 1. Purpose

This document defines the architecture for the JARVIS AI Cognition Runtime (v0.5).

The Cognition Runtime is the first application layer built on top of the JARVIS Kernel.
It is not a single service. It is a general-purpose framework for how JARVIS thinks.
It knows nothing about trading, stocks, markets, or any other domain.

The Kernel is responsible for how the system runs.
The Cognition Runtime is responsible for how the system thinks.

Domain applications (Trading, Research, Voice, Science, Home Automation) are built
on top of the Cognition Runtime. They plug in as agents and skills. The runtime
itself never changes when a new domain is added.

The Kernel provides the OS primitives (DI, lifecycle, events, scheduler, metrics,
health, workers, queue). The Cognition Runtime uses all of them.

The AI Runtime is organised into three tiers:

```
                        User
                          |
                          v
                +---------+---------+
                |       Brain       |   <-- owns context, memory selection,
                |                   |       planning, delegation, objectives
                +---------+---------+
                          |
                          v
                +---------+---------+
                |      Planner      |   <-- decomposes goals into steps
                +---------+---------+
                          |
                          v
                +---------+---------+
                |    Coordinator    |   <-- routes steps to agents
                +---------+---------+
                          |
          +-------+-------+-------+-------+
          |       |       |       |       |
          v       v       v       v       v
       Trader  Analyst  Researcher Planner  (future agents)
          |       |       |
          v       v       v
        Skills  Skills  Skills             <-- domain expertise modules
          |       |       |
          v       v       v
        Tools   Tools   Tools              <-- external capabilities
```

The Brain is the single owner of conversation state. Agents never own state.
Agents own decision-making within their domain. Skills own domain expertise.
Tools own external I/O.

---

## 2. Goals

1. Be completely domain-agnostic -- no trading, market, or stock knowledge
2. Support multiple AI agents running concurrently on the same kernel
3. Provide a shared LLM execution layer that all agents use
4. Provide a shared memory layer (short-term + long-term + embeddings)
5. Provide a structured reasoning layer (chain-of-thought, reflection, planning)
6. Provide an orchestration layer that coordinates agent collaboration
7. Expose a single ExecutionContext that carries all state through the pipeline
8. Treat every request as a state machine with observable transitions
9. Emit events at every pipeline stage for metrics, health, and debugging
10. Wire all of the above to the kernel (DI, lifecycle, events, metrics, health)
11. Preserve all 723 existing tests -- no regressions

---

## 3. What Already Exists (Inventory)

The following files exist from earlier phases and contain working logic.
Phase 6 does NOT delete them. It wraps, extends, or replaces them cleanly.

| Existing File | Status | Phase 6 Action |
|---|---|---|
| `app/core/llm.py` | Working -- GeminiProvider, GroqProvider, OllamaProvider, LLMRouter | Wrap inside `ai/runtime/llm_gateway.py` |
| `app/core/orchestrator.py` | Working -- JarvisOrchestrator (monolith) | Decompose into agent + runtime modules |
| `app/agents/coordinator.py` | Stub -- AgentCoordinator, BaseAgent, AgentRole | Replace with full agent framework |
| `app/reasoning/engine.py` | Stub -- ReasoningEngine, ThoughtStep, Plan | Extend inside `ai/reasoning/` |
| `app/memory/manager.py` | Working -- MemoryManager, MemoryEntry, MemoryType | Extend inside `ai/memory/` |
| `app/core/config.py` | Legacy -- old Settings class | Superseded by Phase 5 config layer |
| `app/core/identity.py` | Working -- JarvisCore, FocusState | Kept as-is |
| `app/core/personality.py` | Working -- PersonalityEngine | Kept as-is |

---

## 4. Folder Structure

```
backend/app/ai/
|
|-- runtime/
|   |-- __init__.py
|   |-- context.py          # AIContext: per-request state (user, session, turn)
|   |-- execution.py        # ExecutionEngine: run one agent turn end-to-end
|   `-- llm_gateway.py      # LLMGateway: wraps app/core/llm.py, adds metrics + retry
|
|-- agents/
|   |-- __init__.py
|   |-- base.py             # BaseAgent ABC: execute(), can_handle(), health_check()
|   |-- trader.py           # TraderAgent: trade signals, execution decisions
|   |-- analyst.py          # AnalystAgent: technical analysis, market context
|   |-- researcher.py       # ResearcherAgent: news, web search, fundamentals
|   `-- planner.py          # PlannerAgent: goal decomposition, multi-step plans
|
|-- reasoning/
|   |-- __init__.py
|   |-- chain.py            # ChainOfThought: step-by-step reasoning trace
|   |-- reflection.py       # Reflection: self-critique and confidence scoring
|   `-- planner.py          # ReasoningPlanner: goal -> steps -> execution plan
|
|-- memory/
|   |-- __init__.py
|   |-- short_term.py       # ShortTermMemory: ring buffer, conversation context
|   |-- long_term.py        # LongTermMemory: persistent store interface
|   `-- embeddings.py       # EmbeddingService: text -> vector, similarity search
|
|-- perception/
|   |-- __init__.py
|   |-- market.py           # MarketPerception: live price, TA, signals
|   |-- news.py             # NewsPerception: market news, sentiment tagging
|   `-- sentiment.py        # SentimentPerception: aggregate sentiment scoring
|
|-- prediction/
|   |-- __init__.py
|   |-- feature_store.py    # FeatureStore: build feature vectors from candles
|   |-- forecasting.py      # ForecastingEngine: XGBoost model wrapper
|   `-- confidence.py       # ConfidenceScorer: signal confidence aggregation
|
|-- orchestration/
|   |-- __init__.py
|   |-- coordinator.py      # AgentCoordinator: route requests to agents
|   `-- workflow.py         # WorkflowEngine: multi-agent sequential/parallel flows
|
|-- prompts/
|   |-- __init__.py
|   |-- system.py           # SystemPromptBuilder: assemble system prompt
|   `-- templates.py        # PromptTemplate: named prompt templates
|
|-- tools/
|   |-- __init__.py
|   `-- registry.py         # AIToolRegistry: tools available to agents
|
`-- __init__.py             # Public API: AIRuntime facade
```

---

## 5. Skill Framework

Agents own decision-making. Skills own domain expertise.

A Skill is a focused, reusable module that encapsulates one area of knowledge
or computation. An agent composes Skills to produce its answer. Skills never
communicate directly with users and never call other agents.

Multiple agents may share the same Skill. For example, both TraderAgent and
AnalystAgent use the TechnicalAnalysisSkill. Neither duplicates that logic.

```
  TraderAgent                    AnalystAgent
       |                               |
       |-- TechnicalAnalysisSkill <----|   (shared)
       |-- FibonacciSkill              |
       |-- CandlestickSkill            |-- SupportResistanceSkill
       |-- SmartMoneySkill             |-- VWAPSkill
       `-- PatternRecognitionSkill     `-- ElliottWaveSkill

  ResearcherAgent
       |
       |-- NewsSkill
       |-- SentimentSkill
       |-- FundamentalsSkill
       `-- MacroEconomySkill
```

Skill responsibilities:
- Accept raw data (candles, news items, price ticks) as input
- Return a structured result (signal, score, annotation)
- Contain no I/O, no LLM calls, no side effects
- Be independently unit-testable with no mocks required

Skills live in `app/ai/skills/<domain>/`. They are introduced progressively
starting in Phase 6D when agents are built. The Skill interface is:

```python
class BaseSkill(ABC):
    name: str
    version: str

    @abstractmethod
    def run(self, data: dict) -> SkillResult:
        """Pure computation. No async. No I/O."""
        pass

    def describe(self) -> str:
        """Human-readable description of what this skill does."""
        return self.name
```

---

## 6. Agent Lifecycle

Each agent follows this lifecycle, managed by the JARVIS Kernel:

```
KERNEL LIFECYCLE MANAGER
        |
        v
  [startup hook]
        |
        v
  Agent.initialize()
    - register with ServiceRegistry
    - register health check with HealthMonitor
    - subscribe to EventBus topics
    - register metrics with MetricsEngine
        |
        v
  Agent.ready()  --> ServiceStatus.HEALTHY
        |
        v
  [request arrives via AgentCoordinator]
        |
        v
  Agent.can_handle(AIContext) --> bool
        |
        v
  Agent.execute(AIContext) --> AgentResult
    - perception (market/news/sentiment)
    - reasoning (chain-of-thought)
    - LLM call via LLMGateway
    - reflection (confidence check)
    - publish result event
        |
        v
  [shutdown hook]
        |
        v
  Agent.shutdown()
    - deregister from ServiceRegistry
    - flush pending metrics
```

---

## 7. Memory Flow

```
User Input
    |
    v
ShortTermMemory.add_turn(user_input)
    |
    v
EmbeddingService.encode(user_input)  [if enabled]
    |
    v
LongTermMemory.search(embedding, top_k=5)  [if enabled]
    |
    v
AIContext.memory_context = [recent_turns + relevant_long_term]
    |
    v
[Agent executes, produces reply]
    |
    v
ShortTermMemory.add_turn(reply)
    |
    v
LongTermMemory.store(entry, importance)  [if importance >= threshold]
```

Short-term memory is a ring buffer (max 50 entries, in-process).
Long-term memory is an interface -- backed by in-memory dict in Phase 6,
swappable to vector DB (Qdrant) in Phase 7+.

---

## 8. Thinking Pipeline

Every agent follows the same standard execution pipeline for every request.
No agent may skip a stage. Stages that produce no output pass an empty result
to the next stage -- they do not abort the pipeline.

```
  User Input
      |
      v
  1. UNDERSTAND
      Classify intent. Identify domain. Select agent.
      Output: intent_type, domain, confidence
      |
      v
  2. GATHER CONTEXT
      Fetch perception data relevant to the intent.
      (market prices, news, portfolio state, tool results)
      Output: perception_bundle
      |
      v
  3. RETRIEVE MEMORY
      Query short-term memory for recent turns.
      Query long-term memory for relevant past knowledge.
      Output: memory_context
      |
      v
  4. COLLECT TOOLS
      Identify which tools and skills are needed.
      Pre-load results where possible (e.g. TA computation).
      Output: tool_results, skill_results
      |
      v
  5. REASON
      Run ChainOfThought over context + memory + tools.
      Produce a structured thought chain.
      Output: thought_chain
      |
      v
  6. VERIFY
      Run Reflection over the thought chain.
      Check for contradictions, hallucination risk, low confidence.
      Output: critique, should_retry flag
      |
      v
  7. CONFIDENCE
      Aggregate confidence from reasoning + skill signals + perception.
      If confidence < threshold and retries remain, loop back to REASON.
      Output: final_confidence (0.0 - 1.0)
      |
      v
  8. EXPLAIN
      Build the explanation layer: why this answer, what data was used,
      what the confidence is, what the agent recommends.
      Output: explanation_bundle
      |
      v
  9. RESPOND
      Assemble final response from LLM call + explanation_bundle.
      Publish AgentCompletedEvent. Store to memory.
      Output: AgentResult
```

This pipeline is enforced by ExecutionEngine. Agents implement the domain-
specific logic inside each stage. The pipeline structure is fixed.

---

## 9. ExecutionContext

Instead of passing individual parameters between pipeline stages, every request
creates one `ExecutionContext` that travels through the entire pipeline.
Each stage reads from it and writes its results back into it.
This makes every request fully observable and debuggable.

```
ExecutionContext
  |
  |-- request_id        str        unique ID for this request
  |-- session_id        str        user session identifier
  |-- user_input        str        raw input from the user
  |-- history           list       recent conversation turns
  |-- active_goal       str        current goal being pursued
  |-- state             State      current pipeline state (see state machine)
  |
  |-- [set by Brain]
  |-- selected_agent    str        name of the agent chosen
  |-- intent_type       str        classified intent
  |
  |-- [set by Memory stage]
  |-- memory_context    list       retrieved memory entries
  |
  |-- [set by Skill/Tool stage]
  |-- skill_results     dict       name -> SkillResult
  |-- tool_results      dict       name -> ToolResult
  |
  |-- [set by Reasoning stage]
  |-- thought_chain     list       ThoughtStep sequence
  |-- critique          str        Reflection output
  |-- retry_count       int        number of reasoning retries so far
  |
  |-- [set by Confidence stage]
  |-- confidence        float      final 0.0-1.0 confidence score
  |
  |-- [set by Response stage]
  |-- response          str        final response text
  |-- explanation       str        how the answer was produced
  |
  |-- [observability]
  |-- timings           dict       stage -> elapsed_ms
  |-- metadata          dict       arbitrary key-value pairs
  `-- error             str|None   set if any stage failed
```

The context is created by ExecutionEngine at request start and discarded
after the response is returned. It is never stored to disk.

---

## 10. Request State Machine

Every request is a state machine. ExecutionEngine drives the transitions.
No stage may be skipped. Each transition emits an event to the EventBus.

```
  CREATED
      |
      v  --> RequestStartedEvent
  PLANNING
      |
      v  --> AgentSelectedEvent
  MEMORY_LOADING
      |
      v  --> MemoryLoadedEvent
  SKILL_SELECTION
      |
      v  --> SkillsCollectedEvent
  TOOL_EXECUTION
      |
      v  --> ToolsExecutedEvent
  REASONING
      |
      v  --> ReasoningCompletedEvent
      |       [if verify fails and retries remain: back to REASONING]
  VERIFICATION
      |
      v  --> VerificationCompletedEvent
  RESPONSE_GENERATION
      |
      v  --> ResponseGeneratedEvent
  COMPLETED
      |
      v  --> RequestFinishedEvent(success=True, latency_ms, confidence)

  [any stage may transition to]
  FAILED
      |
      v  --> RequestFinishedEvent(success=False, error, stage_failed)
```

Observability metrics collected automatically per request:
- Total execution time
- Time per stage (stored in ExecutionContext.timings)
- Selected agent name
- Selected skills (names and count)
- Number of tool calls
- Number of reasoning retries
- Final confidence score
- Success / failure + stage of failure

---

## 11. Reasoning Flow

```
AIContext (user_input, memory_context, perception_data)
    |
    v
ReasoningPlanner.decompose(goal)
    --> [step_1, step_2, ..., step_n]
    |
    v
ChainOfThought.think(step_i)
    --> ThoughtStep(content, confidence)
    |
    v
[repeat for each step]
    |
    v
Reflection.evaluate(thought_chain)
    --> overall_confidence, critique, should_retry
    |
    v
[if should_retry and retries_remaining > 0]
    --> back to ChainOfThought with critique injected
    |
    v
[final thought chain passed to LLMGateway as context]
```

---

## 12. Agent Contract

Every agent in the JARVIS AI Runtime implements the same interface.
This contract is enforced by BaseAgent. No agent may be registered with
the Coordinator unless it fully implements all seven methods.

```python
class BaseAgent(ABC):

    @abstractmethod
    def can_handle(self, context: AIContext) -> bool:
        """
        Return True if this agent is capable of handling the given context.
        Used by AgentCoordinator to select the right agent.
        Must be fast -- no I/O, no LLM calls.
        """

    @abstractmethod
    async def plan(self, context: AIContext) -> AgentPlan:
        """
        Decompose the request into an ordered list of steps.
        Uses ReasoningPlanner. Returns AgentPlan(steps, estimated_confidence).
        """

    @abstractmethod
    async def execute(self, context: AIContext) -> AgentResult:
        """
        Run the full Thinking Pipeline for this agent.
        Calls plan(), then executes each step using skills and tools.
        Returns AgentResult(response, confidence, explanation, metadata).
        """

    @abstractmethod
    async def verify(self, result: AgentResult) -> VerificationResult:
        """
        Self-check the result before returning it.
        Runs Reflection. Returns VerificationResult(passed, critique, retry).
        If retry=True, ExecutionEngine will re-run execute() with critique injected.
        """

    @abstractmethod
    def confidence(self, result: AgentResult) -> float:
        """
        Return a 0.0-1.0 confidence score for the result.
        Aggregates skill signals, reasoning confidence, and perception quality.
        """

    @abstractmethod
    def explain(self, result: AgentResult) -> str:
        """
        Return a human-readable explanation of how the result was produced.
        What data was used. What the reasoning was. What the confidence means.
        Injected into the final response by SystemPromptBuilder.
        """

    @abstractmethod
    async def learn(self, result: AgentResult, outcome: dict) -> None:
        """
        Called after the user receives the response and an outcome is known.
        Stores the result + outcome to long-term memory for future retrieval.
        Phase 6: stores to LongTermMemory. Phase 8: feeds Learning Engine.
        """
```

This contract means every future agent -- voice, portfolio, macro, news --
plugs into the runtime automatically without changes to the Coordinator,
ExecutionEngine, or any other infrastructure component.

---

## 13. Tool Calling

Agents can call tools. Tools are registered in AIToolRegistry.
Tool calls are synchronous from the agent's perspective.
The registry wraps each tool call with:
- timeout enforcement
- error isolation (tool failure does not crash agent)
- metrics recording (call count, latency, error rate)
- security check (tool allowed for this agent role?)

```
Agent.execute()
    |
    v
AIToolRegistry.call(tool_name, params, agent_role)
    |
    v
[security check: is tool_name allowed for agent_role?]
    |
    v
[execute tool with timeout]
    |
    v
ToolResult(success, output, error, latency_ms)
    |
    v
[metrics recorded]
    |
    v
[result injected into agent context]
```

---

## 14. Event Flow

The EventBus (from Phase 5.5) connects all AI Runtime components.

```
Published Events:
  AgentStartedEvent(agent_name, context_id)
  AgentCompletedEvent(agent_name, context_id, latency_ms)
  AgentFailedEvent(agent_name, context_id, error)
  LLMCallEvent(provider, model, tokens_used, latency_ms)
  MemoryStoredEvent(entry_id, importance)
  PerceptionUpdatedEvent(source, symbol, data_type)
  PredictionGeneratedEvent(symbol, direction, confidence)
  WorkflowStartedEvent(workflow_id, steps)
  WorkflowCompletedEvent(workflow_id, result)

Subscribers:
  MetricsEngine  -- records all events as counters/histograms
  HealthMonitor  -- watches AgentFailedEvent for degraded status
  Scheduler      -- triggers periodic perception refresh
  LongTermMemory -- listens for high-importance events to persist
```

---

## 15. Prediction Pipeline

```
MarketPerception.fetch(symbol)
    --> candles, price, volume
    |
    v
FeatureStore.build(candles)
    --> feature_vector (RSI, MACD, EMA, BB, ATR, volume_ratio, ...)
    |
    v
ForecastingEngine.predict(feature_vector, model_name)
    --> raw_prediction (direction, magnitude)
    |
    v
ConfidenceScorer.score(raw_prediction, ta_signal, news_sentiment)
    --> confidence (0.0 - 1.0), reasoning
    |
    v
PredictionResult(symbol, direction, confidence, features_used, model)
    |
    v
EventBus.publish(PredictionGeneratedEvent)
```

ForecastingEngine wraps the existing XGBoost .pkl models in `backend/models/`.
No new ML training in Phase 6 -- inference only.

---

## 16. Model Selection

LLMGateway selects the active provider using this priority chain:

```
1. AIContext.preferred_provider  (per-request override)
2. AISettings.active_llm         (configured default)
3. First enabled profile by priority (fallback)
4. Raise AIProviderUnavailableError (no providers available)
```

Retry on failure uses the PROVIDER_RETRY policy from Phase 5 resilience layer.
Fallback to next-priority provider after max retries exhausted.

---

## 17. Multi-Agent Support

Phase 6 implements single-agent-per-request with coordinator routing.
The architecture is designed for multi-agent from day one.

```
User Request
    |
    v
AgentCoordinator.route(AIContext)
    |
    v
[select best agent: can_handle() + priority + health status]
    |
    v
Agent.execute(AIContext)
    |
    v
AgentResult

-- Phase 7+ extension: parallel agent execution --

WorkflowEngine.run(workflow_definition)
    |
    v
[step_1: AnalystAgent]  [step_2: ResearcherAgent]  (parallel)
    |                           |
    v                           v
[step_3: PlannerAgent]  (sequential, receives both results)
    |
    v
[step_4: TraderAgent]   (final decision)
```

WorkflowEngine is scaffolded in Phase 6 but only sequential flows are active.
Parallel execution is a Phase 7 feature.

---

## 18. Failure Recovery

| Failure | Recovery |
|---|---|
| LLM provider timeout | Retry with PROVIDER_RETRY policy, then fallback to next provider |
| LLM provider error (5xx) | Same as timeout |
| All providers unavailable | Return AIProviderUnavailableError, agent returns degraded response |
| Agent exception | Caught by ExecutionEngine, AgentFailedEvent published, fallback response returned |
| Tool call timeout | ToolResult(success=False, error="timeout"), agent continues without tool result |
| Memory store failure | Log warning, continue without persistence (short-term still works) |
| Perception fetch failure | Log warning, agent proceeds with empty perception context |
| Prediction model missing | Log warning, ConfidenceScorer returns 0.5 (neutral) |

No failure in the AI Runtime should crash the kernel or the API server.
All failures are isolated, logged, and metriced.

---

## 19. Testing Strategy

Phase 6 tests live in `backend/tests/phase6/`.
All tests are pure unit tests -- no network, no file I/O, no LLM calls.

```
test_llm_gateway.py       -- LLMGateway routing, retry, fallback, metrics
test_agent_base.py        -- BaseAgent lifecycle, health check, event publishing
test_agent_trader.py      -- TraderAgent can_handle, execute, signal parsing
test_agent_analyst.py     -- AnalystAgent perception integration
test_reasoning.py         -- ChainOfThought, Reflection, ReasoningPlanner
test_memory.py            -- ShortTermMemory, LongTermMemory, EmbeddingService
test_perception.py        -- MarketPerception, NewsPerception, SentimentPerception
test_prediction.py        -- FeatureStore, ForecastingEngine, ConfidenceScorer
test_orchestration.py     -- AgentCoordinator routing, WorkflowEngine sequential
test_prompts.py           -- SystemPromptBuilder, PromptTemplate rendering
test_ai_runtime.py        -- AIRuntime facade integration (all components wired)
```

Target: 200 new tests. Total after Phase 6: 923/923.

All LLM calls are mocked. All perception fetches are mocked.
All XGBoost model loads are mocked.

---

## 20. Kernel Integration Map

| Kernel Component | AI Runtime Usage |
|---|---|
| DIContainer | All AI components registered as singletons; agents resolved by name |
| ServiceRegistry | Each agent registered with name, type=BaseAgent, tags=[role] |
| LifecycleManager | AIRuntime.startup() / shutdown() registered as lifecycle hooks |
| PluginLoader | LLM providers loaded by plugin_class dotted path from AISettings |
| EventBus | All agent events published; MetricsEngine and HealthMonitor subscribe |
| Scheduler | Periodic perception refresh (market quotes every 60s) |
| HealthMonitor | One health check per agent; AIRuntime overall health aggregated |
| MetricsEngine | LLM call count/latency, agent success/failure, token usage |
| WorkerPool | Perception fetches run in dedicated worker (non-blocking) |
| TaskQueue | Long-term memory writes enqueued (async, non-blocking) |

---

## 21. Public API (AIRuntime Facade)

`app/ai/__init__.py` exposes one object: `AIRuntime`.

```python
runtime = AIRuntime(container=di_container)

# Process a user message
result = await runtime.process(user_input, session_id, preferred_agent=None)

# Stream a user message
async for token in runtime.stream(user_input, session_id):
    yield token

# Get runtime health
health = await runtime.health()

# Get runtime metrics snapshot
metrics = runtime.metrics()
```

The existing `JarvisOrchestrator.process_message()` and `process_stream()` in
`app/core/orchestrator.py` will delegate to `AIRuntime` once Phase 6 is wired.
The orchestrator is NOT deleted -- it remains the API entry point.
This preserves all existing API routes and frontend compatibility.

---

## 22. What Phase 6 Does NOT Do

- Does not implement voice (Phase 9)
- Does not implement a trading execution engine (Phase 7)
- Does not implement portfolio management (Phase 7)
- Does not implement a HUD (Phase 9)
- Does not train new ML models (inference only)
- Does not add new Python dependencies
- Does not move or rename existing files outside `app/ai/`
- Does not break any existing test

---

## 23. Implementation Order

Phase 6 is divided into four independently testable sub-phases.
Each sub-phase ends with a full test run before the next begins.
Tasks are executed one at a time, one file per response.

### Phase 6A -- AI Cognition Runtime
Context, LLM gateway, execution engine, Brain layer, Coordinator wiring.

```
6A.1  app/ai/runtime/context.py           -- AIContext dataclass
6A.2  app/ai/runtime/llm_gateway.py       -- LLMGateway wrapping app/core/llm.py
6A.3  app/ai/runtime/execution.py         -- ExecutionEngine (Thinking Pipeline)
6A.4  app/ai/brain/brain.py               -- Brain (context, state, delegation)
6A.5  app/ai/orchestration/coordinator.py -- AgentCoordinator
6A.6  app/ai/orchestration/workflow.py    -- WorkflowEngine (sequential)
6A.7  app/ai/__init__.py                  -- AIRuntime facade
```
Milestone: AIRuntime.process() routes a request through Brain -> Coordinator.
Tests: tests/phase6/test_6a_runtime.py

### Phase 6B -- Memory System
Short-term, long-term, embeddings, retrieval, memory ranking.

```
6B.1  app/ai/memory/short_term.py         -- ShortTermMemory (ring buffer)
6B.2  app/ai/memory/long_term.py          -- LongTermMemory (in-memory, swappable)
6B.3  app/ai/memory/embeddings.py         -- EmbeddingService (cosine similarity)
```
Milestone: Brain retrieves relevant memory context for every request.
Tests: tests/phase6/test_6b_memory.py

### Phase 6C -- Reasoning Engine
Planning, chain-of-thought, reflection, verification, confidence, explanation.

```
6C.1  app/ai/reasoning/chain.py           -- ChainOfThought
6C.2  app/ai/reasoning/reflection.py      -- Reflection + VerificationResult
6C.3  app/ai/reasoning/planner.py         -- ReasoningPlanner
6C.4  app/ai/prompts/templates.py         -- PromptTemplate
6C.5  app/ai/prompts/system.py            -- SystemPromptBuilder
```
Milestone: ExecutionEngine runs full Thinking Pipeline with reasoning + verify.
Tests: tests/phase6/test_6c_reasoning.py

### Phase 6D -- Agent Framework
Base contract, four domain agents, skills scaffold, tool registry.

```
6D.1  app/ai/agents/base.py               -- BaseAgent ABC (full contract)
6D.2  app/ai/agents/analyst.py            -- AnalystAgent
6D.3  app/ai/agents/researcher.py         -- ResearcherAgent
6D.4  app/ai/agents/trader.py             -- TraderAgent
6D.5  app/ai/agents/planner.py            -- PlannerAgent
6D.6  app/ai/skills/__init__.py           -- BaseSkill + SkillResult
6D.7  app/ai/tools/registry.py            -- AIToolRegistry
6D.8  app/ai/perception/market.py         -- MarketPerception
6D.9  app/ai/perception/news.py           -- NewsPerception
6D.10 app/ai/perception/sentiment.py      -- SentimentPerception
6D.11 app/ai/prediction/feature_store.py  -- FeatureStore
6D.12 app/ai/prediction/forecasting.py    -- ForecastingEngine
6D.13 app/ai/prediction/confidence.py     -- ConfidenceScorer
```
Milestone: All four agents pass full contract. TraderAgent produces a signal.
Tests: tests/phase6/test_6d_agents.py

Final validation: all 923 tests pass before Phase 6 is declared complete.

---

## 24. Version Map (Updated)

| Version | Name | Status |
|---|---|---|
| v0.1 | Prototype | Done |
| v0.2 | Market Data Platform | Done |
| v0.3 | Configuration Kernel | Done |
| v0.4 | Infrastructure Kernel | Done |
| v0.5 | AI Runtime | This phase |
| v0.6 | Decision Intelligence | Next |
| v0.7 | Trading Runtime | Planned |
| v0.8 | Learning Engine | Planned |
| v0.9 | Voice + HUD | Planned |
| v1.0 | Production Release | Target |

---

## 25. Kernel Freeze Declaration

The JARVIS Kernel (v0.4) is hereby declared stable.

Packages under `app/core/` (di, service_registry, lifecycle, plugins, events,
scheduler, health, metrics, workers, queue) and `app/config/` and
`app/resilience/` are frozen.

No new package may be added to the kernel without a formal ACP.
No existing kernel interface may be changed without a formal ACP.

All new capabilities are built as applications on top of the kernel,
not inside it.

---

*Document version: 1.0 | Phase 6 pre-implementation | No code written yet*
