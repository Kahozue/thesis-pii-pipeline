# thesis-pii-pipeline

Privacy-preserving PII detection pipeline for enterprise instant messaging, developed as part of a master's thesis on LLM-assisted social engineering detection in Microsoft Teams.

## Overview

The system implements a two-stage privacy filter designed to analyze internal chat conversations for social engineering risk without exposing sensitive personal data to external LLMs:

- **Stage 1** — OpenAI Privacy Filter ([opf](https://github.com/openai/privacy-filter)) detects PII spans and replaces them with typed placeholders (`[EMAIL_1]`, `[PERSON_2]`, etc.)
- **Stage 2** — Custom token mapping converts placeholders into cross-batch consistent pseudonyms (`EMAIL_A`, `PERSON_B`) so the LLM can reason about identity patterns without seeing real values

A Streamlit demo app (`pii/app.py`) and a FastAPI server (`pii/api_server.py`) expose the pipeline interactively and via REST.

## Repository Structure

```
pii/                    PII detection pipeline
  pipeline.py           Two-stage filter core
  api_server.py         FastAPI REST endpoint
  app.py                Streamlit interactive demo
  regex_baseline.py     Regex-only baseline for comparison
  eval_dataset.py       Synthetic evaluation dataset (fake PII fixtures)
  eval.py               Single-run evaluation script
  eval_concurrency.py   Concurrency / throughput benchmark
  generate_ppt_charts.py  Chart generation for presentation
  eval_charts/          Evaluation result charts and raw data
  eval_charts_oracle/   Oracle baseline evaluation results

consistency/            LLM risk-score consistency validation
  run_consistency_experiment.py   Main experiment runner
  compare_3v5.py        GPT-3.5 vs GPT-4o comparison
  build_custom_samples.py         Custom sample builder
  custom_samples.json   Hand-crafted test cases
  metrics.csv           Per-sample evaluation metrics
  raw_outputs.csv       Full LLM output log
  summary.json          Aggregated results (round 1)
  summary_v3.json       Aggregated results (round 2)

diagrams/               System architecture diagrams (SVG + PNG)
data/                   Synthetic social engineering dataset
```

## Setup

```bash
pip install -r pii/requirements.txt
```

Set `OPENAI_API_KEY` in your environment before running the pipeline or evaluation scripts.

## Running

**Interactive demo:**
```bash
cd pii && streamlit run app.py
```

**API server:**
```bash
cd pii && uvicorn api_server:app --reload
```

**Evaluation:**
```bash
cd pii && python eval.py
```

**Consistency experiment:**
```bash
cd consistency && python run_consistency_experiment.py
```

## Evaluation Results

Key results from `pii/eval_charts/`:

| Metric | Value |
|--------|-------|
| Overall F1 | see `eval_summary.json` |
| Detection rate | see `chart_detection_rate.png` |
| Latency (p50) | see `chart_latency.png` |

See `pii/eval_charts/chart_system_dashboard.png` for a full dashboard overview.

## Note on Test Data

`pii/eval_dataset.py` contains deliberately synthetic PII strings (fake names, fake API key patterns, fake addresses) used as ground-truth fixtures for the evaluation suite. These are not real credentials.
