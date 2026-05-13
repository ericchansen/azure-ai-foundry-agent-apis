# Azure AI Foundry — Agent APIs & Operational Metrics Guide

Practical, tested examples for retrieving **agent metadata**, **per-run token usage**, **aggregate operational metrics**, and **evaluation scores** from [Azure AI Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/).

## The Problem

Azure AI Foundry's UI shows rich agent details — name, model, tools, versioning, token usage, error rates, latency — but the documentation doesn't clearly explain **how to access all of this programmatically**. This repo fills that gap with tested code samples covering every API surface.

## Quick-Reference: Where to Get What

| Data You Need | API Surface | Example |
|---|---|---|
| Agent name, model, tools, instructions, metadata | OpenAI Assistants API | [`01_agent_metadata.py`](examples/01_agent_metadata.py) |
| Agent versioning & lifecycle | Foundry Project v1 API | [`01_agent_metadata.py`](examples/01_agent_metadata.py) |
| Per-run token usage & latency | Runs API (per-thread) | [`02_runs_and_usage.py`](examples/02_runs_and_usage.py) |
| Run steps (tool calls, sub-steps) | Run Steps API | [`02_runs_and_usage.py`](examples/02_runs_and_usage.py) |
| **Aggregate metrics** (error rates, total tokens, avg latency) | **Application Insights** via KQL | [`03_tracing_and_metrics.py`](examples/03_tracing_and_metrics.py) |
| Evaluation scores (coherence, safety, etc.) | OpenAI Evals API | [`04_evaluations.py`](examples/04_evaluations.py) |
| All of the above via cURL | REST | [`curl_reference.sh`](examples/curl_reference.sh) |

> **Key finding**: There is **no direct "metrics endpoint"** for aggregate operational data. The AI Foundry monitoring dashboard reads exclusively from **Application Insights** via OpenTelemetry traces.

## Architecture

```
┌──────────────────────┐          ┌─────────────────────────────┐
│  Your Application     │          │  Azure AI Foundry            │
│                       │          │                              │
│  1. List agents       │── REST ─▶│  /openai/assistants          │
│  2. Get agent detail  │          │  /openai/threads/*/runs      │
│  3. Get run usage     │          │  /openai/threads/*/runs/steps│
│                       │          │                              │
│  4. Aggregate metrics │── KQL ──▶│  Application Insights        │
│     (token, latency,  │          │  (via Azure Monitor Logs)    │
│      error rates)     │          │                              │
│  5. Eval scores       │── REST ─▶│  OpenAI Evals API            │
└──────────────────────┘          └─────────────────────────────┘
```

## Prerequisites

1. **Azure AI Foundry project** with an AI Services resource and at least one model deployment
2. **Python 3.9+**
3. **Azure CLI** (`az login`) or a service principal for authentication
4. (For metrics) **Application Insights** connected to your Foundry project

## Setup

```bash
# Clone the repo
git clone https://github.com/ericchansen/azure-ai-foundry-agent-apis.git
cd azure-ai-foundry-agent-apis

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your values — see comments in the file
```

## Examples

### 1. Agent Metadata ([`examples/01_agent_metadata.py`](examples/01_agent_metadata.py))

List agents, retrieve details (model, tools, instructions, temperature), and query agent versions.

```bash
python examples/01_agent_metadata.py
```

### 2. Runs & Token Usage ([`examples/02_runs_and_usage.py`](examples/02_runs_and_usage.py))

Create a thread, run an agent, poll for completion, then extract per-run token usage, latency, and run steps.

```bash
python examples/02_runs_and_usage.py
```

**Sample run object** (what you get back):
```json
{
  "status": "completed",
  "model": "gpt-4o-mini",
  "usage": {
    "prompt_tokens": 455,
    "completion_tokens": 103,
    "total_tokens": 558
  },
  "started_at": 1778707463,
  "completed_at": 1778707465
}
```

### 3. Tracing & Aggregate Metrics ([`examples/03_tracing_and_metrics.py`](examples/03_tracing_and_metrics.py))

Enable OpenTelemetry tracing, send agent call telemetry to Application Insights, then query aggregate metrics with KQL.

```bash
python examples/03_tracing_and_metrics.py
```

