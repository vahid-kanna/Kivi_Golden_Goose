import os
import sys
import json
import re
import math
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional, Generator, Tuple
from collections.abc import Mapping

from backend.database import get_connection, init_db
from backend.extractor import MemoryExtractor

_MISSING = object()
_NUMERIC = re.compile(r"^[+-]?\d+(?:\.\d+)?$")

def canonical_key(value: object) -> str:
    """Normalizes key name: lowercase and alphanumeric only."""
    return re.sub(r"[^a-z0-9]", "", str(value).casefold())

def flatten_mapping(obj: Mapping, prefix: str = "", depth: int = 0) -> Dict[str, Any]:
    """Recursively flattens nested dictionary up to depth 3."""
    if depth > 3:
        return {}
    out: Dict[str, Any] = {}
    for key, value in obj.items():
        path = f"{prefix}.{key}" if prefix else str(key)
        out[canonical_key(key)] = value
        out[canonical_key(path)] = value
        if isinstance(value, Mapping):
            out.update(flatten_mapping(value, path, depth + 1))
    return out

def get_field(item: Any, aliases: List[str], default: Any = None) -> Any:
    """Extracts field matching any alias across top-level and nested keys. Skips empty strings."""
    if not isinstance(item, Mapping):
        return default
    flat = flatten_mapping(item)
    for alias in aliases:
        value = flat.get(canonical_key(alias), _MISSING)
        if value is not _MISSING and value is not None:
            if isinstance(value, str) and not value.strip():
                continue
            return value
    return default

