"""
Evaluation API Examples
=======================
Demonstrates how to programmatically create, run, and retrieve evaluation
results from Azure AI Foundry using the OpenAI Evals API surface.

Covers three evaluation patterns:
  1. Dataset evaluation — evaluate pre-computed agent outputs
  2. Agent target evaluation — evaluate a live agent against test data
  3. Trace-based evaluation — evaluate production traffic from App Insights

Usage:
    export AZURE_AI_ENDPOINT=https://<resource>.cognitiveservices.azure.com
    python examples/04_evaluations.py
"""

import os
import sys

ENDPOINT = os.environ.get("AZURE_AI_ENDPOINT")
if not ENDPOINT:
    print("Set AZURE_AI_ENDPOINT (e.g. https://<resource>.cognitiveservices.azure.com)")
    sys.exit(1)


# ── Setup ──────────────────────────────────────────────────────
print("=" * 70)
print("EVALUATION API EXAMPLES")
print("=" * 70)

try:
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
except Exception as e:
    print(f"  Connection error: {e}")
    print("  Showing code patterns instead.\n")
    oai = None


# ── Pattern 1: Dataset Evaluation ─────────────────────────────
print("─" * 70)
print("PATTERN 1: Dataset Evaluation (pre-computed outputs)")
print("─" * 70)
print("""
  Use when you already have agent outputs and want to score them.

  from openai.types.eval_create_params import DataSourceConfigCustom

  data_source_config = DataSourceConfigCustom(
      type="custom",
      item_schema={
          "type": "object",
          "properties": {
              "query":        {"type": "string"},
              "response":     {"type": "string"},
              "ground_truth": {"type": "string"},
          },
      },
  )

  testing_criteria = [
      {
          "type": "azure_ai_evaluator",
          "name": "coherence",
          "evaluator_name": "builtin.coherence",
          "initialization_parameters": {"deployment_name": "gpt-4o-mini"},
          "data_mapping": {
              "query": "{{item.query}}",
              "response": "{{item.response}}",
          },
      },
      {
          "type": "azure_ai_evaluator",
          "name": "task_adherence",
          "evaluator_name": "builtin.task_adherence",
          "data_mapping": {
              "query": "{{item.query}}",
              "response": "{{sample.output_items}}",
          },
      },
  ]

  eval_obj = oai.evals.create(
      name="my-evaluation",
      data_source_config=data_source_config,
      testing_criteria=testing_criteria,
  )

  eval_run = oai.evals.runs.create(
      eval_id=eval_obj.id,
      name="run-1",
      data_source={
          "type": "jsonl",
          "source": {"type": "file_id", "id": uploaded_file_id},
      },
  )
""")


# ── Pattern 2: Agent Target Evaluation ────────────────────────
print("─" * 70)
print("PATTERN 2: Agent Target Evaluation (live agent execution)")
print("─" * 70)
print("""
  Use when you want to run an agent against test inputs and evaluate.

  target = {
      "type": "azure_ai_agent",
      "name": "my-agent",
      "version": "1",  # omit for latest
  }

  data_source = {
      "type": "azure_ai_target_completions",
      "source": {"type": "file_id", "id": test_data_file_id},
      "input_messages": {
          "type": "template",
          "template": [
              {
                  "type": "message",
                  "role": "user",
                  "content": {"type": "input_text", "text": "{{item.query}}"},
              }
          ],
      },
      "target": target,
  }

  eval_run = oai.evals.runs.create(
      eval_id=eval_obj.id,
      name="agent-run",
      data_source=data_source,
  )
""")


# ── Pattern 3: Trace-Based Evaluation ────────────────────────
print("─" * 70)
print("PATTERN 3: Trace-Based Evaluation (production traffic)")
print("─" * 70)
print("""
  Use when you want to evaluate actual production agent interactions
  collected via OpenTelemetry tracing in Application Insights.

  # Option A: Automatic discovery by agent ID
  data_source = {
      "type": "azure_ai_traces",
      "agent_id": "my-agent:1",     # gen_ai.agent.id format
      "max_traces": 50,
      "lookback_hours": 24,
  }

  # Option B: Specific trace IDs
  data_source = {
      "type": "azure_ai_traces",
      "trace_ids": ["trace_abc", "trace_def"],
      "lookback_hours": 24,
  }

  eval_obj = oai.evals.create(
      name="trace-eval",
      data_source_config={"type": "azure_ai_source", "scenario": "traces"},
      testing_criteria=testing_criteria,
  )

  eval_run = oai.evals.runs.create(
      eval_id=eval_obj.id,
      name="trace-run",
      data_source=data_source,
  )

  Note: Requires project managed identity to have
  "Log Analytics Reader" role on Application Insights.
""")


# ── Retrieving Results ────────────────────────────────────────
print("─" * 70)
print("RETRIEVING EVALUATION RESULTS")
print("─" * 70)
print("""
  import time

  # Poll until complete
  while True:
      run = oai.evals.runs.retrieve(run_id=eval_run.id, eval_id=eval_obj.id)
      if run.status in ("completed", "failed"):
          break
      time.sleep(5)

  # Get per-item results
  items = list(oai.evals.runs.output_items.list(
      run_id=run.id, eval_id=eval_obj.id
  ))

  # Aggregate results available on the run object:
  #   run.result_counts  → {"passed": 85, "failed": 15, "total": 100}
  #   run.per_testing_criteria_results → per-evaluator breakdown
  #   run.report_url     → link to Foundry portal results page
""")


# ── Built-in Evaluators Reference ────────────────────────────
print("─" * 70)
print("BUILT-IN EVALUATORS")
print("─" * 70)

evaluators = {
    "Agent": [
        "builtin.task_adherence",
        "builtin.intent_resolution",
        "builtin.tool_call_accuracy",
    ],
    "Quality": [
        "builtin.coherence",
        "builtin.relevance",
        "builtin.fluency",
        "builtin.groundedness",
        "builtin.f1_score",
    ],
    "Safety": [
        "builtin.violence",
        "builtin.self_harm",
        "builtin.sexual",
        "builtin.hate_unfairness",
    ],
}

for category, names in evaluators.items():
    print(f"\n  {category}:")
    for name in names:
        print(f"    - {name}")


# ── Live: List Existing Evaluations ──────────────────────────
if oai:
    print("\n" + "─" * 70)
    print("EXISTING EVALUATIONS IN THIS PROJECT")
    print("─" * 70)
    try:
        evals = oai.evals.list()
        count = 0
        for ev in evals:
            count += 1
            print(f"  {ev.id} | {ev.name}")
        if count == 0:
            print("  (none)")
    except Exception as e:
        print(f"  {e}")

print()
