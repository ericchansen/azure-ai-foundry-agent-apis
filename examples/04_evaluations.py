"""
Evaluation API — Live End-to-End Example
=========================================
Creates a dataset, runs an evaluation with a scoring model, polls for
completion, and retrieves per-item scores. Fully tested and runnable.

Supported evaluator types (OpenAI Evals surface):
  score_model, label_model, text_similarity, string_check, python, endpoint

Note: The Azure-specific `azure_ai_evaluator` type (builtin.coherence, etc.)
is available when using the Foundry portal or Azure AI Evaluation SDK, but
is NOT supported on the OpenAI Evals REST surface as of 2025-04-01-preview.

Usage:
    export AZURE_AI_ENDPOINT=https://<resource>.cognitiveservices.azure.com
    python examples/04_evaluations.py
"""

import io
import json
import os
import sys
import time

ENDPOINT = os.environ.get("AZURE_AI_ENDPOINT")
if not ENDPOINT:
    print("Set AZURE_AI_ENDPOINT (e.g. https://<resource>.cognitiveservices.azure.com)")
    sys.exit(1)


# ── Setup ──────────────────────────────────────────────────────
print("=" * 70)
print("EVALUATION API — LIVE TEST")
print("=" * 70)

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

foundry_endpoint = ENDPOINT.replace(
    ".cognitiveservices.azure.com", ".services.ai.azure.com"
)
project_client = AIProjectClient(
    endpoint=foundry_endpoint, credential=DefaultAzureCredential()
)
oai = project_client.get_openai_client()
print("  ✓ Connected to AI Foundry\n")


# ── Step 1: Upload Test Data ──────────────────────────────────
print("=" * 70)
print("STEP 1: UPLOAD TEST DATA")
print("=" * 70)

test_data = [
    {
        "query": "What is the capital of France?",
        "response": "The capital of France is Paris.",
    },
    {
        "query": "Explain photosynthesis in one sentence.",
        "response": "Photosynthesis is the process by which green plants convert "
        "light energy into chemical energy stored in glucose.",
    },
    {
        "query": "What is 25 * 17?",
        "response": "25 * 17 = 425.",
    },
]
jsonl = "\n".join(json.dumps(item) for item in test_data)

data_file = oai.files.create(
    file=("test_data.jsonl", io.BytesIO(jsonl.encode("utf-8"))),
    purpose="evals",
)
print(f"  File ID: {data_file.id}")


# ── Step 2: Create Evaluation ─────────────────────────────────
print("\n" + "=" * 70)
print("STEP 2: CREATE EVALUATION (score_model evaluator)")
print("=" * 70)

eval_obj = oai.evals.create(
    name="coherence-eval",
    data_source_config={
        "type": "custom",
        "item_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "response": {"type": "string"},
            },
        },
    },
    testing_criteria=[
        {
            "type": "score_model",
            "name": "coherence",
            "model": "gpt-4o-mini",
            "input": [
                {
                    "role": "system",
                    "content": (
                        "Rate the coherence of the response to the query on a "
                        "scale of 1-5. Return ONLY a JSON object with 'score' "
                        "(1-5) and 'reason' (brief explanation)."
                    ),
                },
                {
                    "role": "user",
                    "content": "Query: {{item.query}}\nResponse: {{item.response}}",
                },
            ],
            "pass_threshold": 3.0,
            "range": [1, 5],
        },
    ],
)
print(f"  Eval ID: {eval_obj.id}")
print(f"  Name:    {eval_obj.name}")


# ── Step 3: Run Evaluation ────────────────────────────────────
print("\n" + "=" * 70)
print("STEP 3: RUN EVALUATION")
print("=" * 70)

eval_run = oai.evals.runs.create(
    eval_id=eval_obj.id,
    name="run-1",
    data_source={
        "type": "jsonl",
        "source": {"type": "file_id", "id": data_file.id},
    },
)
print(f"  Run ID:  {eval_run.id}")
print(f"  Status:  {eval_run.status}")


# ── Step 4: Poll Until Complete ───────────────────────────────
print("\n" + "=" * 70)
print("STEP 4: POLLING")
print("=" * 70)

elapsed = 0
while eval_run.status not in ("completed", "failed", "canceled"):
    time.sleep(5)
    elapsed += 5
    eval_run = oai.evals.runs.retrieve(run_id=eval_run.id, eval_id=eval_obj.id)
    print(f"  [{elapsed}s] {eval_run.status}")
    if elapsed > 180:
        print("  Timeout — check the Foundry portal for results")
        break


# ── Step 5: Aggregate Results ─────────────────────────────────
print("\n" + "=" * 70)
print("STEP 5: RESULTS")
print("=" * 70)

print(f"  Status:        {eval_run.status}")
print(f"  Result counts: {eval_run.result_counts}")
print(f"  Per-criteria:  {eval_run.per_testing_criteria_results}")
report = getattr(eval_run, "report_url", None)
if report:
    print(f"  Report URL:    {report}")


# ── Step 6: Per-Item Scores ──────────────────────────────────
print("\n" + "=" * 70)
print("STEP 6: PER-ITEM SCORES")
print("=" * 70)

items = list(
    oai.evals.runs.output_items.list(run_id=eval_run.id, eval_id=eval_obj.id)
)
print(f"  {len(items)} items\n")

for item in items:
    results = getattr(item, "results", [])
    for r in results:
        score = getattr(r, "score", "N/A")
        passed = getattr(r, "passed", "N/A")
        name = getattr(r, "name", "unknown")
        print(f"  {name}: score={score}, passed={passed}")


# ── List All Evaluations ─────────────────────────────────────
print("\n" + "=" * 70)
print("ALL EVALUATIONS IN THIS PROJECT")
print("=" * 70)

count = 0
for ev in oai.evals.list():
    count += 1
    print(f"  {ev.id} | {ev.name}")
if count == 0:
    print("  (none)")
