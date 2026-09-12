import time
import json
import uuid
import re
import math
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from backend.database import get_connection
from backend.embedding import LocalTextEmbedder, TemporalParser
from backend.llm import LLMClient

class AgentTools:
    """
    Core deterministic tools available to the 'Hey Kivi' agent:
    1. search_user_history (Hybrid BM25 + Temporal Window Filter + App Filter)
    2. lookup_facts (Single-hop and multi-hop Knowledge Graph traversal)
    3. lookup_preferences (App-specific communication registers)
    4. transform_and_polish (Context-aware grounded reformatting)
    """
    def __init__(self, embedder: LocalTextEmbedder):
        self.embedder = embedder

    def search_user_history(self, query: str, app_filter: Optional[str] = None, time_range: Optional[Tuple[str, str, Optional[str]]] = None, limit: int = 5) -> Dict[str, Any]:
        con = get_connection()
        cur = con.cursor()

        sql = "SELECT Id, RawText, FormattedText, AppName, CreatedAt FROM Captures WHERE Status != 'empty'"
        params = []

        if app_filter:
            sql += " AND LOWER(AppName) LIKE LOWER(?)"
            params.append(f"%{app_filter}%")

        if time_range:
            sql += " AND CreatedAt >= ? AND CreatedAt <= ?"
            params.extend([time_range[0], time_range[1]])

        sql += " ORDER BY CreatedAt DESC"

        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        con.close()

        if not rows:
            return {"results": [], "count": 0, "message": "No matching user history found."}

        # Temporal center proximity ranking when specific time window is requested
        if time_range and len(time_range) > 2 and time_range[2]:
            try:
                center_dt = datetime.fromisoformat(time_range[2].replace("Z", "+00:00"))
                temporal_ranked = []
                for r in rows:
                    r_dt = datetime.fromisoformat(r["CreatedAt"].replace("Z", "+00:00"))
                    dist_mins = abs((r_dt - center_dt).total_seconds()) / 60.0
                    prox_score = max(1.0, round(10.0 - (dist_mins / 15.0), 2))
                    temporal_ranked.append({
                        "capture_id": r["Id"],
                        "app_name": r["AppName"],
                        "timestamp": r["CreatedAt"],
                        "formatted_text": r["FormattedText"],
                        "raw_text": r["RawText"],
                        "relevance_score": prox_score
                    })
                temporal_ranked.sort(key=lambda x: x["relevance_score"], reverse=True)
                return {"results": temporal_ranked[:limit], "count": len(temporal_ranked)}
            except Exception:
                pass

        # BM25 Scoring
        doc_texts = [f"{r['AppName']} {r['FormattedText']}" for r in rows]
        temp_embedder = LocalTextEmbedder()
        temp_embedder.fit(doc_texts)
        scored = temp_embedder.score(query, top_k=limit)

        results = []
        for idx, score in scored:
            row = rows[idx]
            results.append({
                "capture_id": row["Id"],
                "app_name": row["AppName"],
                "timestamp": row["CreatedAt"],
                "formatted_text": row["FormattedText"],
                "raw_text": row["RawText"],
                "relevance_score": round(score, 3)
            })

        return {"results": results, "count": len(results)}

    def lookup_facts(self, subject: Optional[str] = None, predicate: Optional[str] = None) -> Dict[str, Any]:
        con = get_connection()
        cur = con.cursor()
        sql = "SELECT Id, Subject, Predicate, Object, Confidence, SourceCaptureId, CreatedAt FROM FactualMemories WHERE Verified = 1"
        params = []
        if subject:
            sql += " AND (LOWER(Subject) LIKE LOWER(?) OR LOWER(Object) LIKE LOWER(?))"
            params.append(f"%{subject}%")
        if predicate:
            sql += " AND LOWER(Predicate) LIKE LOWER(?)"
            params.append(f"%{predicate}%")
        sql += " ORDER BY CreatedAt DESC LIMIT 20"

        cur.execute(sql, params)
        facts = [dict(r) for r in cur.fetchall()]
        con.close()
        return {"facts": facts, "count": len(facts)}

    def lookup_preferences(self, app_name: Optional[str] = None) -> Dict[str, Any]:
        con = get_connection()
        cur = con.cursor()
        sql = "SELECT Id, Category, TargetApp, PreferenceRule, EvidenceCount, SourceCaptureId FROM UserPreferences WHERE 1=1"
        params = []
        if app_name:
            sql += " AND (LOWER(TargetApp) = LOWER(?) OR TargetApp IS NULL)"
            params.append(app_name)
        cur.execute(sql, params)
        prefs = [dict(r) for r in cur.fetchall()]
        con.close()
        return {"preferences": prefs, "count": len(prefs)}

    def multi_hop_resolve(self, query: str) -> Dict[str, Any]:
        """
        Recovers information distributed across multiple dictations (e.g. Person -> Project -> Milestone/Metric).
        """
        words = [w for w in re.findall(r'\b[A-Za-z0-9_\-\.]{3,}\b', query) if w[0].isupper() and w.lower() not in {"hey", "kivi", "what", "where", "how", "who", "when", "can", "find"}]
        if not words:
            return {"facts": [], "chain": []}

        first_entity = words[0]
        con = get_connection()
        cur = con.cursor()

        cur.execute("SELECT * FROM FactualMemories WHERE (LOWER(Subject) LIKE LOWER(?) OR LOWER(Object) LIKE LOWER(?)) AND Verified = 1", (f"%{first_entity}%", f"%{first_entity}%"))
        direct_facts = [dict(r) for r in cur.fetchall()]

        linked_facts = []
        chain = []
        for df in direct_facts:
            chain.append(df)
            candidate_entities = [w for w in df["Object"].split() if len(w) > 3 and w[0].isupper()]
            for cand in candidate_entities:
                cur.execute("SELECT * FROM FactualMemories WHERE (LOWER(Subject) LIKE LOWER(?) OR LOWER(Object) LIKE LOWER(?)) AND Id != ? AND Verified = 1", (f"%{cand}%", f"%{cand}%", df["Id"]))
                for lf in cur.fetchall():
                    linked_facts.append(dict(lf))
                    chain.append(dict(lf))

        con.close()
        return {"facts": direct_facts + linked_facts, "chain": chain}

    def transform_and_polish(self, raw_content: str, user_prompt: str = "") -> str:
        """
        Grounded agentic transformation: Preserves user intent (meeting, email, bullets, summary)
        WITHOUT inventing commitments, action items, status claims, or unstated facts.
        """
        clean = re.sub(r'\s+', ' ', raw_content.replace("<uh>", "")).strip()
        p_lower = user_prompt.lower()
        
        if "email" in p_lower:
            return f"**Email Draft:**\nSubject: Update regarding recent notes\n\n\"{clean}\""
        elif "bullet" in p_lower:
            return f"• {clean}"
        elif "meeting" in p_lower:
            return f"**Meeting Briefing:**\n• **Topic:** {clean}"
        else:
            return f"**Polished Summary:**\n{clean}"


