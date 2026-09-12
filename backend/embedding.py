import re
import math
import calendar
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple, Optional
from backend.database import get_connection

STOP_WORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'aren',
    'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by',
    'can', 'could', 'did', 'do', 'does', 'doing', 'down', 'during', 'each', 'few', 'for', 'from',
    'further', 'had', 'has', 'have', 'having', 'he', 'her', 'here', 'hers', 'herself', 'him', 'himself',
    'his', 'how', 'i', 'if', 'in', 'into', 'is', 'it', 'its', 'itself', 'just', 'me', 'more', 'most',
    'my', 'myself', 'no', 'nor', 'not', 'now', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'our',
    'ours', 'ourselves', 'out', 'over', 'own', 'same', 'she', 'should', 'so', 'some', 'such', 'than',
    'that', 'the', 'their', 'theirs', 'them', 'themselves', 'then', 'there', 'these', 'they', 'this',
    'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'we', 'were', 'what', 'when',
    'where', 'which', 'while', 'who', 'whom', 'why', 'will', 'with', 'would', 'you', 'your', 'yours',
    'hey', 'kivi', 'kivis', 'tell', 'find', 'show', 'check', 'get', 'want', 'please', 'know'
}

WEEKDAYS = {name.casefold(): i for i, name in enumerate(calendar.day_name)}

class TemporalParser:
    """
    Parses natural-language relative and absolute temporal expressions into UTC ISO bounds.
    Calculates reference time dynamically from current database state to prevent reference drift.
    """
    @staticmethod
    def get_default_reference() -> datetime:
        """Derives reference time dynamically from latest capture in SQLite, advancing to session day."""
        con = None
        try:
            con = get_connection()
            cur = con.cursor()
            cur.execute("SELECT MAX(CreatedAt) FROM Captures WHERE CreatedAt IS NOT NULL;")
            row = cur.fetchone()
            if row and row[0]:
                text = row[0].strip()
                clean = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
                latest_dt = datetime.fromisoformat(clean)
                if latest_dt.tzinfo is None:
                    latest_dt = latest_dt.replace(tzinfo=timezone.utc)
                else:
                    latest_dt = latest_dt.astimezone(timezone.utc)
                return latest_dt + timedelta(days=1)
        except Exception:
            pass
        finally:
            if con:
                try:
                    con.close()
                except Exception:
                    pass
        return datetime.now(timezone.utc)

    @staticmethod
    def parse_time_filter(query: str, reference_date: Optional[datetime] = None) -> Optional[Tuple[str, str, Optional[str]]]:
        """
        Returns (start_iso_utc, end_iso_utc, center_iso_utc).
        Safely parses 'yesterday at 5 PM', 'last Friday', 'this morning', 'last week', etc.
        """
        q = " ".join(query.casefold().split())
        ref = reference_date or TemporalParser.get_default_reference()
        if ref.tzinfo is None:
            ref = ref.replace(tzinfo=timezone.utc)

        base_day = ref
        source_matched = False

        # 1. Resolve Day Anchors
        if "day before yesterday" in q:
            base_day = ref - timedelta(days=2)
            source_matched = True
        elif "yesterday" in q:
            base_day = ref - timedelta(days=1)
            source_matched = True
        elif "tomorrow" in q:
            base_day = ref + timedelta(days=1)
            source_matched = True
        elif "today" in q or "this morning" in q or "tonight" in q:
            base_day = ref
            source_matched = True
        else:
            wd_match = re.search(r"\blast\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", q)
            if wd_match:
                target_wd = WEEKDAYS[wd_match.group(1)]
                delta = (ref.weekday() - target_wd) % 7
                if delta == 0:
                    delta = 7
                base_day = ref - timedelta(days=delta)
                source_matched = True

        # 2. Check "last week"
        if "last week" in q:
            this_monday = (ref - timedelta(days=ref.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            start_dt = this_monday - timedelta(days=7)
            end_dt = this_monday
            return (start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), None)

        # 3. Check Hour & Minute match (e.g., "around 5 pm", "at 4:30 pm")
        hm_match = re.search(r"\b(?:around|about|at)?\s*(0?[1-9]|1[0-2])(?::([0-5]\d))?\s*([ap])\.?m\.?\b", q)
        if hm_match:
            try:
                hr = int(hm_match.group(1))
                mn = int(hm_match.group(2) or 0)
                ampm = hm_match.group(3)
                if ampm == "p" and hr != 12:
                    hr += 12
                elif ampm == "a" and hr == 12:
                    hr = 0

                if 0 <= hr <= 23 and 0 <= mn <= 59:
                    center_dt = base_day.replace(hour=hr, minute=mn, second=0, microsecond=0)
                    is_fuzzy = bool(re.search(r"\b(?:around|about)\b", q))
                    radius = timedelta(minutes=120 if is_fuzzy else 30)
                    start_dt = center_dt - radius
                    end_dt = center_dt + radius
                    return (
                        start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                        center_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                    )
            except (ValueError, OverflowError):
                pass

        # 4. Day-level bounds
        if source_matched:
            start_dt = base_day.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = start_dt + timedelta(days=1)
            if "this morning" in q:
                end_dt = start_dt.replace(hour=12)
            elif "tonight" in q:
                start_dt = start_dt.replace(hour=18)
            return (start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), None)

        return None


