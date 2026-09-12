import os
import sys
import json
import uuid
import time
import argparse
from typing import List, Dict, Any, Optional
from backend.database import get_connection, init_db
from backend.extractor import MemoryExtractor

def get_field(item: Dict[str, Any], candidate_keys: List[str], default: Any = None) -> Any:
    """Extracts a field from a dictionary by checking alternative key names case-insensitively."""
    for key in candidate_keys:
        if key in item and item[key] is not None:
            return item[key]
        for actual_k in item.keys():
            if actual_k.lower() == key.lower() and item[actual_k] is not None:
                return item[actual_k]
    return default

def import_corpus(corpus_path: str, batch_size: int = 50, verbose: bool = True) -> Dict[str, Any]:
    """
    Ingests any arbitrary corpus of dictation records into Kivi memory.
    Resilient to diverse log schemas, alternative key names, and custom metadata.
    """
    init_db()
    if not os.path.exists(corpus_path):
        raise FileNotFoundError(f"Corpus file not found at: {corpus_path}")

    records = []
    with open(corpus_path, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception as e:
                    if verbose:
                        print(f"[!] Warning: Skipping invalid JSON line {line_no}: {e}")

    total = len(records)
    if verbose:
        print(f"[*] Starting ingestion of {total} records from {corpus_path}...")

    extractor = MemoryExtractor()
    con = get_connection()
    cur = con.cursor()

    t0 = time.time()
    captures_count = 0
    facts_count = 0
    prefs_count = 0
    episodes_count = 0

    for i, item in enumerate(records):
        cap_id = str(get_field(item, ["id", "capture_id", "take_id", "clienttakeid"], str(uuid.uuid4())))
        raw_text = str(get_field(item, ["raw_text", "raw", "asr_output", "asr_transcript", "transcript", "text"], ""))
        fmt_text = str(get_field(item, ["formatted_text", "formatted", "clean_text", "final_text", "text"], raw_text))
        app_name = str(get_field(item, ["app_name", "app", "application", "window_title"], "Desktop"))
        created_at = str(get_field(item, ["timestamp", "created_at", "when_utc", "date", "time"], "2026-09-01T10:00:00Z"))
        mode = str(get_field(item, ["mode"], "dictate"))
        duration = float(get_field(item, ["duration", "duration_seconds", "audio_captured_ms"], 5.0))

        # Insert capture
        cur.execute("""
        INSERT OR REPLACE INTO Captures (
            Id, RawText, FormattedText, AppName, CreatedAt, UpdatedAt, Mode, DurationSeconds, Status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'final')
        """, (cap_id, raw_text, fmt_text, app_name, created_at, created_at, mode, duration))
        captures_count += 1

        # Extract semantic memory
        extracted = extractor.extract(raw_text, fmt_text, app_name, created_at, cap_id)

        # Insert facts
        for f in extracted.get("facts", []):
            cur.execute("""
            INSERT OR REPLACE INTO FactualMemories (
                Id, Subject, Predicate, Object, Confidence, SourceCaptureId, CreatedAt, Verified
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 1)
            """, (f["id"], f["subject"], f["predicate"], f["object"], f["confidence"], f["capture_id"], f["created_at"]))
            facts_count += 1

        # Insert preferences
        for p in extracted.get("preferences", []):
            cur.execute("""
            INSERT OR REPLACE INTO UserPreferences (
                Id, Category, TargetApp, PreferenceRule, EvidenceCount, SourceCaptureId, CreatedAt
            ) VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (p["id"], p["category"], p["target_app"], p["preference_rule"], p["capture_id"], p["created_at"]))
            prefs_count += 1

        # Insert episodes
        for ep in extracted.get("episodes", []):
            cur.execute("""
            INSERT OR REPLACE INTO Episodes (
                Id, CaptureId, Timestamp, AppName, Topic, Summary, Keywords
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (ep["id"], ep["capture_id"], ep["timestamp"], ep["app_name"], ep["topic"], ep["summary"], ep["keywords"]))
            episodes_count += 1

        if (i + 1) % batch_size == 0 or (i + 1) == total:
            con.commit()
            if verbose:
                print(f"  -> Ingested {i + 1}/{total} records (Facts: {facts_count}, Episodes: {episodes_count})...")

    con.commit()
    con.close()
    elapsed = round(time.time() - t0, 2)

    stats = {
        "total_records_ingested": captures_count,
        "facts_extracted": facts_count,
        "preferences_extracted": prefs_count,
        "episodes_created": episodes_count,
        "elapsed_seconds": elapsed,
        "throughput_records_per_sec": round(captures_count / elapsed, 2) if elapsed > 0 else total
    }

    if verbose:
        print(f"[✓] Ingestion complete in {elapsed}s: {json.dumps(stats, indent=2)}")

    return stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kivi Resilient Corpus Ingestion Pipeline")
    parser.add_argument("--file", "-f", required=True, help="Path to JSONL corpus file")
    args = parser.parse_args()
    import_corpus(args.file)