def normalize_text(value: Any) -> str:
    """Handles strings, lists of fragments, or nested dicts without crashing."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return " ".join(normalize_text(v) for v in value if v is not None).strip()
    if isinstance(value, Mapping):
        nested = get_field(value, ["text", "transcript", "content", "raw", "clean"], "")
        return normalize_text(nested)
    return str(value).strip()

def parse_timestamp(value: Any) -> Optional[str]:
    """
    Parses timestamps into normalized UTC ISO-8601 strings (YYYY-MM-DDTHH:MM:SSZ).
    Guards against booleans, non-finite floats, overflow, and arbitrary epoch units.
    """
    if value is None or value == "" or isinstance(value, bool):
        return None

    # Handle numeric epoch timestamps
    if isinstance(value, (int, float)) or _NUMERIC.fullmatch(str(value).strip()):
        try:
            number = float(value)
            if not math.isfinite(number):
                return None
            mag = abs(number)
            if mag >= 1e17:      # nanoseconds
                number /= 1_000_000_000
            elif mag >= 1e14:    # microseconds
                number /= 1_000_000
            elif mag >= 1e11:    # milliseconds
                number /= 1_000

            # Valid unix epoch range: 1970 to 2100 (0 to 4,102,444,800)
            if number < 0 or number > 4_200_000_000:
                return None

            return datetime.fromtimestamp(number, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except (ValueError, OverflowError, OSError, TypeError):
            return None

    text = str(value).strip()
    if not text:
        return None

    try:
        clean = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except (ValueError, OverflowError):
        pass

    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
            return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue

    return None

def parse_duration_seconds(item: Mapping) -> float:
    """Extracts and normalizes audio duration in seconds with bounds checks."""
    ms = get_field(item, ["audio_captured_ms", "duration_ms", "audiocapturedms"])
    if ms is not None and ms != "" and not isinstance(ms, bool):
        try:
            val = float(ms) / 1000.0
            if math.isfinite(val) and 0 <= val <= 24 * 3600:
                return round(val, 2)
        except (ValueError, TypeError):
            pass

    raw = get_field(item, ["duration_seconds", "duration", "durationseconds", "length"])
    if raw is not None and raw != "" and not isinstance(raw, bool):
        try:
            val = float(raw)
            if math.isfinite(val) and 0 <= val <= 24 * 3600:
                return round(val, 2)
        except (ValueError, TypeError):
            pass

    return 5.0

def stable_id(kind: str, capture_id: str, *parts: str) -> str:
    """Generates a deterministic SHA256 ID for idempotent ingestion."""
    material = "\x1f".join([kind, capture_id, *[p.casefold().strip() for p in parts]])
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]

def load_records(path: str) -> Generator[Tuple[int, Any], None, None]:
    """Reads JSONL lines or JSON arrays with UTF-8 BOM tolerance."""
    suffix = Path(path).suffix.casefold()
    with open(path, "r", encoding="utf-8-sig") as handle:
        if suffix == ".json":
            payload = json.load(handle)
            if isinstance(payload, dict):
                payload = payload.get("records", payload.get("data", []))
            if not isinstance(payload, list):
                raise ValueError("JSON corpus must be an array or contain a 'records' or 'data' array.")
            for index, item in enumerate(payload, 1):
                yield index, item
        else:
            for line_no, line in enumerate(handle, 1):
                line = line.strip()
                if line:
                    yield line_no, json.loads(line)

def import_corpus(corpus_path: str, batch_size: int = 50, verbose: bool = True, strict: bool = False) -> Dict[str, Any]:
    """
    Hardened, schema-tolerant, failure-isolated ingestion pipeline.
    Uses per-record SQLite SAVEPOINTs so individual bad rows do not crash the batch.
    """
    init_db()
    if not os.path.exists(corpus_path):
        raise FileNotFoundError(f"Corpus file not found at: {corpus_path}")

    raw_keys = ["raw_text", "raw_asr", "raw_asr_output", "rawasroutput", "asr_output", "asr_transcript", "transcript", "utterance", "text"]
    formatted_keys = ["formatted_text", "llm_formatted_output", "llmformattedoutput", "formatted_output", "final_text", "clean_text", "display_text", "text"]
    app_keys = ["app_name", "application_name", "application", "app", "active_app", "process_name", "window_title", "metadata.app_name"]
    time_keys = ["timestamp", "created_at", "createdAt", "event_time", "occurred_at", "when_utc", "start_time", "time", "date"]
    id_keys = ["id", "capture_id", "take_id", "client_take_id", "clienttakeid"]

    extractor = MemoryExtractor()
    con = get_connection()
    cur = con.cursor()

    t0 = time.time()
    total_records = 0
    accepted_records = 0
    rejected_records = 0
    errors: List[Dict[str, Any]] = []
    warnings: List[str] = []

    facts_count = 0
    prefs_count = 0
    episodes_count = 0

    if verbose:
        print(f"[*] Starting ingestion from {corpus_path}...")

    for line_no, item in load_records(corpus_path):
        total_records += 1
        savepoint = f"sp_{line_no}"
        cur.execute(f"SAVEPOINT {savepoint}")

        try:
            if not isinstance(item, Mapping):
                raise ValueError("Record is not a valid JSON dictionary")

            raw_text = normalize_text(get_field(item, raw_keys, ""))
            fmt_text = normalize_text(get_field(item, formatted_keys, raw_text))
            app_name = str(get_field(item, app_keys, "Desktop")).strip()
            time_raw = get_field(item, time_keys)
            created_at = parse_timestamp(time_raw)

            if not created_at:
                created_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                warnings.append(f"Line {line_no}: Missing valid timestamp. Assigned current UTC timestamp.")

            cap_id = str(get_field(item, id_keys, ""))
            if not cap_id:
                cap_id = stable_id("cap", f"{app_name}:{created_at}", raw_text or fmt_text)

            duration = parse_duration_seconds(item)
            mode = str(get_field(item, ["mode"], "dictate")).strip()

            # Reject empty captures from contaminating memory
            if not raw_text and not fmt_text:
                warnings.append(f"Line {line_no}: Empty transcript. Stored as raw capture without memory synthesis.")
                cur.execute("""
                INSERT OR IGNORE INTO Captures (Id, RawText, FormattedText, AppName, CreatedAt, UpdatedAt, Mode, DurationSeconds, Status)
                VALUES (?, '', '', ?, ?, ?, ?, ?, 'empty')
                """, (cap_id, app_name, created_at, created_at, mode, duration))
                cur.execute(f"RELEASE SAVEPOINT {savepoint}")
                accepted_records += 1
                continue

            # Insert capture
            cur.execute("""
            INSERT OR IGNORE INTO Captures (Id, RawText, FormattedText, AppName, CreatedAt, UpdatedAt, Mode, DurationSeconds, Status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'final')
            """, (cap_id, raw_text, fmt_text, app_name, created_at, created_at, mode, duration))

            # Extract memory
            extracted = extractor.extract(raw_text, fmt_text, app_name, created_at, cap_id)

            for f in extracted.get("facts", []):
                f_id = stable_id("fact", cap_id, f["subject"], f["predicate"], f["object"])
                cur.execute("""
                INSERT OR IGNORE INTO FactualMemories (Id, Subject, Predicate, Object, Confidence, SourceCaptureId, CreatedAt, Verified)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """, (f_id, f["subject"], f["predicate"], f["object"], f["confidence"], cap_id, created_at))
                facts_count += 1

            for p in extracted.get("preferences", []):
                p_id = stable_id("pref", cap_id, p["category"], p.get("target_app", ""), p["preference_rule"])
                cur.execute("""
                INSERT OR IGNORE INTO UserPreferences (Id, Category, TargetApp, PreferenceRule, EvidenceCount, SourceCaptureId, CreatedAt)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """, (p_id, p["category"], p.get("target_app"), p["preference_rule"], cap_id, created_at))
                prefs_count += 1

            for ep in extracted.get("episodes", []):
                ep_id = stable_id("ep", cap_id, ep["topic"])
                cur.execute("""
                INSERT OR IGNORE INTO Episodes (Id, CaptureId, Timestamp, AppName, Topic, Summary, Keywords)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (ep_id, cap_id, created_at, app_name, ep["topic"], ep["summary"], ep["keywords"]))
                episodes_count += 1

            cur.execute(f"RELEASE SAVEPOINT {savepoint}")
            accepted_records += 1

        except Exception as exc:
            cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            cur.execute(f"RELEASE SAVEPOINT {savepoint}")
            rejected_records += 1
            errors.append({"line": line_no, "error": type(exc).__name__, "message": str(exc)})
            if strict:
                con.close()
                raise

        if total_records % batch_size == 0:
            con.commit()

    con.commit()
    con.close()
    elapsed = round(time.time() - t0, 2)

    stats = {
        "total_records_processed": total_records,
        "accepted_records": accepted_records,
        "rejected_records": rejected_records,
        "facts_extracted": facts_count,
        "preferences_extracted": prefs_count,
        "episodes_created": episodes_count,
        "elapsed_seconds": elapsed,
        "throughput_records_per_sec": round(accepted_records / elapsed, 2) if elapsed > 0 else total_records,
        "warnings_count": len(warnings),
        "errors_count": len(errors)
    }

    if verbose:
        print(f"[✓] Ingestion complete in {elapsed}s: {json.dumps(stats, indent=2)}")

    return stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Kivi Resilient Corpus Ingestion Pipeline")
    parser.add_argument("--file", "-f", required=True, help="Path to JSONL/JSON corpus file")
    parser.add_argument("--strict", action="store_true", help="Fail on any malformed record")
    args = parser.parse_args()
    import_corpus(args.file, strict=args.strict)
