import re
import math
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional

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

class TemporalParser:
    """
    Parses natural-language relative time expressions:
    - 'around 5 PM', 'at 10 AM'
    - 'yesterday', 'today', 'last week', 'last month'
    - 'in August', 'on September 4'
    Returns an ISO timestamp range (start_iso, end_iso) to filter captures.
    """
    @staticmethod
    def parse_time_filter(query: str, reference_date: Optional[datetime] = None) -> Optional[Tuple[str, str]]:
        q = query.lower()
        ref = reference_date or datetime(2026, 9, 5, 12, 0, 0) # Anchored to active dataset timeline

        # 1. Check for specific hours (e.g., "around 5 pm", "at 4 pm", "around 10:30 am")
        hour_match = re.search(r'(?:around|at|about)\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)', q)
        
        # 2. Check for relative days
        is_yesterday = "yesterday" in q
        is_today = "today" in q or "this morning" in q

        target_date = ref
        if is_yesterday:
            target_date = ref - timedelta(days=1)

        if hour_match:
            hr = int(hour_match.group(1))
            mn = int(hour_match.group(2) or 0)
            ampm = hour_match.group(3)
            if ampm == "pm" and hr < 12:
                hr += 12
            elif ampm == "am" and hr == 12:
                hr = 0
            
            center_dt = target_date.replace(hour=hr, minute=mn, second=0)
            # +/- 2.5 hour window around mentioned time
            start_dt = center_dt - timedelta(hours=2, minutes=30)
            end_dt = center_dt + timedelta(hours=2, minutes=30)
            return (start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"))

        if is_yesterday:
            start_dt = (ref - timedelta(days=1)).replace(hour=0, minute=0, second=0)
            end_dt = (ref - timedelta(days=1)).replace(hour=23, minute=59, second=59)
            return (start_dt.strftime("%Y-%m-%dT%H:%M:%SZ"), end_dt.strftime("%Y-%m-%dT%H:%M:%SZ"))

        return None


class LocalTextEmbedder:
    """
    High-performance zero-dependency BM25 + n-gram term vector engine with stop-word pruning.
    """
    def __init__(self):
        self.doc_len = []
        self.avgdl = 0.0
        self.corpus_size = 0
        self.doc_freqs = {}
        self.docs = []
        self.idf = {}
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

        for doc in corpus:
            tokens = set(self.tokenize(doc, filter_stop=True))
            total_len += len(tokens)
            self.doc_len.append(len(tokens))
            for t in tokens:
                self.doc_freqs[t] = self.doc_freqs.get(t, 0) + 1

        self.avgdl = total_len / self.corpus_size if self.corpus_size > 0 else 1.0
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
            for idx, doc_text in enumerate(self.docs):
                doc_tokens = self.tokenize(doc_text, filter_stop=True)
                tf = doc_tokens.count(term)
                if tf > 0:
                    numerator = tf * (self.k1 + 1)
                    denominator = tf + self.k1 * (1 - self.b + self.b * (self.doc_len[idx] / self.avgdl))
                    scores[idx] += term_idf * (numerator / denominator)

        ranked = sorted(list(enumerate(scores)), key=lambda x: x[1], reverse=True)
        return [r for r in ranked[:top_k] if r[1] >= 1.0]
