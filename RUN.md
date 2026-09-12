# RUN.md — Verification & Operation Guide

This document declares the primary review method and execution procedure for Sarvam’s evaluation agent and human reviewers.

---

## Primary Review Method: Completely Local Application & Backend

The submission is self-contained and operates completely locally on any standard machine (Linux, macOS, Windows) with Python 3.10+.

### 1. Required Runtimes & Versions
- **Python:** `3.10`, `3.11`, `3.12`, or `3.14`
- **Package Manager:** `pip` or `uv`
- **Database:** Local embedded SQLite (zero external database daemons required)

---

### 2. Environment Variables & Model Configuration
The application operates in **two modes**:
1. **Offline Zero-Dependency Mode (Default):** Runs immediately with high-speed BM25 stop-word vector retrieval and semantic grammar extraction. Requires **NO external API keys**.
2. **LLM Synthesis Mode (Optional):** To enable live LLM generation, set your API key:
   ```bash
   export OPENAI_API_KEY="your-openai-or-groq-key"
   # Optional custom endpoint:
   # export OPENAI_BASE_URL="https://api.groq.com/openai/v1"
   # export KIVI_LLM_MODEL="llama-3.3-70b-versatile"
   ```

A template is provided in `.env.example`.

---

### 3. Installation of Dependencies

In your terminal / shell:
```bash
cd Kivi_Golden_Goose
pip install -r requirements.txt
```
*(Dependencies: `fastapi`, `uvicorn`, `pydantic` — all standard lightweight libraries).*

---

### 4. Database Setup & Seeding

To initialize the schema and seed the 500-record benchmark dataset:
```bash
# 1. Reset and initialize SQLite schema
python backend/database.py

# 2. Ingest the 500-record multimodal benchmark corpus
python import_corpus.py --file data/corpus_500.jsonl
```
*Ingestion finishes in less than 1 second (~3,000 records/sec throughput).*

---

### 5. Running the Candidate Benchmark Evaluation

To execute the automated 20-case benchmark evaluation suite (testing Grounded Facts, Cross-App Episodes, Preferences, and Negative Guardrail Abstentions):

```bash
python evaluate.py
```
- **Console Output:** Prints real-time pass/fail status, end-to-end latency, and summary metrics.
- **Artifact:** Generates a detailed audit breakdown at `EVALUATION_REPORT.md`.

To run a quick interactive demonstration of the flagship use cases (temporal resolution, meeting polish, knowledge graph traversal, and guardrail refusal) in your terminal:
```bash
python test_interactive.py
```

---

### 6. Procedure for Importing Sarvam's Internal Review Corpus

When Sarvam’s automated review agent tests the system against its private 500-record user corpus:
```bash
python import_corpus.py --file /path/to/sarvam_internal_corpus.jsonl
```
The ingestion pipeline automatically:
- Parses `raw_text`, `formatted_text`, `app_name`, and `timestamp`.
- Structures episodic summaries, factual triples, and style preferences.
- Re-indexes the local hybrid vector space for immediate Hey Kivi queries.

---

### 7. Starting the Interactive Demonstration Interface

To launch the full visual workstation and API server:
```bash
python app.py
```
Open your browser at:
👉 **`http://127.0.0.1:8000`**

#### Primary Interactions to Try in the UI:
1. **Ordinary Dictation:** Enter a spoken thought in the left panel under Slack/Notion and click *Simulate Speech Ingestion*. Notice sub-15ms formatting latency and background extraction.
2. **Hey Kivi Conversational Partner:** In the center panel, ask:
   - *"Hey Kivi, who is leading the backend migration to Postgres?"* $\rightarrow$ Returns Priya with source capture ID and timestamp.
   - *"Hey Kivi, what is our site delay holding cost per day in SyncPro?"* $\rightarrow$ Returns ₹34,000/day.
   - *"Hey Kivi, who is the president of France?"* $\rightarrow$ **Triggers the Anti-Hallucination Guardrail** and refuses to invent an answer.
3. **Memory Inspector:** In the right panel, switch between *Factual Triples*, *Episodes*, and *Preferences*. Delete or curate facts with immediate visual confirmation.

---

### 8. Procedure for Resetting the System

To clear and rebuild the database with the seed corpus for a clean evaluation run:
```bash
python rebuild_database.py
```
Or click the **↺ Reset Memory** button in the top navigation bar of the web interface.
