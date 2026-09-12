# Kivi Semantic Memory Engine & Hey Kivi Agent (Golden Goose Submission)

**Candidate:** Shaik Vahid Basha (IIT Madras)  
**Track:** Golden Goose Intern (Product + Engineering + Design)  
**Repository:** Kivi by Sarvam Personal Voice-First Computing Submission  

---

## Executive Summary

This repository contains the complete end-to-end implementation of **Kivi’s Semantic Memory Engine** and the **Hey Kivi** conversational agent, fulfilling both Part One (Product Position and Vision) and Part Two (End-to-End System, 500-Record Multimodal Corpus, and Reproducible Evaluation Harness) of the Sarvam Golden Goose challenge.

Kivi bridges the divide between fleeting speech-to-text dictation and durable personal intelligence:
1. **Zero-Latency Dictation Ingestion:** Preserves sub-50ms local paste performance by decoupling immediate text injection from background memory synthesis.
2. **Three-Tier Memory Architecture:** Discretizes spoken context into **Episodic Context** (cross-app timestamps & topics), **Grounded Facts** (structured knowledge triples), and **User Preferences** (communication registers).
3. **Anti-Hallucination Guardrail:** Refuses to extrapolate or guess when evidence is absent in the user's spoken history (100% precision on out-of-domain queries).
4. **Complete Inspectability:** Every answer cites the source capture ID, application name, and timestamp.

---

## Repository Structure

```
Kivi_Golden_Goose/
├── POSITION_AND_VISION.md       # Part One: Positioning (87w) & Vision Doc (529w)
├── RUN.md                       # Exact verification & reproduction commands
├── EVALUATION_REPORT.md         # Automated 20-case benchmark audit report
├── app.py                       # FastAPI server powering API & dashboard
├── import_corpus.py             # CLI corpus ingestion pipeline (schema-tolerant)
├── evaluate.py                  # Reproducible benchmark runner
├── rebuild_database.py          # One-click clean database rebuild & corpus seeder
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment configuration template
│
├── backend/
│   ├── database.py              # SQLite schema matching Kivi history.db
│   ├── embedding.py             # BM25 + Natural Language Temporal Window Resolver
│   ├── extractor.py             # Multi-tier memory extraction pipeline
│   ├── agent.py                 # Hey Kivi agent with multi-hop graph traversal & meeting polish
│   └── llm.py                   # Multi-provider LLM interface
│
├── data/
│   ├── generate_corpus.py       # Authentic 60-day narrative corpus generator
│   └── corpus_500.jsonl         # 500 realistic multimodal dictation records
│
├── static/
│   └── index.html               # Interactive dark-mode desktop GUI studio
│
└── docs/
    └── ARCHITECTURE.md          # In-depth system design & data flows
```

---

## Key Performance Highlights

- **Benchmark Accuracy:** **100%** (20/20 test cases passed in `evaluate.py`).
- **Abstention Precision:** **100%** (6/6 ungrounded queries correctly refused without hallucination).
- **Sarvam Flagship Scenario:** Resolves *"find dictation around 5 PM yesterday in Slack and polish for meeting"* in **3.0 milliseconds**.
- **Corpus Ingestion Throughput:** **~2,000–3,000 records / second** on consumer hardware.
- **Database Footprint:** **~664 KB** for 500 comprehensive captures, structured facts, and episodes.
- **Inspectability:** 100% provenance tracking logged in `AuditTraces` table with unforgeable capture IDs.

---

## AI Disclosure & Methodology

In compliance with Sarvam's submission guidelines:
- **Product Position and Vision (Part One):** The conceptual framework, three-tier memory hierarchy, anti-assumption philosophy, and positioning statements were authored entirely from first principles and founder insights (SyncPro, RailRaksha). Generative AI was not used to synthesize or formulate the positioning thesis.
- **Engineering Execution (Part Two):** Hermes Agent and local development tools were utilized to accelerate boilerplate coding, test harness scaffolding, and benchmark automation, with all architecture, data contracts, and verification owned and reviewed by the candidate.
