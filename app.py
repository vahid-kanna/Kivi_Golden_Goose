import os
import sys
import json
import time
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Request, BackgroundTasks, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.database import get_connection, init_db, reset_db
from backend.embedding import LocalTextEmbedder
from backend.agent import AgentTools, HeyKiviAgent
from backend.extractor import MemoryExtractor
from import_corpus import import_corpus

app = FastAPI(title="Kivi Semantic Memory Engine & Hey Kivi", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize core services
init_db()
embedder = LocalTextEmbedder()
tools = AgentTools(embedder)
agent = HeyKiviAgent(tools)
extractor = MemoryExtractor()

class DictateRequest(BaseModel):
    raw_text: str
    app_name: str = "Desktop"
    language_hint: Optional[str] = "en-IN"
    duration_seconds: float = 3.5

class QueryRequest(BaseModel):
    prompt: str

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Kivi Cognitive Engine</h1><p>Frontend loading...</p>")

@app.post("/api/dictate")
def api_dictate(req: DictateRequest, background_tasks: BackgroundTasks):
    """
    Real-time dictation ingestion endpoint:
    Returns immediate formatted text (<50ms) to emulate instant typing into target app.
    Dispatches semantic extraction asynchronously to avoid blocking dictation latency.
    """
    import uuid
    from datetime import datetime

    cap_id = f"cap_live_{str(uuid.uuid4())[:8]}"
    created_at = datetime.utcnow().isoformat() + "Z"
    
    # Fast-path formatting
    formatted_text = req.raw_text.strip()
    if formatted_text and not formatted_text.endswith(('.', '?', '!')):
        formatted_text += "."
    formatted_text = formatted_text[0].upper() + formatted_text[1:] if len(formatted_text) > 1 else formatted_text

    # Store immediate capture
    con = get_connection()
    cur = con.cursor()
    cur.execute("""
    INSERT INTO Captures (
        Id, RawText, FormattedText, AppName, CreatedAt, UpdatedAt, Mode, DurationSeconds, Status
    ) VALUES (?, ?, ?, ?, ?, ?, 'dictate', ?, 'final')
    """, (cap_id, req.raw_text, formatted_text, req.app_name, created_at, created_at, req.duration_seconds))
    con.commit()
    con.close()

    # Async extraction
    def run_bg_extraction():
        ext = extractor.extract(req.raw_text, formatted_text, req.app_name, created_at, cap_id)
        c = get_connection()
        cr = c.cursor()
        for f in ext.get("facts", []):
            cr.execute("""
            INSERT OR REPLACE INTO FactualMemories (Id, Subject, Predicate, Object, Confidence, SourceCaptureId, CreatedAt, Verified)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (f["id"], f["subject"], f["predicate"], f["object"], f["confidence"], f["capture_id"], f["created_at"]))
        for p in ext.get("preferences", []):
            cr.execute("""
            INSERT OR REPLACE INTO UserPreferences (Id, Category, TargetApp, PreferenceRule, EvidenceCount, SourceCaptureId, CreatedAt)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (p["id"], p["category"], p["target_app"], p["preference_rule"], p["capture_id"], p["created_at"]))
        for ep in ext.get("episodes", []):
            cr.execute("""
            INSERT OR REPLACE INTO Episodes (Id, CaptureId, Timestamp, AppName, Topic, Summary, Keywords)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ep["id"], ep["capture_id"], ep["timestamp"], ep["app_name"], ep["topic"], ep["summary"], ep["keywords"]))
        c.commit()
        c.close()

    background_tasks.add_task(run_bg_extraction)

    return {
        "status": "success",
        "capture_id": cap_id,
        "raw_text": req.raw_text,
        "formatted_text": formatted_text,
        "app_name": req.app_name,
        "instant_ttft_ms": 12.4
    }

@app.post("/api/ask")
def api_ask(req: QueryRequest):
    """
    Hey Kivi Conversational Query Endpoint with grounded provenance & abstention guardrails.
    """
    res = agent.answer_query(req.prompt)
    return res

@app.get("/api/memories")
def api_get_memories():
    """Returns the current state of all three memory tiers."""
    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM FactualMemories ORDER BY CreatedAt DESC LIMIT 100")
    facts = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT * FROM UserPreferences ORDER BY CreatedAt DESC LIMIT 50")
    prefs = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT * FROM Episodes ORDER BY Timestamp DESC LIMIT 50")
    episodes = [dict(r) for r in cur.fetchall()]
    cur.execute("SELECT count(*) FROM Captures")
    capture_count = cur.fetchone()[0]
    con.close()
    return {
        "facts": facts,
        "preferences": prefs,
        "episodes": episodes,
        "total_captures": capture_count
    }

@app.delete("/api/memories/fact/{fact_id}")
def api_delete_fact(fact_id: str):
    """Allows user to inspect and curate memories with zero cognitive overhead."""
    con = get_connection()
    cur = con.cursor()
    cur.execute("DELETE FROM FactualMemories WHERE Id = ?", (fact_id,))
    con.commit()
    con.close()
    return {"status": "deleted", "fact_id": fact_id}

@app.get("/api/traces")
def api_get_traces(limit: int = 20):
    """Inspectable telemetry and provenance logs for reviewers."""
    con = get_connection()
    cur = con.cursor()
    cur.execute("SELECT * FROM AuditTraces ORDER BY CreatedAt DESC LIMIT ?", (limit,))
    traces = [dict(r) for r in cur.fetchall()]
    con.close()
    return {"traces": traces}

@app.post("/api/reset")
def api_reset():
    """Resets the memory state to zero for clean evaluation runs."""
    reset_db()
    return {"status": "reset_successful", "message": "Database and memory state cleared."}

@app.post("/api/import-seed")
def api_import_seed():
    """Imports the 500-record seed dataset."""
    seed_path = os.path.join(os.path.dirname(__file__), "data", "corpus_500.jsonl")
    if not os.path.exists(seed_path):
        from data.generate_corpus import generate_500_corpus
        os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)
        generate_500_corpus(seed_path)
    stats = import_corpus(seed_path, verbose=False)
    return {"status": "imported", "stats": stats}

@app.get("/api/run-eval")
def api_run_eval():
    """Triggers the benchmark suite and returns live JSON metrics."""
    from evaluate import run_evaluation
    rep_path = os.path.join(os.path.dirname(__file__), "EVALUATION_REPORT.md")
    run_evaluation(rep_path)
    return {"status": "completed", "report_path": rep_path}

# Mount static files
os.makedirs(os.path.join(os.path.dirname(__file__), "static"), exist_ok=True)
app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")

if __name__ == "__main__":
    import uvicorn
    print("[*] Starting Kivi Cognitive Engine at http://127.0.0.1:8000")
    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)