class LocalTextEmbedder:
    """
    High-performance zero-dependency BM25 + word n-gram engine.
    Calculates correct document token lengths and caches document term frequencies.
    """
    def __init__(self):
        self.doc_len: List[int] = []
        self.avgdl: float = 0.0
        self.corpus_size: int = 0
        self.doc_freqs: Dict[str, int] = {}
        self.doc_counters: List[Counter] = []
        self.docs: List[str] = []
        self.idf: Dict[str, float] = {}
        self.k1 = 1.5
        self.b = 0.75

    def tokenize(self, text: str, filter_stop: bool = False) -> List[str]:
        text = text.lower()
        words = re.findall(r'\b[a-z0-9_\-\./@]{2,}\b', text)
        if filter_stop:
            words = [w for w in words if w not in STOP_WORDS]
        ngrams = []
        for i in range(len(words) - 1):
            ngrams.append(f"{words[i]}_{words[i+1]}")
        return words + ngrams

    def fit(self, corpus: List[str]):
        self.docs = corpus
        self.corpus_size = len(corpus)
        if self.corpus_size == 0:
            return

        total_len = 0
        self.doc_freqs = {}
        self.doc_len = []
        self.doc_counters = []

        for doc in corpus:
            tokens = self.tokenize(doc, filter_stop=True)
            t_count = len(tokens)
            total_len += t_count
            self.doc_len.append(t_count)
            counter = Counter(tokens)
            self.doc_counters.append(counter)
            for t in counter.keys():
                self.doc_freqs[t] = self.doc_freqs.get(t, 0) + 1

        self.avgdl = (total_len / self.corpus_size) if self.corpus_size > 0 else 1.0
        self.idf = {}
        for term, freq in self.doc_freqs.items():
            self.idf[term] = math.log(1 + (self.corpus_size - freq + 0.5) / (freq + 0.5))

    def score(self, query: str, top_k: int = 5) -> List[Tuple[int, float]]:
        if self.corpus_size == 0:
            return []
        q_tokens = self.tokenize(query, filter_stop=True)
        if not q_tokens:
            return []

        scores = [0.0] * self.corpus_size

        for term in q_tokens:
            if term not in self.idf:
                continue
            term_idf = self.idf[term]
            for idx in range(self.corpus_size):
                tf = self.doc_counters[idx].get(term, 0)
                if tf > 0:
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * (self.doc_len[idx] / self.avgdl))
                    scores[idx] += term_idf * (numerator / denominator)

        ranked = sorted(list(enumerate(scores)), key=lambda x: x[1], reverse=True)
        return [r for r in ranked[:top_k] if r[1] >= 1.0]
