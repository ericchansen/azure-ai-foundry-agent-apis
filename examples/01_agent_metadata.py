"""
Agent Metadata Retrieval
========================
Demonstrates listing agents, retrieving details (model, tools, instructions,
metadata), and querying agent versions via two API surfaces:

  1. OpenAI-compatible Assistants API (runtime agents)
  2. Foundry Project v1 API (versioned/named agents)

Usage:
    export AZURE_AI_ENDPOINT=https://<resource>.cognitiveservices.azure.com
    python examples/01_agent_metadata.py
"""

import json
import os
import sys
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
headers = {"Authorization": f"Bearer {token}"}
base = f"{ENDPOINT}/openai"


# ── 1. List All Agents ──────────────────────────────────────────
print("=" * 70)
print("LIST ALL AGENTS (OpenAI Assistants API)")
print("=" * 70)

resp = requests.get(f"{base}/assistants?api-version={API_VERSION}", headers=headers)
resp.raise_for_status()
agents = resp.json()

print(f"\nTotal agents: {len(agents['data'])}\n")

for agent in agents["data"]:
    print(f"  ID:           {agent['id']}")
    print(f"  Name:         {agent.get('name', 'N/A')}")
    print(f"  Model:        {agent['model']}")
    print(f"  Instructions: {(agent.get('instructions') or '')[:80]}...")
    print(f"  Tools:        {[t['type'] for t in agent.get('tools', [])]}")
    print(f"  Metadata:     {json.dumps(agent.get('metadata', {}))}")
    print(f"  Temperature:  {agent.get('temperature')}")
    print(f"  Top P:        {agent.get('top_p')}")
    print(f"  Created:      {datetime.fromtimestamp(agent['created_at'])}")
    print()


# ── 2. Get Specific Agent Details ───────────────────────────────
if agents["data"]:
    agent_id = agents["data"][0]["id"]
    print("=" * 70)
    print(f"AGENT DETAILS: {agent_id}")
    print("=" * 70)

    resp = requests.get(
        f"{base}/assistants/{agent_id}?api-version={API_VERSION}", headers=headers
    )
    resp.raise_for_status()
    detail = resp.json()
    print(json.dumps(detail, indent=2, default=str))


# ── 3. Foundry v1 API (Versioned Agents) ───────────────────────
print("\n" + "=" * 70)
print("FOUNDRY v1 API: VERSIONED AGENTS")
print("=" * 70)

try:
    from azure.ai.projects import AIProjectClient

    # The Foundry v1 API uses the *.services.ai.azure.com endpoint
    foundry_endpoint = ENDPOINT.replace(
        ".cognitiveservices.azure.com", ".services.ai.azure.com"
    )
    project_client = AIProjectClient(
        endpoint=foundry_endpoint, credential=credential
    )

    for agent in project_client.agents.list():
        print(f"\n  Name:    {agent.name}")
        print(f"  Version: {getattr(agent, 'version', 'N/A')}")
        print(f"  Created: {agent.created_at}")
        defn = getattr(agent, "definition", None)
        if defn:
            print(f"  Kind:    {getattr(defn, 'kind', 'N/A')}")

        # List versions
        try:
            versions = list(project_client.agents.list_versions(name=agent.name))
            print(f"  Versions: {len(versions)}")
            for v in versions:
                print(f"    v{v.version} — {v.created_at}")
        except Exception as e:
            print(f"  Versions: {e}")

except ImportError:
    print("  Install azure-ai-projects for Foundry v1 API support:")
    print('  pip install "azure-ai-projects>=2.0.0"')
except Exception as e:
    print(f"  Foundry v1 API: {e}")
    print("  (This is expected if no agents were created via the Foundry portal)")