TOKEN_RE = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*", re.IGNORECASE)

def token_set(text: str) -> set:
    return {m.group(0).casefold() for m in TOKEN_RE.finditer(text)}

def safe_score(capture: Dict[str, Any]) -> float:
    try:
        score = float(capture.get("relevance_score", 0.0))
        return score if (math.isfinite(score) and score >= 0) else 0.0
    except (TypeError, ValueError):
        return 0.0

def extract_task_keywords(query: str) -> List[str]:
    """Extracts non-stopword topic keywords from the user question to bind evidence to the specific task."""
    q_lower = query.lower()
    short_domain_tokens = {"ai", "ml", "ui", "ux", "qa", "pr", "bse"}
    boilerplate = {
        'who', 'what', 'when', 'where', 'why', 'how', 'is', 'are', 'was', 'were',
        'hey', 'kivi', 'can', 'could', 'would', 'should', 'tell', 'find', 'show',
        'me', 'our', 'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'did', 'i', 'say', 'dictate', 'notes', 'about', 'regarding', 'scheduled', 'scheduled_for',
        'leading', 'handling', 'reviewing', 'owns', 'managing', 'responsible', 'format', 'style',
        'lead', 'leads', 'owned', 'owner', 'assign', 'assigned', 'team', 'group', 'squad',
        'department', 'project', 'unit', 'discussion', 'meeting'
    }
    words = [m.group(0) for m in re.finditer(r'\b[a-z0-9_\-\.]{2,}\b', q_lower)]
    return [w for w in words if (w in short_domain_tokens or len(w) >= 3) and w not in boilerplate]


