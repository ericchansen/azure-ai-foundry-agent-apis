"""
OpenTelemetry Tracing → Application Insights → KQL Queries
=============================================================
Demonstrates the end-to-end workflow for getting aggregate operational
metrics (token usage, error rates, latency) from Azure AI Foundry agents:

  1. Configure OpenTelemetry to send traces to Application Insights
  2. Run instrumented agent calls (generates telemetry)
  3. Query aggregate metrics via KQL

This is how the AI Foundry monitoring dashboard gets its data — there is
no separate metrics API.

Usage:
    export AZURE_AI_ENDPOINT=https://<resource>.cognitiveservices.azure.com
    export APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=...
    export APPINSIGHTS_RESOURCE_ID=/subscriptions/.../Microsoft.Insights/components/...
    python examples/03_tracing_and_metrics.py
"""

import os
import sys
import time
from datetime import datetime

# ── Feature flags must be set BEFORE importing the instrumentor ──
os.environ.setdefault("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING", "true")
os.environ.setdefault("AZURE_TRACING_GEN_AI_CONTENT_RECORDING_ENABLED", "true")

import requests
from azure.identity import DefaultAzureCredential
from azure.monitor.opentelemetry import configure_azure_monitor

try:
    from azure.ai.agents.telemetry import AIAgentsInstrumentor
except ImportError:
    AIAgentsInstrumentor = None

ENDPOINT = os.environ.get("AZURE_AI_ENDPOINT")
CONN_STRING = os.environ.get("APPLICATIONINSIGHTS_CONNECTION_STRING")
APPI_RESOURCE_ID = os.environ.get("APPINSIGHTS_RESOURCE_ID")

if not ENDPOINT:
    print("Set AZURE_AI_ENDPOINT (e.g. https://<resource>.cognitiveservices.azure.com)")
    sys.exit(1)

API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")
credential = DefaultAzureCredential()


# ── STEP 1: Configure Tracing ──────────────────────────────────
print("=" * 70)
print("STEP 1: CONFIGURE OPENTELEMETRY TRACING")
print("=" * 70)

if CONN_STRING:
    configure_azure_monitor(
        connection_string=CONN_STRING,
        logger_name="azure.ai.agents",
    )
    print("  ✓ Azure Monitor configured")
else:
    print("  ⚠ APPLICATIONINSIGHTS_CONNECTION_STRING not set — tracing disabled")
    print("    Metrics queries will still work if App Insights has existing data")

if AIAgentsInstrumentor:
    AIAgentsInstrumentor().instrument()
    print("  ✓ AIAgentsInstrumentor active")
else:
    print("  ⚠ azure-ai-agents not installed — SDK-level tracing unavailable")


# ── STEP 2: Run Agent Calls (Generates Telemetry) ─────────────
print("\n" + "=" * 70)
print("STEP 2: RUN TRACED AGENT CALLS")
print("=" * 70)

token = credential.get_token("https://cognitiveservices.azure.com/.default").token
hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
base = f"{ENDPOINT}/openai"

# Find an agent to use
resp = requests.get(f"{base}/assistants?api-version={API_VERSION}", headers=hdrs)
resp.raise_for_status()
agents = resp.json()["data"]

if not agents:
    print("  No agents found — create one first. Skipping to metrics queries.")
else:
    agent_id = agents[0]["id"]
    print(f"  Using agent: {agents[0].get('name', agent_id)}")

    queries = [
        "What is the weather in New York?",
        "Calculate the factorial of 10.",
        "List 3 benefits of cloud computing.",
    ]

    for i, q in enumerate(queries, 1):
        print(f"\n  Run {i}: {q}")
        thread = requests.post(
            f"{base}/threads?api-version={API_VERSION}", headers=hdrs, json={}
        ).json()
        tid = thread["id"]

        requests.post(
            f"{base}/threads/{tid}/messages?api-version={API_VERSION}",
            headers=hdrs,
            json={"role": "user", "content": q},
        )

        run = requests.post(
            f"{base}/threads/{tid}/runs?api-version={API_VERSION}",
            headers=hdrs,
            json={"assistant_id": agent_id},
        ).json()
        rid = run["id"]

        terminal = ("completed", "failed", "expired", "cancelled")
        while run["status"] not in terminal:
            time.sleep(2)
            run = requests.get(
                f"{base}/threads/{tid}/runs/{rid}?api-version={API_VERSION}",
                headers=hdrs,
            ).json()

        usage = run.get("usage", {})
        latency = (run.get("completed_at") or 0) - (run.get("started_at") or 0)
        print(f"    Status:  {run['status']}")
        print(f"    Tokens:  {usage.get('total_tokens', 'N/A')}")
        print(f"    Latency: {latency}s")

    if CONN_STRING:
        print("\n  Waiting 10s for traces to flush...")
        time.sleep(10)


