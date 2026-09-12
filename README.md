# Kivi Semantic Memory Engine & Hey Kivi

Voice-first semantic memory architecture and agentic recall engine built for Kivi by Sarvam (Golden Goose track).

Kivi already handles real-time dictation cleanly. This repository builds its missing cognitive layer: turning fleeting spoken thoughts across Slack, Gmail, VS Code, and Notion into durable episodic context, factual knowledge graph triples, and communication preferences without adding latency to live dictation.

---

## Core System Architecture

```
                    Spoken Audio / Transcript Ingestion
                                   │
         ┌─────────────────────────┴─────────────────────────┐
         ▼                                                   ▼
 [The Fast Path: <15ms]                             [The Background Worker]
 Instant formatting & local paste                  • Episodic timeline extraction
 into active app (Slack/Gmail/Code)                • Factual triples (Subject-Predicate-Object)
                                                   • Style & register induction
                                                             │
                                                             ▼
                                                    Local SQLite Store
                                                    (Captures, Facts, Episodes)
                                                             │
                                                             ▼
                                                    Hybrid BM25 + Time Filter
                                                    (Queried when "Hey Kivi" is summoned)
```

1. **Decoupled Fast/Slow Paths:** Real-time dictation cannot tolerate model delays. Dictation formatting returns in under 15ms so typing remains instant, while semantic extraction and entity linking run asynchronously in the background.
2. **Three Memory Strata:**
   - **Episodic Context:** Cross-app timestamps, topics, and original transcripts across tools.
   - **Factual Invariants:** Hard structured triples (`Priya` -> `leads` -> `Postgres migration`, `SyncPro` -> `holding_cost` -> `Rs. 34,000/day`).
   - **User Preferences:** Communication styles observed per application (e.g. short bullets in Slack, executive brevity in Gmail).
3. **Temporal Window Resolver:** Parses relative natural-language time expressions (*"around 5 PM yesterday"*, *"last Friday"*) into ISO timestamp ranges for precise chronological filtering.
4. **Anti-Hallucination Guardrail:** Strict refusal logic when history lacks ground truth. If asked about an unrecorded event or out-of-domain topic, the engine returns *"I don't have enough recorded context in your history to answer that reliably."* rather than inventing facts.
5. **Grounded Provenance:** Every response cites its source capture ID, application context, and timestamp for complete review auditability.

---

## Repository Structure

```
Kivi_Golden_Goose/
├── POSITION_AND_VISION.md       # Part One: Positioning statement & Vision document
├── RUN.md                       # Setup, execution, evaluation, and import instructions
├── EVALUATION_REPORT.md         # Full 20-case benchmark audit report
├── app.py                       # FastAPI application serving API and local studio UI
├── import_corpus.py             # Schema-tolerant CLI ingestion pipeline
├── evaluate.py                  # Automated benchmark evaluation suite
├── rebuild_database.py          # Clean database wipe and seed script
├── test_interactive.py          # Quick terminal test of flagship scenarios
├── requirements.txt             # Minimal dependencies (fastapi, uvicorn, pydantic)
├── .env.example                 # Environment configuration template
│
├── backend/
│   ├── database.py              # SQLite schema matching Kivi history.db + memory tables
│   ├── embedding.py             # BM25 engine + natural language temporal parser
│   ├── extractor.py             # Three-tier memory extraction engine
│   ├── agent.py                 # Hey Kivi agent, multi-hop resolver & polish tool
│   └── llm.py                   # Multi-provider LLM interface (Groq/OpenAI-compatible/Offline)
│
├── data/
│   ├── generate_corpus.py       # 60-day narrative multimodal corpus generator
│   └── corpus_500.jsonl         # 500 authentic chronological dictation records
│
├── static/
│   └── index.html               # Interactive dark-mode workstation with floating dock
│
└── docs/
    └── ARCHITECTURE.md          # Detailed subsystem data flows & storage contracts
```

---

## Benchmark Results

Evaluated using `python evaluate.py` across 20 multi-vector test cases:

| Metric | Result | Benchmark Standard | Status |
| :--- | :--- | :--- | :--- |
| **Overall Benchmark Accuracy** | **100.0%** (20/20 passed) | >= 90.0% | PASS |
| **Abstention Precision (Guardrail)** | **100.0%** (6/6 unrecorded queries refused) | 100.0% | PASS |
| **Flagship Temporal Polish Scenario** | **5.0 ms** latency | < 1000 ms | PASS |
| **Corpus Ingestion Throughput** | **~2,000–3,000 records/sec** | High-throughput | PASS |
| **Database Footprint (500 records)** | **664 KB** | Compact embedded | PASS |

---

## Development & Authorship

- **Part One (Position and Vision):** Authored directly from personal product operating experience founding SyncPro (Nirmaan AI construction controls) and deploying RailRaksha (offline track worker safety PWA).
- **Part Two (Engineering & Evaluation):** All system architecture, SQLite data models, BM25 ranking algorithms, linguistic modality filters, and the 20-case evaluation harness were implemented and verified locally using standard developer CLI tooling for scaffolding and validation.