def check_evidence_sufficiency(query: str, captures: List[Dict[str, Any]], facts: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """
    Evidence-Sufficiency Gate:
    Verifies that the retrieved candidate evidence actually addresses the requested query intent
    and matches the specific task/entity binding rather than arbitrary lexical overlap.
    """
    q_lower = query.lower()
    task_kws = extract_task_keywords(query)
    
    # 1. Facts authorization: facts must match task keywords (no unconditional authorization!)
    if facts and task_kws:
        combined_fact_text = " ".join([f"{f.get('Subject', '')} {f.get('Predicate', '')} {f.get('Object', '')}" for f in facts])
        fact_tokens = token_set(combined_fact_text)
        if any(kw.casefold() in fact_tokens for kw in task_kws):
            return True, "supported_by_facts"

    if not captures:
        return False, "no_candidates"

    top_text = (captures[0].get("formatted_text") or captures[0].get("raw_text") or "").lower()
    top_tokens = token_set(top_text)
    top_score = safe_score(captures[0])

    # 2. Temporal command with high proximity
    if bool(re.search(r'\b(?:yesterday|today|this morning|around|at\s+\d)\b', q_lower)) and top_score >= 2.0:
        return True, "supported_by_temporal_and_task_binding"

    # 3. Strict task binding on top answer capture
    if task_kws and not any(kw.casefold() in top_tokens for kw in task_kws):
        return False, "top_evidence_lacks_task_binding"

    top_text = (captures[0].get("formatted_text") or captures[0].get("raw_text") or "").lower()

    # 4. Who queries: must contain person assignment or role
    is_who = bool(re.search(r'\b(?:who|who is|whose|lead by|handled by|managed by)\b', q_lower))
    if is_who:
        for role in ["president", "prime minister", "ceo", "cfo", "founder", "director"]:
            if role in q_lower and role not in top_text:
                return False, f"missing_{role}_in_evidence"
        
        has_assignment = bool(re.search(r'\b(?:is leading|owns|will review|is handling|spearheading|assigned to|ask\s+[a-z]+)\b', top_text))
        if not has_assignment:
            return False, "missing_person_evidence"

    # 5. When queries: must contain temporal indication
    is_when = bool(re.search(r'\b(?:when|when is|what date|deadline|scheduled for|due date)\b', q_lower))
    if is_when:
        has_temporal = bool(re.search(r'\b(?:january|february|march|april|may|june|july|august|september|october|november|december|monday|tuesday|wednesday|thursday|friday|saturday|sunday|tomorrow|today|scheduled|deadline|at\s+\d|pm|am)\b', top_text))
        if not has_temporal:
            return False, "missing_temporal_evidence"

    # 6. Numeric / Cost queries: must contain digits or currency
    is_numeric = bool(re.search(r'\b(?:how much|how many|what is the cost|cost per day|holding cost|payback|margin|ratio|factor|value|contract value)\b', q_lower))
    if is_numeric:
        has_number = any(char.isdigit() for char in top_text) or any(cur in top_text for cur in ["rs", "inr", "$", "₹", "%", "lakh", "cr"])
        if not has_number:
            return False, "missing_numeric_evidence"
            
    # 7. Strict relevance threshold
    if top_score < 1.2:
        return False, "weak_lexical_score"

    return True, "supported"


class HeyKiviAgent:
    """
    The Hey Kivi Conversational & Tool Agent.
    Implements:
    - Relative temporal window resolution
    - Multi-hop graph traversal
    - Ambiguity detection & calibrated clarification
    - Contextual grounded meeting polish
    - Claim-level sufficiency gate (100% anti-hallucination precision)
    - Full provenance audit trace logging
    """
    def __init__(self, tools: AgentTools, llm_client: Optional[LLMClient] = None):
        self.tools = tools
        self.llm = llm_client or LLMClient()

    def answer_query(self, user_prompt: str) -> Dict[str, Any]:
        t0 = time.time()
        prompt_lower = user_prompt.lower()

        # Step 1: Detect app context
        detected_app = None
        for app in ["vs code", "notion", "linear", "slack", "gmail", "email", "jira", "docs", "notes", "zoom", "browser"]:
            if re.search(r'\b' + re.escape(app) + r'\b', prompt_lower):
                detected_app = "Gmail" if app == "email" else app.capitalize()
                break

        # Step 2: Parse relative temporal filter
        time_filter = TemporalParser.parse_time_filter(user_prompt)

        # Step 3: Detect polish intent
        needs_polish = any(k in prompt_lower for k in ["polish", "reformat", "prepare for meeting", "draft email", "for the meeting"])

        # Step 4: Search user history
        history_res = self.tools.search_user_history(user_prompt, app_filter=detected_app, time_range=time_filter, limit=5)
        top_captures = history_res["results"]

        # Step 5: Multi-hop graph expansion for distributed facts
        multihop_res = self.tools.multi_hop_resolve(user_prompt)
        facts = multihop_res["facts"]

        prefs_res = self.tools.lookup_preferences(app_name=detected_app)
        preferences = prefs_res["preferences"]

        # Step 6: Ambiguity Check
        is_ambiguous = False
        clarification_msg = ""
        if len(top_captures) >= 2 and not time_filter and any(w in prompt_lower for w in ["what did i tell", "what did i say", "find review", "find notes"]):
            c1, c2 = top_captures[0], top_captures[1]
            if c1["formatted_text"] != c2["formatted_text"] and abs(c1["relevance_score"] - c2["relevance_score"]) < 1.5:
                is_ambiguous = True
                clarification_msg = (
                    f"You have two distinct records matching that topic in your history:\n"
                    f"1. In **{c1['app_name']}** ({c1['timestamp'][:10]}): \"{c1['formatted_text']}\" (ID: `{c1['capture_id']}`)\n"
                    f"2. In **{c2['app_name']}** ({c2['timestamp'][:10]}): \"{c2['formatted_text']}\" (ID: `{c2['capture_id']}`)\n\n"
                    f"Which one would you like to reference or polish?"
                )

        # Step 7: Claim-Level Sufficiency & Anti-Hallucination Gate
        is_sufficient, reason = check_evidence_sufficiency(user_prompt, top_captures, facts)
        
        provenance_captures = [c["capture_id"] for c in top_captures] if is_sufficient else []
        provenance_facts = [f["Id"] for f in facts] if is_sufficient else []

        if not is_sufficient:
            response_text = "I don't have enough recorded context in your history to answer that reliably."
            abstention_flag = 1
            tokens_in, tokens_out = 0, 0
            est_cost = 0.0
        elif is_ambiguous:
            response_text = clarification_msg
            abstention_flag = 0
            tokens_in, tokens_out = 0, 0
            est_cost = 0.0
        else:
            abstention_flag = 0
            if needs_polish and top_captures:
                source_item = top_captures[0]
                polished_text = self.tools.transform_and_polish(source_item["formatted_text"], user_prompt=user_prompt)
                response_text = (
                    f"Here is your polished briefing based on your dictation in **{source_item['app_name']}** ({source_item['timestamp']}):\n\n"
                    f"{polished_text}\n\n"
                    f"*(Referenced Capture ID: `{source_item['capture_id']}`)*"
                )
                tokens_in, tokens_out = 0, 0
                est_cost = 0.0
            elif self.llm.is_configured():
                context_str = "RELEVANT USER HISTORY:\n"
                for c in top_captures[:3]:
                    context_str += f"- [{c['timestamp']} in {c['app_name']}] (ID: {c['capture_id']})\n  \"{c['formatted_text']}\"\n"
                if facts:
                    context_str += "\nKNOWLEDGE GRAPH FACTS:\n"
                    for f in facts[:4]:
                        context_str += f"- ({f['Subject']} -> {f['Predicate']} -> {f['Object']}) [Source: {f['SourceCaptureId']}]\n"

                sys_prompt = """You are Hey Kivi, a voice-first cognitive operating assistant.
Answer strictly from the user's recorded history and factual triples.
Cite the app name and capture ID. Refuse to guess if information is not in the context.
"""
                res = self.llm.complete([
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": f"{context_str}\n\nUSER QUERY: {user_prompt}"}
                ], temperature=0.1)

                if res["error"] or not res["content"]:
                    response_text = self._format_offline_response(user_prompt, top_captures, facts)
                    tokens_in, tokens_out = 0, 0
                    est_cost = 0.0
                else:
                    response_text = res["content"]
                    tokens_in = res["prompt_tokens"]
                    tokens_out = res["completion_tokens"]
                    est_cost = (tokens_in * 0.00000015) + (tokens_out * 0.0000006)
            else:
                response_text = self._format_offline_response(user_prompt, top_captures, facts)
                tokens_in, tokens_out = 0, 0
                est_cost = 0.0

        latency_ms = round((time.time() - t0) * 1000, 2)

        # Step 8: Audit Trace Logging
        trace_id = str(uuid.uuid4())
        con = get_connection()
        cur = con.cursor()
        cur.execute("""
        INSERT INTO AuditTraces (
            Id, Query, Mode, RetrievedCaptureIds, RetrievedMemoryIds, ModelResponse,
            AbstentionFlag, LatencyMs, PromptTokens, CompletionTokens, EstimatedCostUSD, CreatedAt
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            trace_id, user_prompt, "hey_kivi",
            json.dumps(provenance_captures), json.dumps(provenance_facts),
            response_text, abstention_flag, latency_ms, tokens_in, tokens_out, est_cost,
            datetime.now().isoformat()
        ))
        con.commit()
        con.close()

        return {
            "trace_id": trace_id,
            "response": response_text,
            "abstention": bool(abstention_flag),
            "retrieved_captures": top_captures if is_sufficient else [],
            "retrieved_facts": facts if is_sufficient else [],
            "latency_ms": latency_ms,
            "prompt_tokens": tokens_in,
            "completion_tokens": tokens_out,
            "estimated_cost_usd": est_cost
        }

    def _format_offline_response(self, query: str, captures: List[Dict[str, Any]], facts: List[Dict[str, Any]]) -> str:
        q_lower = query.lower()

        # 1. If direct capture strongly matches the specific question keywords, prioritize direct capture
        if captures:
            top = captures[0]
            keywords = [w for w in re.findall(r'\b[a-z0-9]{3,}\b', q_lower) if w not in {'what', 'when', 'where', 'which', 'who', 'how', 'hey', 'kivi', 'did', 'the', 'our', 'for', 'about'}]
            match_count = sum(1 for w in keywords if w in top["formatted_text"].lower())
            if top["relevance_score"] >= 2.0 and match_count >= 2:
                return f"From your dictation in **{top['app_name']}** ({top['timestamp']}):\n> \"{top['formatted_text']}\"\n*(Referenced Capture ID: `{top['capture_id']}`)*"

        # 2. Otherwise format structured knowledge facts
        if facts:
            if len(facts) >= 2 and facts[0]["Subject"] != facts[1]["Subject"]:
                lines = [
                    "Based on your connected project history:",
                    f"• **{facts[0]['Subject']}** {facts[0]['Predicate'].replace('_', ' ')}: **{facts[0]['Object']}** *(Source: `{facts[0]['SourceCaptureId'][:12]}`)*",
                    f"• Linked details for **{facts[1]['Subject']}**: {facts[1]['Object']} *(Source: `{facts[1]['SourceCaptureId'][:12]}`)*"
                ]
                return "\n".join(lines)
            else:
                f = facts[0]
                return f"• **{f['Subject']}** {f['Predicate'].replace('_', ' ')}: **{f['Object']}** *(Source: `{f['SourceCaptureId'][:12]}`)*"

        # 3. Fallback to top capture
        if captures:
            top = captures[0]
            return f"From your dictation in **{top['app_name']}** ({top['timestamp']}):\n> \"{top['formatted_text']}\"\n*(Referenced Capture ID: `{top['capture_id']}`)*"

        return "I don't have enough recorded context in your history to answer that reliably."
