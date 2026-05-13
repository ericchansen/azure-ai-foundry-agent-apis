"""
Agent Runs & Token Usage
========================
Demonstrates the full agent runtime lifecycle:
  - Create a thread
  - Add a user message
  - Execute an agent run
  - Poll for completion
  - Extract token usage, latency, and error info
  - List run steps (tool calls, message creation)
  - Retrieve the agent's response

Usage:
    export AZURE_AI_ENDPOINT=https://<resource>.cognitiveservices.azure.com
    python examples/02_runs_and_usage.py
"""

import json
import os
import sys
import time
from datetime import datetime

import requests
from azure.identity import DefaultAzureCredential

ENDPOINT = os.environ.get("AZURE_AI_ENDPOINT")
if not ENDPOINT:
    print("Set AZURE_AI_ENDPOINT (e.g. https://<resource>.cognitiveservices.azure.com)")
    sys.exit(1)

API_VERSION = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview")

credential = DefaultAzureCredential()
token = credential.get_token("https://cognitiveservices.azure.com/.default").token
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
base = f"{ENDPOINT}/openai"


def get_first_agent_id() -> str:
    """Get the first available agent ID, or exit with guidance."""
    resp = requests.get(f"{base}/assistants?api-version={API_VERSION}", headers=headers)
    resp.raise_for_status()
    data = resp.json()["data"]
    if not data:
        print("No agents found. Create one first:")
        print("  python -c \"import requests; ...\"")
        print("  Or use the curl_reference.sh script (step 3)")
        sys.exit(1)
    return data[0]["id"]


# ── 1. Pick an Agent ────────────────────────────────────────────
agent_id = os.environ.get("AGENT_ID") or get_first_agent_id()
print(f"Using agent: {agent_id}\n")


# ── 2. Create Thread ────────────────────────────────────────────
print("=" * 70)
print("CREATE THREAD & RUN AGENT")
print("=" * 70)

thread = requests.post(
    f"{base}/threads?api-version={API_VERSION}", headers=headers, json={}
).json()
thread_id = thread["id"]
print(f"\n  Thread: {thread_id}")


# ── 3. Add Message ──────────────────────────────────────────────
msg = requests.post(
    f"{base}/threads/{thread_id}/messages?api-version={API_VERSION}",
    headers=headers,
    json={"role": "user", "content": "Explain quantum computing in 2 sentences."},
).json()
print(f"  Message: {msg['id']}")


# ── 4. Create Run ──────────────────────────────────────────────
run = requests.post(
    f"{base}/threads/{thread_id}/runs?api-version={API_VERSION}",
    headers=headers,
    json={"assistant_id": agent_id},
).json()
run_id = run["id"]
print(f"  Run: {run_id} (status: {run['status']})")


# ── 5. Poll Until Complete ─────────────────────────────────────
terminal_states = ("completed", "failed", "expired", "cancelled")
while run["status"] not in terminal_states:
    time.sleep(2)
    run = requests.get(
        f"{base}/threads/{thread_id}/runs/{run_id}?api-version={API_VERSION}",
        headers=headers,
    ).json()
    print(f"    ... {run['status']}")


# ── 6. Display Run Details + Token Usage ───────────────────────
print("\n" + "=" * 70)
print("RUN RESULTS")
print("=" * 70)

print(f"\n  Status:           {run['status']}")
print(f"  Model:            {run['model']}")

usage = run.get("usage", {})
print(f"  Prompt Tokens:    {usage.get('prompt_tokens', 'N/A')}")
print(f"  Completion Tokens:{usage.get('completion_tokens', 'N/A')}")
print(f"  Total Tokens:     {usage.get('total_tokens', 'N/A')}")

started = run.get("started_at")
completed = run.get("completed_at")
if started and completed:
    print(f"  Latency:          {completed - started}s")

if run.get("last_error"):
    err = run["last_error"]
    print(f"  Error Code:       {err.get('code')}")
    print(f"  Error Message:    {err.get('message')}")


# ── 7. Run Steps ──────────────────────────────────────────────
print("\n" + "=" * 70)
print("RUN STEPS")
print("=" * 70)

steps = requests.get(
    f"{base}/threads/{thread_id}/runs/{run_id}/steps?api-version={API_VERSION}",
    headers=headers,
).json()

for step in steps["data"]:
    print(f"\n  Step: {step['id']}")
    print(f"    Type:   {step['type']}")
    print(f"    Status: {step['status']}")
    if step["type"] == "tool_calls":
        for tc in step.get("step_details", {}).get("tool_calls", []):
            print(f"    Tool:   {tc['type']}")


# ── 8. Messages (Agent Response) ──────────────────────────────
print("\n" + "=" * 70)
print("MESSAGES")
print("=" * 70)

msgs = requests.get(
    f"{base}/threads/{thread_id}/messages?api-version={API_VERSION}",
    headers=headers,
).json()

for m in msgs["data"]:
    role = m["role"]
    text = m["content"][0]["text"]["value"][:300] if m["content"] else "N/A"
    print(f"\n  [{role}] {text}")


# ── 9. List All Runs for Thread ───────────────────────────────
print("\n" + "=" * 70)
print("ALL RUNS FOR THIS THREAD")
print("=" * 70)

all_runs = requests.get(
    f"{base}/threads/{thread_id}/runs?api-version={API_VERSION}",
    headers=headers,
).json()

for r in all_runs["data"]:
    u = r.get("usage", {})
    tokens = u.get("total_tokens", "N/A") if u else "N/A"
    print(f"  {r['id']} | {r['status']} | tokens: {tokens}")