### 4. Evaluations ([`examples/04_evaluations.py`](examples/04_evaluations.py))

Create and run evaluations using the OpenAI Evals API (`score_model` evaluator), upload test data, poll for completion, retrieve per-item scores.

```bash
python examples/04_evaluations.py
```

### cURL Reference ([`examples/curl_reference.sh`](examples/curl_reference.sh))

Complete REST API reference using cURL — useful for non-Python integrations or quick testing.

## API Authentication

All examples use [DefaultAzureCredential](https://learn.microsoft.com/en-us/python/api/azure-identity/azure.identity.defaultazurecredential), which supports:

- **Azure CLI** (`az login`) — best for development
- **Managed Identity** — best for production
- **Service Principal** — best for CI/CD

The REST APIs accept either:
- **Bearer token** (scope: `https://cognitiveservices.azure.com/.default`)
- **API key** via the `api-key` header

## Key OpenTelemetry Attributes

When tracing is enabled, these attributes appear in Application Insights and can be queried with KQL:

| Attribute | Purpose |
|---|---|
| `gen_ai.agent.id` | Agent identifier |
| `gen_ai.agent.name` | Human-readable name |
| `gen_ai.usage.input_tokens` | Prompt token count |
| `gen_ai.usage.output_tokens` | Completion token count |
| `gen_ai.request.model` | Model used (e.g., `gpt-4o-mini`) |
| `gen_ai.operation.name` | `invoke_agent`, `chat`, `execute_tool` |
| `gen_ai.response.finish_reasons` | `["stop"]`, `["error"]`, etc. |

## Evaluators

The OpenAI Evals API surface supports these evaluator types:

| Type | Purpose |
|---|---|
| `score_model` | LLM-as-judge scoring (1–5 scale, custom prompt) — **tested in this repo** |
| `label_model` | LLM-as-judge classification (pass/fail, custom labels) |
| `text_similarity` | Fuzzy text matching |
| `string_check` | Exact/substring match |
| `python` | Custom Python evaluation function |
| `endpoint` | Call an external evaluation endpoint |

> **Note:** The Azure-specific `azure_ai_evaluator` type (`builtin.coherence`, `builtin.task_adherence`, etc.) is available via the Foundry portal and [Azure AI Evaluation SDK](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/cloud-evaluation), but is not supported on the OpenAI Evals REST surface as of `2025-04-01-preview`.

## RBAC Requirements

| Scenario | Role Needed | Scope |
|---|---|---|
| Query App Insights metrics | **Log Analytics Reader** | App Insights resource + linked workspace |
| Continuous evaluation | **Azure AI User** | Foundry project (assigned to project managed identity) |
| Agent CRUD / Runs | **Cognitive Services User** | AI Services resource |

## Documentation References

| Topic | URL |
|---|---|
| AI Projects Python SDK | [learn.microsoft.com](https://learn.microsoft.com/en-us/python/api/overview/azure/ai-projects-readme) |
| AI Agents Python SDK | [learn.microsoft.com](https://learn.microsoft.com/en-us/python/api/azure-ai-agents/azure.ai.agents.agentsclient) |
| Foundry Project REST API | [learn.microsoft.com](https://learn.microsoft.com/en-us/azure/ai-foundry/reference/foundry-project-rest-preview) |
| Agent Tracing (OpenTelemetry) | [learn.microsoft.com](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/trace-agents-sdk) |
| Agent Monitoring Dashboard | [learn.microsoft.com](https://learn.microsoft.com/en-us/azure/ai-foundry/observability/how-to/how-to-monitor-agents-dashboard) |
| Cloud Evaluation SDK | [learn.microsoft.com](https://learn.microsoft.com/en-us/azure/ai-foundry/how-to/develop/cloud-evaluation) |

## Known Limitations

- **No cross-agent "all runs" endpoint** — the Runs API is per-thread only. Use Application Insights KQL for aggregate views.
- **Tracing is experimental** — the `AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true` feature gate means span attributes may change in future releases.
- **Trace ingestion delay** — newly sent traces take 2–5 minutes to appear in Application Insights queries.
- **Foundry v1 API** requires agents created through the Foundry portal or v1 API; agents created via the OpenAI Assistants API appear only on the OpenAI surface.

## License

[MIT](LICENSE)
