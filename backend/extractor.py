import re
import uuid
import json
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from backend.llm import LLMClient

# Comprehensive linguistic modality guardrail
UNCERTAIN_RE = re.compile(
    r"\b(?:hope|wish|plan(?:ning)? to|intend(?:ing)? to|expect(?:ing)? to|"
    r"maybe|might|could|should|would|possibly|probably|likely|i think|"
    r"i guess|tentative|provisional|target(?:ing)?|if\b|unless|trying to|"
    r"aim(?:ing)? to|considering|doubtful)\b",
    re.IGNORECASE
)
NEGATED_RE = re.compile(
    r"\b(?:not|never|no longer|isn't|aren't|wasn't|didn't|don't|cannot|won't)\b",
    re.IGNORECASE
)
QUESTION_RE = re.compile(
    r"^\s*(?:who|what|when|where|why|how|is|are|did|does|can|could|should)\b|\?\s*$",
    re.IGNORECASE
)

def is_asserted_claim(text: str) -> bool:
    """Strict modality guardrail: Rejects questions, negations, and uncertain/aspirational text."""
    if QUESTION_RE.search(text):
        return False
    if NEGATED_RE.search(text):
        return False
    if UNCERTAIN_RE.search(text):
        return False
    return True

class MemoryExtractor:
    """
    Three-tier memory extractor with strict modality filtering and anti-assumption guardrails.
    Rejects aspirations, questions, and negations from entering verified factual memory.
    """
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm = llm_client or LLMClient()

    def extract_deterministic(self, raw_text: str, formatted_text: str, app_name: str, timestamp: str, capture_id: str) -> Dict[str, Any]:
        text = formatted_text if formatted_text else raw_text
        facts = []
        preferences = []
        episodes = []

        # Only extract durable factual memories if the statement is an asserted fact
        if is_asserted_claim(text):
            # 1. Fact Extraction: Assignments & Ownership
            assign_patterns = [
                r'(?P<subj>[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\s+(?:is\s+handling|is\s+reviewing|will\s+review|is\s+leading|owns|is\s+working\s+on|is\s+managing|is\s+spearheading)\s+(?P<obj>[^,\.\;]+)',
                r'ask\s+(?P<subj>[A-Z][a-zA-Z]+)\s+to\s+(?P<pred>review|check|deploy|update|inspect|test)\s+(?P<obj>[^,\.\;]+)',
                r'(?P<obj>[^,\.\;]+)\s+(?:is\s+assigned\s+to|will\s+be\s+done\s+by)\s+(?P<subj>[A-Z][a-zA-Z]+)'
            ]
            for p in assign_patterns:
                for m in re.finditer(p, text, re.IGNORECASE):
                    d = m.groupdict()
                    subj = d.get('subj', '').strip()
                    obj = d.get('obj', '').strip()
                    pred = d.get('pred', 'responsible_for').strip()
                    if subj and obj and len(subj) > 1 and len(obj) > 2:
                        facts.append({
                            "id": str(uuid.uuid4()),
                            "subject": subj.title(),
                            "predicate": pred.lower(),
                            "object": obj,
                            "confidence": 0.95,
                            "capture_id": capture_id,
                            "created_at": timestamp
                        })

            # 2. Fact Extraction: Deadlines, Dates & Milestones
            date_patterns = [
                r'(?P<subj>[a-zA-Z0-9_\-\s]{3,35}?)\s+(?:is\s+scheduled\s+for|scheduled\s+for|deadline\s+is|due\s+date\s+is|launch\s+date\s+is|release\s+is)\s+(?P<obj>[A-Z][a-z]+(?:\s+\d{1,2})?|\d{1,2}(?:st|nd|rd|th)?\s+[A-Z][a-z]+|tomorrow|friday|monday|thursday|wednesday|next\s+week)',
                r'(?:due\s+by|finish\s+by|ship\s+on|release\s+on)\s+(?P<obj>[A-Z][a-z]+(?:\s+\d{1,2})?|\d{1,2}(?:st|nd|rd|th)?\s+[A-Z][a-z]+|tomorrow|friday|thursday)',
                r'(?P<subj>[a-zA-Z0-9_\-\s]{3,25}?)\s+meeting\s+(?:is\s+at|scheduled\s+for)\s+(?P<obj>\d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)|tomorrow|\w+day)'
            ]
            for p in date_patterns:
                for m in re.finditer(p, text, re.IGNORECASE):
                    d = m.groupdict()
                    subj = d.get('subj', 'Milestone').strip()
                    obj = d.get('obj', '').strip()
                    if obj and len(obj) >= 2:
                        facts.append({
                            "id": str(uuid.uuid4()),
                            "subject": subj.strip().title(),
                            "predicate": "scheduled_for",
                            "object": obj,
                            "confidence": 0.90,
                            "capture_id": capture_id,
                            "created_at": timestamp
                        })

            # 3. Fact Extraction: Metrics, Quantities, Pricing & Invariants
            metric_patterns = [
                r'(?P<subj>[a-zA-Z0-9_\-\s]{3,35}?)\s+(?:is\s+calculated\s+at|is\s+finalized\s+at|is\s+measured\s+at|is\s+capped\s+at|achieved|tested\s+over|shows|equals|costs)\s+(?P<obj>(?:Rs\.?|INR|\$|₹)?\s*\d+(?:[\.,]\d+)?\s*(?:k|cr|lakh|ms|seconds|percent|%|users|per\s+day|/day|months|ratio|factor|setups|backtests|requests\s+per\s+second)?)'
            ]
            for p in metric_patterns:
                for m in re.finditer(p, text, re.IGNORECASE):
                    d = m.groupdict()
                    subj = d.get('subj', '').strip()
                    obj = d.get('obj', '').strip()
                    if subj and obj and len(subj) > 2 and any(char.isdigit() for char in obj):
                        facts.append({
                            "id": str(uuid.uuid4()),
                            "subject": subj.strip().title(),
                            "predicate": "value_metric",
                            "object": obj.strip(),
                            "confidence": 0.90,
                            "capture_id": capture_id,
                            "created_at": timestamp
                        })

        # 4. User Preference Extraction
        pref_patterns = [
            r'(?:always|never|prefer\s+to|please\s+use)\s+(?P<rule>[^,\.;]+)',
            r'format\s+(?:as|in)\s+(?P<rule>bullet\s+points|concise|formal|markdown|table)',
            r'(?:keep\s+it|make\s+it)\s+(?P<rule>short|brief|formal|executive|punchy)'
        ]
        for p in pref_patterns:
            for m in re.finditer(p, text, re.IGNORECASE):
                rule = m.group('rule').strip()
                if rule and len(rule) > 3:
                    preferences.append({
                        "id": str(uuid.uuid4()),
                        "category": "style_formatting",
                        "target_app": app_name,
                        "preference_rule": rule,
                        "capture_id": capture_id,
                        "created_at": timestamp
                    })

        # 5. Episodic Summary
        clean_summary = text.strip().replace("\n", " ")
        if len(clean_summary) > 120:
            clean_summary = clean_summary[:117] + "..."
        
        words = [w for w in re.findall(r'\b[A-Za-z0-9_\-\.]{3,}\b', text) if w.lower() not in {'this', 'that', 'with', 'from', 'have', 'what', 'your', 'about', 'just', 'will', 'then'}]
        topic = f"{app_name}: {' '.join(words[:4])}" if words else f"{app_name} Take"
        keywords = ", ".join(list(dict.fromkeys(words[:6])))

        episodes.append({
            "id": str(uuid.uuid4()),
            "capture_id": capture_id,
            "timestamp": timestamp,
            "app_name": app_name,
            "topic": topic,
            "summary": clean_summary,
            "keywords": keywords
        })

        return {
            "facts": facts,
            "preferences": preferences,
            "episodes": episodes
        }

    def extract(self, raw_text: str, formatted_text: str, app_name: str, timestamp: str, capture_id: str, use_llm: bool = False) -> Dict[str, Any]:
        if not use_llm or not self.llm.is_configured():
            return self.extract_deterministic(raw_text, formatted_text, app_name, timestamp, capture_id)

        prompt = f"""You are Kivi's Semantic Memory Extractor.
Extract durable factual memories, user preferences, and an episodic summary.
ANTI-ASSUMPTION RULE: Extract ONLY explicitly stated facts. NEVER infer unsaid intentions. Reject questions, aspirations (e.g. 'hope', 'might', 'plan to'), and negations from facts.

Capture Metadata:
- App: {app_name}
- Timestamp: {timestamp}
- Raw ASR: {raw_text}
- Formatted Text: {formatted_text}

Respond in EXACT JSON format:
{{
  "summary": "1 concise sentence",
  "topic": "3-5 word topic",
  "keywords": ["keyword1", "keyword2"],
  "facts": [
    {{"subject": "Entity", "predicate": "relation", "object": "value"}}
  ],
  "preferences": [
    {{"category": "style", "rule": "exact stated preference"}}
  ]
}}
"""
        res = self.llm.complete([
            {"role": "system", "content": "You extract structured knowledge with zero hallucination."},
            {"role": "user", "content": prompt}
        ], temperature=0.0)

        if res["error"] or not res["content"]:
            return self.extract_deterministic(raw_text, formatted_text, app_name, timestamp, capture_id)

        try:
            raw_json = res["content"].strip()
            if "```json" in raw_json:
                raw_json = raw_json.split("```json")[1].split("```")[0].strip()
            elif "```" in raw_json:
                raw_json = raw_json.split("```")[1].split("```")[0].strip()
            data = json.loads(raw_json)

            facts = []
            for f in data.get("facts", []):
                if f.get("subject") and f.get("object"):
                    facts.append({
                        "id": str(uuid.uuid4()),
                        "subject": f["subject"],
                        "predicate": f.get("predicate", "related_to"),
                        "object": f["object"],
                        "confidence": 0.95,
                        "capture_id": capture_id,
                        "created_at": timestamp
                    })

            preferences = []
            for p in data.get("preferences", []):
                if p.get("rule"):
                    preferences.append({
                        "id": str(uuid.uuid4()),
                        "category": p.get("category", "style"),
                        "target_app": app_name,
                        "preference_rule": p["rule"],
                        "capture_id": capture_id,
                        "created_at": timestamp
                    })

            episodes = [{
                "id": str(uuid.uuid4()),
                "capture_id": capture_id,
                "timestamp": timestamp,
                "app_name": app_name,
                "topic": data.get("topic", f"{app_name} Take"),
                "summary": data.get("summary", formatted_text[:100]),
                "keywords": ", ".join(data.get("keywords", []))
            }]

            return {
                "facts": facts,
                "preferences": preferences,
                "episodes": episodes
            }
        except Exception:
            return self.extract_deterministic(raw_text, formatted_text, app_name, timestamp, capture_id)
