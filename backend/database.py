import sqlite3
import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime

DB_PATH = os.environ.get("KIVI_DB_PATH", os.path.join(os.path.dirname(__file__), "..", "kivi_memory.db"))

def get_connection():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    con = get_connection()
    cur = con.cursor()

    # 1. Base Captures (Exact parity with Kivi desktop history.db)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS Captures (
        Id TEXT PRIMARY KEY,
        RawText TEXT NOT NULL,
        FormattedText TEXT NOT NULL,
        AppBundleId TEXT,
        AppName TEXT,
        ExePath TEXT,
        LanguageHint TEXT,
        DurationSeconds REAL,
        Mode TEXT NOT NULL DEFAULT 'dictate',
        Pinned INTEGER NOT NULL DEFAULT 0,
        Archived INTEGER NOT NULL DEFAULT 0,
        CreatedAt TEXT NOT NULL,
        UpdatedAt TEXT NOT NULL,
        RevisionCount INTEGER NOT NULL DEFAULT 0,
        Status TEXT NOT NULL DEFAULT 'final',
        UserId TEXT,
        ClientTakeId TEXT
    );
    """)

    # 2. Episodic Summary
    cur.execute("""
    CREATE TABLE IF NOT EXISTS Episodes (
        Id TEXT PRIMARY KEY,
        CaptureId TEXT NOT NULL,
        Timestamp TEXT NOT NULL,
        AppName TEXT NOT NULL,
        Topic TEXT NOT NULL,
        Summary TEXT NOT NULL,
        Keywords TEXT NOT NULL,
        FOREIGN KEY (CaptureId) REFERENCES Captures(Id) ON DELETE CASCADE
    );
    """)

    # 3. Factual Memory (Structured Knowledge Graph Triples with Forensic Provenance)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS FactualMemories (
        Id TEXT PRIMARY KEY,
        Subject TEXT NOT NULL,
        Predicate TEXT NOT NULL,
        Object TEXT NOT NULL,
        Confidence REAL NOT NULL DEFAULT 1.0,
        SourceCaptureId TEXT NOT NULL,
        CreatedAt TEXT NOT NULL,
        Verified INTEGER NOT NULL DEFAULT 1,
        FOREIGN KEY (SourceCaptureId) REFERENCES Captures(Id) ON DELETE CASCADE
    );
    """)

    # 4. User Implicit & Explicit Preferences
    cur.execute("""
    CREATE TABLE IF NOT EXISTS UserPreferences (
        Id TEXT PRIMARY KEY,
        Category TEXT NOT NULL,
        TargetApp TEXT,
        PreferenceRule TEXT NOT NULL,
        EvidenceCount INTEGER NOT NULL DEFAULT 1,
        SourceCaptureId TEXT NOT NULL,
        CreatedAt TEXT NOT NULL,
        FOREIGN KEY (SourceCaptureId) REFERENCES Captures(Id) ON DELETE CASCADE
    );
    """)

    # 5. Reviewer Audit Traces & Telemetry
    cur.execute("""
    CREATE TABLE IF NOT EXISTS AuditTraces (
        Id TEXT PRIMARY KEY,
        Query TEXT NOT NULL,
        Mode TEXT NOT NULL,
        RetrievedCaptureIds TEXT,
        RetrievedMemoryIds TEXT,
        ModelResponse TEXT NOT NULL,
        AbstentionFlag INTEGER NOT NULL DEFAULT 0,
        LatencyMs REAL NOT NULL,
        PromptTokens INTEGER NOT NULL DEFAULT 0,
        CompletionTokens INTEGER NOT NULL DEFAULT 0,
        EstimatedCostUSD REAL NOT NULL DEFAULT 0.0,
        CreatedAt TEXT NOT NULL
    );
    """)

    # Indexes for sub-millisecond retrieval
    cur.execute("CREATE INDEX IF NOT EXISTS idx_captures_time ON Captures (CreatedAt);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_captures_app ON Captures (AppName);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_facts_subj ON FactualMemories (Subject);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_episodes_time ON Episodes (Timestamp);")

    con.commit()
    con.close()

def reset_db():
    con = get_connection()
    cur = con.cursor()
    cur.execute("DROP TABLE IF EXISTS Captures;")
    cur.execute("DROP TABLE IF EXISTS Episodes;")
    cur.execute("DROP TABLE IF EXISTS FactualMemories;")
    cur.execute("DROP TABLE IF EXISTS UserPreferences;")
    cur.execute("DROP TABLE IF EXISTS AuditTraces;")
    con.commit()
    con.close()
    init_db()

if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", os.path.abspath(DB_PATH))
