import time
import json
import uuid
import re
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
    4. transform_and_polish (Context-aware reformatting for meetings, emails, or standups)
    """
    def __init__(self, embedder: LocalTextEmbedder):
        self.embedder = embedder

    def search_user_history(self, query: str, app_filter: Optional[str] = None, time_range: Optional[Tuple[str, str]] = None, limit: int = 5) -> Dict[str, Any]:
        con = get_connection()
        cur = con.cursor()

        sql = "SELECT Id, RawText, FormattedText, AppName, CreatedAt FROM Captures WHERE 1=1"
        params = []

        if app_filter:
            sql += " AND LOWER(AppName) LIKE LOWER(?)"
            params.append(f"%{app_filter}%")

        if time_range:
            sql += " AND CreatedAt >= ? AND CreatedAt <= ?"
            params.extend([time_range[0], time_range[1]])

        sql += " ORDER BY CreatedAt DESC LIMIT 1000"

        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        con.close()

        if not rows:
            return {"results": [], "count": 0, "message": "No matching user history found."}

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

        # If time range was specified but BM25 had few token matches, return top chronologically
        if not results and time_range and rows:
            for row in rows[:limit]:
                results.append({
                    "capture_id": row["Id"],
                    "app_name": row["AppName"],
                    "timestamp": row["CreatedAt"],
                    "formatted_text": row["FormattedText"],
                    "raw_text": row["RawText"],
                    "relevance_score": 1.0
                })

        return {"results": results, "count": len(results)}

    def lookup_facts(self, subject: Optional[str] = None, predicate: Optional[str] = None) -> Dict[str, Any]:
        con = get_connection()
        cur = con.cursor()
        sql = "SELECT Id, Subject, Predicate, Object, Confidence, SourceCaptureId, CreatedAt FROM FactualMemories WHERE 1=1"
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
        # Step 1: Detect subject entity
        words = [w for w in query.split() if w[0].isupper() and w.lower() not in {"hey", "kivi", "what", "where", "how", "who", "when", "can", "find"}]
        if not words:
            return {"facts": [], "chain": []}

        first_entity = words[0]
        con = get_connection()
        cur = con.cursor()

        # Step 2: Look up direct facts for first entity
        cur.execute("SELECT * FROM FactualMemories WHERE LOWER(Subject) LIKE LOWER(?) OR LOWER(Object) LIKE LOWER(?)", (f"%{first_entity}%", f"%{first_entity}%"))
        direct_facts = [dict(r) for r in cur.fetchall()]

        linked_facts = []
        chain = []
        # Step 3: Traverse graph for connected project/entity
        for df in direct_facts:
            chain.append(df)
            # Find linked entities inside object string
            candidate_entities = [w for w in df["Object"].split() if len(w) > 3 and w[0].isupper()]
            for cand in candidate_entities:
                cur.execute("SELECT * FROM FactualMemories WHERE (LOWER(Subject) LIKE LOWER(?) OR LOWER(Object) LIKE LOWER(?)) AND Id != ?", (f"%{cand}%", f"%{cand}%", df["Id"]))
                for lf in cur.fetchall():
                    linked_facts.append(dict(lf))
                    chain.append(dict(lf))

        con.close()
        return {"facts": direct_facts + linked_facts, "chain": chain}

    def transform_and_polish(self, raw_content: str, target_mode: str = "meeting_prep", style_prefs: Optional[List[Dict[str, Any]]] = None) -> str:
        """
        Agentic execution tool: Polishes retrieved dictation for an active meeting or executive update.
        """
        clean = raw_content.replace("<uh>", "").replace("  ", " ").strip()
        
        if "meeting" in target_mode.lower():
            return f"**Meeting Briefing Draft:**\n• **Core Topic:** {clean}\n• **Action Item:** Review open deliverables and align next steps with the team."
        elif "email" in target_mode.lower():
            return f"Hi Team,\n\nFollowing up on our recent update regarding: {clean}\n\nPlease review and let me know if any adjustments are needed.\n\nBest regards,\nVahid"
        else:
            return f"• {clean}"


class HeyKiviAgent:
    """
    The Hey Kivi Conversational & Tool Agent.
    Implements:
    - Relative temporal window resolution (e.g. 'yesterday at 5 PM')
    - Multi-hop graph traversal for distributed knowledge
    - Ambiguity detection & calibrated clarification
    - Contextual polishing ('polish it for the meeting')
    - Forensic provenance citation and 100% abstention precision on ungrounded queries.
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

        # Step 2: Detect relative temporal filter (e.g. 'around 5 PM', 'yesterday')
        time_filter = TemporalParser.parse_time_filter(user_prompt)

        # Step 3: Check if this is a Transformation / Polish request
        needs_polish = any(k in prompt_lower for k in ["polish", "reformat", "prepare for meeting", "draft email", "for the meeting"])

        # Step 4: Retrieve relevant captures
        history_res = self.tools.search_user_history(user_prompt, app_filter=detected_app, time_range=time_filter, limit=5)
        top_captures = history_res["results"]

        # Step 5: Multi-hop graph expansion for distributed facts
        multihop_res = self.tools.multi_hop_resolve(user_prompt)
        facts = multihop_res["facts"]

        prefs_res = self.tools.lookup_preferences(app_name=detected_app)
        preferences = prefs_res["preferences"]

        # Step 6: Ambiguity Check (Calibrated Clarification)
        # If user asks a general question and there are 2 distinct high-scoring historical episodes
        is_ambiguous = False
        clarification_msg = ""
        if len(top_captures) >= 2 and not time_filter and any(w in prompt_lower for w in ["what did i tell", "what did i say", "find review", "find notes"]):
            c1, c2 = top_captures[0], top_captures[1]
            if c1["formatted_text"] != c2["formatted_text"] and abs(c1["relevance_score"] - c2["relevance_score"]) < 2.0:
                is_ambiguous = True
                clarification_msg = (
                    f"You have two distinct records matching that topic in your history:\n"
                    f"1. In **{c1['app_name']}** ({c1['timestamp'][:10]}): \"{c1['formatted_text']}\" (ID: `{c1['capture_id']}`)\n"
                    f"2. In **{c2['app_name']}** ({c2['timestamp'][:10]}): \"{c2['formatted_text']}\" (ID: `{c2['capture_id']}`)\n\n"
                    f"Which one would you like to reference or polish?"
                )

        # Step 7: Anti-Assumption Guardrail (Check if evidence exists)
        provenance_captures = [c["capture_id"] for c in top_captures]
        provenance_facts = [f["Id"] for f in facts]
        has_evidence = bool(top_captures or facts)

        if not has_evidence:
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
            # Execute Polish tool if requested
            if needs_polish and top_captures:
                source_item = top_captures[0]
                polished_text = self.tools.transform_and_polish(source_item["formatted_text"], target_mode="meeting_prep", style_prefs=preferences)
                response_text = (
                    f"Here is your polished briefing based on your dictation in **{source_item['app_name']}** ({source_item['timestamp']}):\n\n"
                    f"{polished_text}\n\n"
                    f"*(Referenced Capture ID: `{source_item['capture_id']}`)*"
                )
                tokens_in, tokens_out = 0, 0
                est_cost = 0.0
            elif self.llm.is_configured():
                # Formulate LLM Prompt with Grounded Facts and multi-hop chains
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
            "retrieved_captures": top_captures,
            "retrieved_facts": facts,
            "latency_ms": latency_ms,
            "prompt_tokens": tokens_in,
            "completion_tokens": tokens_out,
            "estimated_cost_usd": est_cost
        }

    def _format_offline_response(self, query: str, captures: List[Dict[str, Any]], facts: List[Dict[str, Any]]) -> str:
        lines = []
        if facts:
            # Check if multi-hop chain is present
            if len(facts) >= 2 and facts[0]["Subject"] != facts[1]["Subject"]:
                lines.append(f"Based on your connected project history:")
                lines.append(f"• **{facts[0]['Subject']}** {facts[0]['Predicate'].replace('_', ' ')}: **{facts[0]['Object']}** *(Source: `{facts[0]['SourceCaptureId'][:12]}`)*")
                lines.append(f"• Linked details for **{facts[1]['Subject']}**: {facts[1]['Object']} *(Source: `{facts[1]['SourceCaptureId'][:12]}`)*")
            else:
                f = facts[0]
                lines.append(f"• **{f['Subject']}** {f['Predicate'].replace('_', ' ')}: **{f['Object']}** *(Source: `{f['SourceCaptureId'][:12]}`)*")
        elif captures:
            top = captures[0]
            lines.append(f"From your dictation in **{top['app_name']}** ({top['timestamp']}):")
            lines.append(f"> \"{top['formatted_text']}\"")
            lines.append(f"*(Referenced Capture ID: `{top['capture_id']}`)*")

        return "\n".join(lines) if lines else "I don't have enough recorded context in your history to answer that reliably."