# ── STEP 3: Query Metrics from Application Insights ───────────
print("\n" + "=" * 70)
print("STEP 3: QUERY AGGREGATE METRICS (Application Insights KQL)")
print("=" * 70)

if not APPI_RESOURCE_ID:
    print("  APPINSIGHTS_RESOURCE_ID not set — skipping KQL queries")
    print("  Set it to: /subscriptions/{sub}/resourceGroups/{rg}")
    print("             /providers/Microsoft.Insights/components/{name}")
    sys.exit(0)

from azure.monitor.query import LogsQueryClient

logs_client = LogsQueryClient(credential)

print("\n  Note: Traces take 2-5 minutes to appear after ingestion.\n")

kql_queries = {
    "Token Usage by Model (last 24h)": """
        dependencies
        | where timestamp > ago(24h)
        | extend agent_id = tostring(customDimensions["gen_ai.agent.id"])
        | extend input_tokens = toint(customDimensions["gen_ai.usage.input_tokens"])
        | extend output_tokens = toint(customDimensions["gen_ai.usage.output_tokens"])
        | extend model = tostring(customDimensions["gen_ai.request.model"])
        | where isnotempty(model)
        | summarize
            total_runs = count(),
            total_input_tokens = sum(input_tokens),
            total_output_tokens = sum(output_tokens),
            avg_latency_ms = avg(duration),
            p95_latency_ms = percentile(duration, 95)
          by model
    """,
    "Error Rate by Agent (last 24h)": """
        dependencies
        | where timestamp > ago(24h)
        | extend agent_id = tostring(customDimensions["gen_ai.agent.id"])
        | where isnotempty(agent_id)
        | summarize
            total = count(),
            errors = countif(success == false),
            error_rate_pct = round(100.0 * countif(success == false) / count(), 2)
          by agent_id
    """,
    "Recent Agent Traces (last 1h)": """
        dependencies
        | where timestamp > ago(1h)
        | extend model = tostring(customDimensions["gen_ai.request.model"])
        | extend input_tokens = toint(customDimensions["gen_ai.usage.input_tokens"])
        | extend output_tokens = toint(customDimensions["gen_ai.usage.output_tokens"])
        | where isnotempty(model)
        | project timestamp, name, duration, success, model, input_tokens, output_tokens
        | order by timestamp desc
        | take 10
    """,
    "Hourly Token Consumption (last 24h)": """
        dependencies
        | where timestamp > ago(24h)
        | extend input_tokens = toint(customDimensions["gen_ai.usage.input_tokens"])
        | extend output_tokens = toint(customDimensions["gen_ai.usage.output_tokens"])
        | extend model = tostring(customDimensions["gen_ai.request.model"])
        | where isnotempty(model)
        | summarize
            runs = count(),
            input_tokens = sum(input_tokens),
            output_tokens = sum(output_tokens)
          by bin(timestamp, 1h), model
        | order by timestamp desc
    """,
}

for title, query in kql_queries.items():
    print(f"  {title}:")
    try:
        result = logs_client.query_resource(
            APPI_RESOURCE_ID, query=query, timespan=None
        )
        if hasattr(result, "tables") and result.tables:
            table = result.tables[0]
            if table.rows:
                cols = [c.name for c in table.columns]
                print(f"    {' | '.join(cols)}")
                print(f"    {'-' * 70}")
                for row in table.rows:
                    print(f"    {' | '.join(str(v) for v in row)}")
            else:
                print("    (no data yet — traces take 2-5 min to ingest)")
        else:
            print("    (no data)")
    except Exception as e:
        print(f"    Error: {e}")
    print()

print("=" * 70)
print("DONE")
print("=" * 70)
