#!/bin/bash
# ================================================================
# Azure AI Foundry Agent APIs — cURL Reference
# ================================================================
#
# Complete REST API reference for agent metadata, runs, token usage,
# and messages. Useful for non-Python integrations or quick testing.
#
# Prerequisites:
#   az login
#
# Usage:
#   export AZURE_AI_ENDPOINT=https://<resource>.cognitiveservices.azure.com
#   bash examples/curl_reference.sh
# ================================================================

set -euo pipefail

ENDPOINT="${AZURE_AI_ENDPOINT:?Set AZURE_AI_ENDPOINT first}"
API_VERSION="${AZURE_OPENAI_API_VERSION:-2025-04-01-preview}"
TOKEN=$(az account get-access-token \
  --resource https://cognitiveservices.azure.com \
  --query accessToken -o tsv)

AUTH="Authorization: Bearer ${TOKEN}"


# ── 1. List All Agents ──────────────────────────────────────
echo "=== 1. List Agents ==="
curl -s "${ENDPOINT}/openai/assistants?api-version=${API_VERSION}" \
  -H "${AUTH}" | python3 -m json.tool


# ── 2. Create an Agent ──────────────────────────────────────
echo -e "\n=== 2. Create Agent ==="
AGENT=$(curl -s -X POST \
  "${ENDPOINT}/openai/assistants?api-version=${API_VERSION}" \
  -H "${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "demo-agent",
    "model": "gpt-4o-mini",
    "instructions": "You are a helpful assistant. Keep answers concise.",
    "tools": [{"type": "code_interpreter"}],
    "metadata": {"purpose": "api-demo"}
  }')
AGENT_ID=$(echo "${AGENT}" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Created agent: ${AGENT_ID}"
echo "${AGENT}" | python3 -m json.tool


# ── 3. Get Agent Details ────────────────────────────────────
echo -e "\n=== 3. Get Agent Details ==="
curl -s "${ENDPOINT}/openai/assistants/${AGENT_ID}?api-version=${API_VERSION}" \
  -H "${AUTH}" | python3 -m json.tool


# ── 4. Create a Thread ──────────────────────────────────────
echo -e "\n=== 4. Create Thread ==="
THREAD=$(curl -s -X POST \
  "${ENDPOINT}/openai/threads?api-version=${API_VERSION}" \
  -H "${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{}')
THREAD_ID=$(echo "${THREAD}" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Thread: ${THREAD_ID}"


# ── 5. Add Message ──────────────────────────────────────────
echo -e "\n=== 5. Add Message ==="
curl -s -X POST \
  "${ENDPOINT}/openai/threads/${THREAD_ID}/messages?api-version=${API_VERSION}" \
  -H "${AUTH}" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "user",
    "content": "What is Azure AI Foundry? Answer in 2 sentences."
  }' | python3 -m json.tool


# ── 6. Create Run ──────────────────────────────────────────
echo -e "\n=== 6. Create Run ==="
RUN=$(curl -s -X POST \
  "${ENDPOINT}/openai/threads/${THREAD_ID}/runs?api-version=${API_VERSION}" \
  -H "${AUTH}" \
  -H "Content-Type: application/json" \
  -d "{\"assistant_id\": \"${AGENT_ID}\"}")
RUN_ID=$(echo "${RUN}" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Run: ${RUN_ID}"


# ── 7. Poll Run (includes token usage when completed) ──────
echo -e "\n=== 7. Poll Run Status ==="
STATUS="queued"
while [[ "${STATUS}" != "completed" && "${STATUS}" != "failed" && \
         "${STATUS}" != "expired" && "${STATUS}" != "cancelled" ]]; do
  sleep 2
  RUN_RESP=$(curl -s \
    "${ENDPOINT}/openai/threads/${THREAD_ID}/runs/${RUN_ID}?api-version=${API_VERSION}" \
    -H "${AUTH}")
  STATUS=$(echo "${RUN_RESP}" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
  echo "  Status: ${STATUS}"
done

echo -e "\nRun result (includes usage.prompt_tokens, usage.completion_tokens):"
echo "${RUN_RESP}" | python3 -m json.tool


# ── 8. List Run Steps ──────────────────────────────────────
echo -e "\n=== 8. Run Steps ==="
curl -s \
  "${ENDPOINT}/openai/threads/${THREAD_ID}/runs/${RUN_ID}/steps?api-version=${API_VERSION}" \
  -H "${AUTH}" | python3 -m json.tool


# ── 9. List Messages ───────────────────────────────────────
echo -e "\n=== 9. Messages ==="
curl -s \
  "${ENDPOINT}/openai/threads/${THREAD_ID}/messages?api-version=${API_VERSION}" \
  -H "${AUTH}" | python3 -m json.tool


# ── 10. List All Runs for Thread ───────────────────────────
echo -e "\n=== 10. All Runs ==="
curl -s \
  "${ENDPOINT}/openai/threads/${THREAD_ID}/runs?api-version=${API_VERSION}" \
  -H "${AUTH}" | python3 -m json.tool


# ── 11. Cleanup: Delete Agent ──────────────────────────────
echo -e "\n=== 11. Cleanup ==="
curl -s -X DELETE \
  "${ENDPOINT}/openai/assistants/${AGENT_ID}?api-version=${API_VERSION}" \
  -H "${AUTH}" | python3 -m json.tool
echo "Deleted agent: ${AGENT_ID}"

echo -e "\nDone!"
