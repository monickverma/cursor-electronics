# JEV by TypeSafe AI (typesafe.ai): identity, capabilities, integration, pricing, limitations

Method note (read first): typesafe.ai, docs.typesafe.ai, Wikipedia, Tom's Hardware and most third-party pages were **blocked by this environment's egress proxy**, so I could not open them. Facts below come from (a) **primary package metadata and SDK source code** pulled directly from PyPI and npm (high confidence, first-party), and (b) **web search result snippets** (medium confidence: summaries of the linked pages, not verified by reading the full page). Every bullet says which kind it is. As of 2026-09-24, the product is 9 days past launch, so expect fast changes.

## 1. What is typesafe.ai, and what is JEV? (identity and acronym)

### Takeaway
Identity confirmed with high confidence. TypeSafe AI is a San Francisco AI lab. "Jev" (usually written "Jev", sometimes "JEV") is its first model, which it calls a "System One model." Jev does not generate text. It returns typed decisions (yes/no, choice, score) with calibrated probabilities. I found **no source that treats "JEV" as an acronym**: every source uses it as a proper name, so no expansion is recorded.

### Cited Findings
- Jev is a proprietary model from TypeSafe AI, a San Francisco company founded in 2024 by Diogo Almeida, Erik Gafni and Sasha Sheng. It entered **limited early access on 15 Sept 2026**, announced together with a **US$40M seed round led by DCVC** (search snippet) — [Wikipedia: Jev (AI model)](https://en.wikipedia.org/wiki/Jev_(AI_model))
- The CEO, Almeida, spent about 4 years at OpenAI working on RLHF, InstructGPT, ChatGPT and GPT-4 (search snippet) — [Wikipedia](https://en.wikipedia.org/wiki/Jev_(AI_model)); [TypeSafe blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- The launch post is "Introducing System One Models & Jev," dated 15 Sept 2026. The "System One" name comes from Kahneman's fast, intuitive System 1 thinking (search snippet) — [TypeSafe AI Blog](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- Jev "does not generate natural-language text. It instead returns typed values together with probability estimates and confidence scores," and its output is meant to be read by software, not people (search snippet) — [Wikipedia](https://en.wikipedia.org/wiki/Jev_(AI_model))
- The official SDK sets the default model to `"jev-latest"`. The API's model list example shows `{"name": "jev-latest", "description": "General-purpose system one model.", "release_date": "2026-09-15"}` (first-party code) — [PyPI typesafe-sdk 0.7.1](https://pypi.org/project/typesafe-sdk/)
- OpenRouter lists a versioned model id, "Jev 1.13" (search result title only) — [OpenRouter typesafe/jev-1.13](https://openrouter.ai/typesafe/jev-1.13)

### Inferences
- The user's "jev from typesafe.ai" is this product. Nothing else with that name shows up.
- Possible confusion: "Typesafe Inc." was the old name of Lightbend, the Scala/Akka company. It has no connection to typesafe.ai. The PyPI package `typesafe` (0.9.1, "formal type asserting decorators") is also unrelated.

### Gaps
- No acronym expansion for "JEV" was found. Assume it is a name, not an acronym.
- I could not read the launch blog directly, so exact wording and any named launch customers are unverified.

## 2. What decision workflows does Jev support? Core primitives

### Takeaway
Jev takes a **state** (any text or JSON describing the situation) plus a named set of **questions**. Each question is one of three primitives: **Noul** (yes/no probability), **Choice** (pick one label from a fixed set) or **Score** (rate on an ordered rubric). Jev answers all questions **in parallel in one call** and returns probabilities and a confidence value for each. It suits classification, routing, gating, triage, moderation, rubric scoring and LLM-as-judge-style evaluation. It does not produce free text, generate structured data, or reason over multiple steps.

### Cited Findings (first-party SDK source, typesafe-sdk 0.7.1 wheel)
- Endpoints: `POST https://api.typesafe.ai/v1/systemone` and `GET /v1/models`. Request body: `{"state": ..., "model": ..., "questions": {name: question}}` — [PyPI typesafe-sdk](https://pypi.org/project/typesafe-sdk/)
- **Noul** question: `instructions` (text, object or array, optional) and optional `criteria: {true: ..., false: ...}`. **NoulAnswer**: `noul: float`, the "probability of a yes answer or a true statement, from 0 to 1 … values near 0.5 indicate uncertainty" — [PyPI typesafe-sdk](https://pypi.org/project/typesafe-sdk/)
- **Choice** question: `criteria: {label: description-or-None}`. **ChoiceAnswer**: `choice` (the label with the highest probability), `confidence` (0–1; "use lower values to flag uncertain selections for review") and `probabilities` per label, which sum to about 1 — [PyPI typesafe-sdk](https://pypi.org/project/typesafe-sdk/)
- **Score** question: `criteria` is an ordered, non-empty list of level descriptions, with the index as the score, starting at 0. **ScoreAnswer**: `score` (the "probability-weighted average of the rubric levels. May fall between integer levels"), `confidence`, a `legend` and per-level `probabilities` — [PyPI typesafe-sdk](https://pypi.org/project/typesafe-sdk/)
- The response carries `model`, `usage` (`input_tokens`, `output_tokens`; "Output tokens are currently free of charge") and `answers` keyed by question name — [PyPI typesafe-sdk](https://pypi.org/project/typesafe-sdk/)
- Documented use cases: choosing one label from a known set, scoring against a rubric, estimating support for a yes/no statement, choosing an agent tool, ranking candidates, and screening content before another action runs (search snippet) — [TypeSafe MCP / GitHub topic results](https://github.com/topics/typesafe-jev); [cloudraft use cases](https://www.cloudraft.io/blog/top-use-cases-of-jev-typesafe-ai-model)
- Jev is non-autoregressive, produces decisions "in a single pass," and evaluates independent questions in parallel (search snippet) — [MindStudio](https://www.mindstudio.ai/blog/jev-system-one-model-launch)
- Training method is called "RLCD — Reinforcement Learning for Calibrated Decisions." The goal is that higher-probability predictions are correct more often (search snippet, third-party summary) — [Community reference gist](https://gist.github.com/pjburnhill/adf8d28efcad9df037bfdece178ef965); [getmaxim](https://www.getmaxim.ai/articles/what-is-jev-system-one-model/)

### Inferences
- In practice Jev is a hosted, calibrated classifier/scorer that uses prompt-style instructions instead of training data. It fits "decide among known options" steps, not "author an artifact" steps.
- The `confidence` and probability fields are built for threshold routing: auto-accept when confident, send to a human or an LLM when not.

### Gaps
- No independent calibration study found. Third-party writers themselves advise checking calibration on your own data before relying on it ([getmaxim](https://www.getmaxim.ai/articles/what-is-jev-system-one-model/)).
- Image and multimodal input support is unknown. The SDK types allow only JSON/text `state`.

## 3. How developers integrate it (API, SDKs, CLI, MCP, agent frameworks)

### Takeaway
There are official **REST API**, **Python SDK** (`typesafe-sdk`) and **TypeScript SDK** (`@typesafe-ai/sdk`) packages. **Pydantic AI** supports Jev natively (`typesafe:jev-latest`). It is also listed on **OpenRouter**. I found **no official CLI or MCP server**. Several community MCP servers and a community `@jev.fn` decorator package exist. Keys come from console.typesafe.ai.

### Cited Findings
- **Python SDK** `typesafe-sdk`: v0.7.1 (21 Sept 2026). First release 0.0.1a0 was on 9 Sept 2026. Author "TypeSafe AI <support@typesafe.ai>", MIT licence, Python >=3.10, classifier "Production/Stable", repo github.com/typesafe-ai/typesafe-sdk-python. It has sync and async clients (`TypeSafeClient`, `AsyncTypeSafeClient`), a retry policy, a typed error hierarchy (`TypeSafeRateLimitError` and others), a default 10s timeout, and env vars `TYPESAFE_API_KEY`, `TYPESAFE_BASE_URL`, `TYPESAFE_DEFAULT_MODEL` (first-party) — [PyPI typesafe-sdk](https://pypi.org/project/typesafe-sdk/)
- Official quickstart, verbatim from the package README:
  ```python
  from typesafe_sdk import Choice, TypeSafeClient
  with TypeSafeClient() as client:
      response = client.system_one(
          state={"document": "I was charged twice. Please fix this ASAP."},
          questions={"category": Choice(
              instructions="What is this ticket about?",
              criteria={"billing": None, "technical": None, "other": None})},
      )
  print(response.choices["category"].choice)
  ```
  — [PyPI typesafe-sdk](https://pypi.org/project/typesafe-sdk/)
- **TypeScript SDK** `@typesafe-ai/sdk`: "TypeScript SDK for the TypeSafe API," latest 0.6.0, created 12 Sept 2026. Maintainers use @typesafe.ai email addresses (diogo@, allie@) (first-party registry data) — [npm @typesafe-ai/sdk](https://www.npmjs.com/package/@typesafe-ai/sdk)
- **Pydantic AI**: `TypeSafeModel` and `TypeSafeProvider` were added in PR #8450. Install with `pip install "pydantic-ai[typesafe]"` and use model id `typesafe:jev-latest`. Each field of `output_type` becomes a question and the user prompt becomes the state (search snippet) — [Pydantic docs: TypeSafe (Jev)](https://pydantic.dev/docs/ai/models/typesafe/); [PR #8450](https://github.com/pydantic/pydantic-ai/pull/8450). Pydantic also published "Cheap AI scoring with Jev and Pydantic Evals" — [pydantic.dev](https://pydantic.dev/articles/jev-evals)
- **Community `jev` package** (PyPI 0.3.0, 18 Sept 2026, no named author, Python >=3.14). `@jev.fn` compiles a function signature, docstring and Pydantic return model into a Jev query. Field mapping: `bool`→Noul (threshold 0.5), `Literal`/`Enum`→Choice, bounded `int`/`float`→Score. `str`, nested models, lists and `Optional` raise `TypeError`. `.map()` batches items into one call. Returning a model instance directly skips the API, which gives tests a mock point. Stated limits: 255 options per choice, 256 levels per score — [PyPI jev](https://pypi.org/project/jev/)
- **MCP servers (community, not official)**: jbt95/jev-toolkit ("MCP-first toolkit … One stdio server (jev mcp)"), itsmostafa/typesafe-mcp, nirvana124/typesafe-mcp, pedroknigge/mcp_jev. The descriptions mention a TypeScript/Node 20+ stdio server for Claude Code (search snippets) — [jev-toolkit](https://github.com/jbt95/jev-toolkit); [itsmostafa/typesafe-mcp](https://github.com/itsmostafa/typesafe-mcp); [Glama mcp_jev](https://glama.ai/mcp/servers/pedroknigge/mcp_jev)
- Supply-chain warning: `typesafe-ai` on PyPI is **not** official. A third party (Gerome Dexheimer) registered it as a defensive "slopsquatting" shim because AI assistants invent that name. The real package is `typesafe-sdk`. The npm name `typesafe-sdk` (unscoped) is also held by an unrelated user — [PyPI typesafe-ai](https://pypi.org/project/typesafe-ai/)
- LangChain published a guide, "building a harness with Jev" (search result title) — [LangChain blog](https://www.langchain.com/blog/building-a-harness-with-jev)

### Inferences
- The integration surface is small: one POST endpoint and three question types, so wrapping it is cheap.
- Pin the SDK version. The SDK went from 0.0.1a0 to 0.7.1 in 12 days, even though it is labelled "Production/Stable."

### Gaps
- Could not confirm whether an official MCP server or CLI exists, because the docs site was blocked. None showed up in search or registry checks.
- Official rate limits and SLAs were not found.

## 4. Pricing, availability, maturity, notable users, limitations

### Takeaway
Jev is in **limited early access since 15 Sept 2026**, with advertised early-access pricing of **$0.042 per 1M input tokens and free output**. Documented limits: text/JSON-only typed outputs, a context cap of roughly 32k tokens per state+question branch and roughly 65k per request (from third-party summaries), fixed-option answers only, and headline speed and cost figures that come from the vendor.

### Cited Findings
- Price: $0.042 per 1M input tokens ($42 per billion), output free. This is early-access pricing and may change (search snippet) — [MindStudio pricing](https://www.mindstudio.ai/blog/jev-pricing-cost-per-token); [The Rundown](https://www.therundown.ai/news/typesafe-jev-ai-decisions-software). The SDK schema confirms "Output tokens are currently free of charge" (first-party) — [PyPI typesafe-sdk](https://pypi.org/project/typesafe-sdk/)
- Reported latency: 70–500 ms per response (search snippet citing TypeSafe) — [Pydantic docs / AlphaSignal](https://alphasignal.ai/news/pydantic-ai-adds-jev-to-cut-classification-latency-6x-without-generating-tokens)
- Context limits: about 32,768 tokens per branch (state plus one question), about 65,536 per request. High-cardinality choices may need multi-stage scoring (search snippet, third-party) — [Community reference gist](https://gist.github.com/pjburnhill/adf8d28efcad9df037bfdece178ef965); [MindStudio](https://www.mindstudio.ai/blog/jev-system-one-model-launch)
- Vendor claim: up to **193.6x faster and 444.6x cheaper** than frontier LLMs, measured against GPT-6 Astra and Fable 5.1 on multi-step workflows, at the high end of four selected evaluations (search snippet) — [Tom's Hardware](https://www.tomshardware.com/tech-industry/artificial-intelligence/typesafe-ais-jev-offers-an-alternative-to-llms-that-claims-to-be-193x-faster-and-445x-cheaper-system-one-type-model-is-bespoke-for-probabilistic-decision-making); [Latent Space AINews](https://www.latent.space/p/ainews-jev-a-system-one-model-that)
- **Independent checks found much smaller gains**: 4–7x faster and 31–65x cheaper than Claude Sonnet 5, GPT-5.6 Sol and Gemini 3.8 Flash. A listing-moderation test (Near Here) found about 5x faster and 8.6x cheaper than Mistral Small 4 (search snippets) — [DEV Community](https://dev.to/arifulislamat/typesafes-jev-model-is-it-really-193x-faster-and-444x-cheaper-56oa); [Cherry Creek News](https://thecherrycreeknews.com/typesafe-jev-system-one-model-claims-evals-independent-tests-cherry_creek/); [jev-vs-claude-benchmark](https://github.com/prerak1603/jev-vs-claude-benchmark)
- Criticism of method: a headline says Jev's "own eval scores against two other models' answers," meaning the eval labels were LLM-generated (search result title) — [Cherry Creek News](https://thecherrycreeknews.com/typesafe-jev-system-one-model-claims-evals-independent-tests-cherry_creek/); a claim-vs-evidence write-up — [pearpages](https://pearpages.com/blog/2026/09/16/jev-sorted-what-typesafes-system-one-model-actually-is-and-what-is-still-just-a-claim)
- A third-party reseller, "B.AI API," lists Jev at the same $0.042/1M input (search result title) — [KuCoin news](https://www.kucoin.com/news/flash/typesafe-ai-model-jev-launches-on-b-ai-api-with-0-042-1m-token-input-cost)

### Inferences
- The cost is so low that it rarely matters. Latency (tens to hundreds of ms) and calibrated confidence are the real benefits.
- "Limited early access" plus a vendor only 9 days past launch means real availability and continuity risk. Do not put it on a critical path without a fallback.

### Gaps
- No verified list of named production customers or GA date was found.
- Several sites (jevtypesafeai.com, jevlist.ai, lmspedia) look like SEO/aggregator sites and were not used as sources of fact.
- Unknown: data retention, privacy, SOC 2, and region/on-prem options.

## 5. Positioning vs. alternatives (and relevance to a Circuit OS-style project)

### Takeaway
Jev is positioned as a **replacement for LLM calls in fast decision steps**: classification, routing, guardrails and cheap judging. It is not a structured-output library for generative models. Instructor, Pydantic AI (with LLMs) and BAML constrain an LLM to *generate* arbitrary typed JSON. Jev can only *choose among, score or affirm* predefined options, and it adds calibrated probabilities. It is not a decision-log or ADR tool: "make decisions" here means runtime machine decisions inside software, not recording architecture decisions.

### Cited Findings
- Framed as "the decision layer" for agents and backends: gates, risk checks, file triage, choosing tools (search snippet) — [mcpplaygroundonline Jev MCP](https://mcpplaygroundonline.com/blog/jev-mcp); [Medium: Typed AI Decisions for Backends](https://medium.com/@faaaizan/jev-by-typesafe-typed-ai-decisions-for-backends-a8626a37c4df)
- Pydantic positions it for cheap scoring in evals (LLM-as-judge replacement) — [pydantic.dev Jev evals](https://pydantic.dev/articles/jev-evals)
- The `jev` package states Jev "cannot produce" `str`, nested models or lists (first-party README of the community package) — [PyPI jev](https://pypi.org/project/jev/)
- Trade-off guidance on when to use a decision model instead of an LLM — [Correlation One](https://www.correlation-one.com/blog/what-is-an-ai-decision-model-jev-system-one-models-and-when-to-use-one-instead-of-an-llm-2026)

### Inferences (for the Circuit OS decision)
- Circuit OS's core path needs *generated* structured JSON: DesignSpec, a CircuitIR with components and connections, and patch JSON. **Jev cannot produce this**, because its answers are only noul/choice/score over fixed options. It cannot replace `circuit_reasoner.py` or `patcher.py`.
- Plausible fits:
  1. Classifying a prompt into one of the 5 Phase 1 templates (TPL_001–TPL_005, plus an "out of scope" label) as a Choice with confidence. Low confidence falls back to Claude `intent_parser` or asks the user to clarify.
  2. Pre-screening patch commands, e.g. a Noul for "this command requests a change outside Phase 1 scope."
  3. Rubric-scoring `explainer.py` output for "consequential vs descriptive" language as an automated eval (a Score with a 0–2 rubric).
- These uses keep "The One Rule" intact: Jev emits typed values, never SPICE, KiCad or .ino. But the project rule says AI modules use Anthropic `tool_use`, so a Jev call is a new provider and a new env var (`TYPESAFE_API_KEY`). That needs an explicit decision, and `config.py` must treat the key as optional so startup does not fail when it is absent.
- It should not replace deterministic checks: `ir_validator.py` and `HardwareRuleEngine` are rule-based physics checks, and a probabilistic model should not override them.

### Gaps
- No public head-to-head accuracy benchmark exists for Jev vs a Claude `tool_use` classifier on domain-specific (electronics) prompts. It would have to be measured locally.
