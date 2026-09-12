# System Architecture: Kivi Semantic Memory Engine & Hey Kivi Agent

## 1. Overview
The Kivi Semantic Memory Engine is a modular, high-performance cognitive architecture designed to power the "Hey Kivi" agentic assistant while maintaining zero performance overhead on real-time dictation.

## 2. Core Subsystems

### A. Dictation Ingestion Pipeline (`dictate`)
- Accepts raw ASR transcripts with metadata (timestamp, active app, duration, mode).
- Immediate local fast-formatting (phonetic replacement, punctuation).
- Persists asynchronously to SQLite (`Captures` table).
- Dispatches event to the Semantic Ingestion Worker.

### B. Background Semantic Ingestion Engine
Processes raw captures into durable structured memory:
1. **Episodic Chunking:** Stores the interaction context (AppName, Time, Action intent).
2. **Entity & Fact Extraction:**
   - Detects mentions of people, projects, dates, metrics, systems, and technical terms.
   - Discards casual fillers and noise.
   - Enforces the **Anti-Assumption Guardrail**: Only facts explicitly stated by the speaker are indexed.
3. **Preference Induction:**
   - Detects style instructions ("make it bullet points", "more concise", "executive tone") or repeated revisions.
4. **Vector & BM25 Hybrid Index:**
   - Combines semantic dense vectors with exact keyword matching (BM25) for high-precision entity recall (e.g. specific IDs, names, codes).

### C. Hey Kivi Agent & Tools (`hey_kivi`)
The agent executes user voice commands using an intentional toolset:
1. `search_user_history(query, app_filter, time_range)`: Hybrid search across episodes and captures.
2. `lookup_facts(entity, attribute)`: Exact retrieval of personal/work facts and relationships.
3. `polish_and_transform(text, target_audience, style, constraints)`: Context-aware rewriting.
4. `synthesize_episodes(topic, since)`: Multi-source temporal aggregation across disparate applications.

### D. Absolute Provenance & Hallucination Guardrail
- Every answer produced by Hey Kivi cites the exact `capture_id`, `app_name`, and `timestamp`.
- Strict **Knowledge Boundary**: If the ingested user history does not contain sufficient ground truth to answer a question, Hey Kivi explicitly responds:
  *"I don't have enough recorded context in your history to answer that reliably."*
- Complete trace inspection endpoint (`/api/traces`) for reviewer auditability.
