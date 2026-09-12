import json
import uuid
import random
from datetime import datetime, timedelta

def generate_500_corpus(output_path: str):
    """
    Generates a rich, realistic 500-record user corpus modeling an authentic 60-day
    working history of a high-velocity technical builder across multiple tools.
    Contains interconnected multi-hop narrative threads, hard invariants, and distinct entries.
    """
    random.seed(42)

    apps = [
        ("Slack", 0.35),
        ("Gmail", 0.20),
        ("VS Code", 0.15),
        ("Notion", 0.15),
        ("Linear", 0.10),
        ("Messages", 0.05)
    ]

    # Interconnected multi-hop facts & milestones
    factual_records = [
        # Sneha / RailRaksha thread
        ("Sneha is leading the frontend mobile PWA redesign for RailRaksha.", "Sneha is leading the frontend mobile PWA redesign for RailRaksha.", "Notion", "2026-08-10T10:15:00Z"),
        ("RailRaksha field pilot test with the railway track gang is scheduled for September 22.", "RailRaksha field pilot test with the railway track gang is scheduled for September 22.", "Notion", "2026-08-18T14:30:00Z"),
        ("The RailRaksha offline cache size is capped at 50MB in IndexedDB for low-end Android devices.", "The RailRaksha offline cache size is capped at 50MB in IndexedDB for low-end Android devices.", "VS Code", "2026-08-25T17:45:00Z"),
        ("RailRaksha safety alerting model achieved zero false alarms during initial simulation runs.", "RailRaksha safety alerting model achieved 0 false alarms during initial simulation runs.", "VS Code", "2026-08-27T11:00:00Z"),
        ("Sneha will review the Telugu voice model accuracy before the field pilot.", "Sneha will review the Telugu voice model accuracy before the field pilot.", "Slack", "2026-08-29T15:20:00Z"),

        # Vikram / Enterprise thread
        ("Vikram is handling the client contract negotiations for the enterprise tier.", "Vikram is handling the client contract negotiations for the enterprise tier.", "Gmail", "2026-08-12T11:20:00Z"),
        ("Tata Projects enterprise pilot contract value is finalized at Rs 12 Lakh.", "Tata Projects enterprise pilot contract value is finalized at Rs. 12 Lakh.", "Gmail", "2026-08-22T16:10:00Z"),
        ("Vikram is managing client onboarding for Afcons Infrastructure next month.", "Vikram is managing client onboarding for Afcons Infrastructure next month.", "Slack", "2026-08-28T14:00:00Z"),
        ("Afcons Infrastructure initial pilot scope is finalized at Rs 8 Lakh.", "Afcons Infrastructure initial pilot scope is finalized at Rs. 8 Lakh.", "Gmail", "2026-09-01T10:30:00Z"),

        # Priya / Backend & Cloud thread
        ("Priya is leading the backend migration to Postgres starting next Monday.", "Priya is leading the backend migration to Postgres starting next Monday.", "Slack", "2026-09-04T09:30:00Z"),
        ("The Postgres connection pool benchmark achieved 1200 requests per second under peak load.", "The Postgres connection pool benchmark achieved 1,200 requests per second under peak load.", "VS Code", "2026-09-04T15:20:00Z"),
        ("Priya is reviewing the JWT auth session refresh token implementation today.", "Priya is reviewing the JWT auth session refresh token implementation today.", "Linear", "2026-09-03T11:15:00Z"),
        ("Backend API 99th percentile latency is measured at 45ms across all query endpoints.", "Backend API 99th percentile latency is measured at 45ms across all query endpoints.", "VS Code", "2026-09-02T16:40:00Z"),

        # Aaditya / Speech & Streaming Latency
        ("Ask Aaditya to check the Sarvam Kivi streaming endpoint latency.", "Ask Aaditya to check the Sarvam Kivi streaming endpoint latency.", "Slack", "2026-09-04T16:45:00Z"),
        ("Hey Aditya, can you review the new auth flow PR before standup today?", "Hey Aditya, can you review the new auth flow PR before standup today?", "Slack", "2026-09-04T17:10:00Z"),
        ("The speech recognition TTFT is measured at 469ms with p50 latency under 950ms.", "The speech recognition TTFT is measured at 469ms with p50 latency under 950ms.", "Slack", "2026-09-01T14:00:00Z"),
        ("Aditya is spearheading the audio compression pipeline optimization for Windows.", "Aditya is spearheading the audio compression pipeline optimization for Windows.", "Linear", "2026-08-30T10:00:00Z"),

        # SyncPro Metrics & Strategy
        ("Site delay holding cost is calculated at Rs 34000 per day.", "Site delay holding cost is calculated at Rs. 34,000 per day.", "Notion", "2026-08-15T12:00:00Z"),
        ("SyncPro unit economics model shows 82% gross margins with a 4.68x LTV to CAC ratio.", "SyncPro unit economics model shows 82% gross margins with a 4.68x LTV:CAC ratio.", "Gmail", "2026-08-20T10:00:00Z"),
        ("Our customer payback period is 1.8 months based on current pilot data.", "Our customer payback period is 1.8 months based on current pilot data.", "Notion", "2026-08-24T18:00:00Z"),
        ("The beta launch date is scheduled for October 14.", "The beta launch date is scheduled for October 14.", "Gmail", "2026-08-28T09:00:00Z"),
        ("SyncPro investor pitch meeting is scheduled for Thursday.", "SyncPro investor pitch meeting is scheduled for Thursday.", "Slack", "2026-09-03T16:00:00Z"),
        ("Anita is leading user discovery interviews with site engineers for SyncPro.", "Anita is leading user discovery interviews with site engineers for SyncPro.", "Slack", "2026-08-16T11:00:00Z"),
        ("The DCMA 14-point schedule health audit deadline is Wednesday.", "The DCMA 14-point schedule health audit deadline is Wednesday.", "VS Code", "2026-09-01T09:00:00Z"),
        ("Nirmaan pre-incubation grant funding is finalized at Rs 5 Lakh.", "Nirmaan pre-incubation grant funding is finalized at Rs. 5 Lakh.", "Notion", "2026-08-11T13:00:00Z"),

        # Rohan / BSE Quantitative Alpha
        ("BSE quant engine tested over 50000 trade setups with a 2.98 profit factor.", "BSE quant engine tested over 50,000 trade setups with a 2.98 profit factor.", "VS Code", "2026-08-14T15:00:00Z"),
        ("Rohan will review the BSE alpha backtest pipeline results tomorrow morning.", "Rohan will review the BSE alpha backtest pipeline results tomorrow morning.", "Linear", "2026-08-26T14:00:00Z"),
        ("BSE corporate filing parser achieved 857000 announcement documents analyzed.", "BSE corporate filing parser achieved 857,000 announcement documents analyzed.", "VS Code", "2026-08-21T16:30:00Z"),
        ("Rohan is managing the Monte Carlo stress testing run for the trading models.", "Rohan is managing the Monte Carlo stress testing run for the trading models.", "Slack", "2026-08-27T17:00:00Z"),

        # User Preferences
        ("Always format client meeting summaries in bullet points with owners and deadlines.", "Always format client meeting summaries in bullet points with owners and deadlines.", "Notion", "2026-08-05T10:00:00Z"),
        ("Keep customer email replies concise, formal, and under three paragraphs.", "Keep customer email replies concise, formal, and under three paragraphs.", "Gmail", "2026-08-06T11:00:00Z"),
        ("In Slack messages, use short bullet points and tag relevant leads.", "In Slack messages, use short bullet points and tag relevant leads.", "Slack", "2026-08-07T14:00:00Z"),
        ("Format code review comments as constructive suggestions with code snippets.", "Format code review comments as constructive suggestions with code snippets.", "VS Code", "2026-08-08T16:00:00Z"),
        ("Prefer to format technical documentation in markdown with Mermaid diagrams.", "Prefer to format technical documentation in markdown with Mermaid diagrams.", "Notion", "2026-08-09T09:00:00Z")
    ]

    # Additional daily development tasks & team interactions (Realistic diversity)
    templates_pool = [
        ("Refactored the WebSocket reconnect handler to back off exponentially when network drops.", "VS Code"),
        ("Checking memory consumption on the audio buffer, looks stable at 45MB.", "VS Code"),
        ("Added unit tests for the token bucket rate limiter in the API gateway.", "VS Code"),
        ("The Docker build image size dropped from 1.2GB to 340MB after multi-stage compilation.", "VS Code"),
        ("Merged the pull request for SQLite WAL mode configuration, disk contention is eliminated.", "VS Code"),
        ("Fixed the date formatting bug in the export CSV worker thread.", "VS Code"),
        ("Profiling the hot path in the BM25 tokenizer, 2-gram generation is under 2 milliseconds.", "VS Code"),
        ("Upgraded FastAPI dependency to resolve the CORS preflight caching issue.", "VS Code"),
        ("The CI pipeline failed because the integration test timed out on database setup.", "VS Code"),
        ("Added comprehensive docstrings for the memory retrieval scoring function.", "VS Code"),
        ("Quick heads up everyone, deploying the hotfix for the session timeout bug in ten minutes.", "Slack"),
        ("Great job on wrapping up the sprint goals early this week team.", "Slack"),
        ("Can we do a quick five minute huddle to clarify the schema migration sequence?", "Slack"),
        ("Shared the updated Figma designs for the audio waveform in the design channel.", "Slack"),
        ("I will be offline for lunch for the next forty minutes, ping me if anything catches fire.", "Slack"),
        ("Please make sure all open pull requests are reviewed before tomorrow's code freeze.", "Slack"),
        ("Checking out the customer support ticket from yesterday regarding microphone permission.", "Slack"),
        ("Jumping on the vendor sync call now, will drop notes in the thread afterwards.", "Slack"),
        ("Reminder that tomorrow morning at 10 AM is our weekly cross-functional alignment.", "Slack"),
        ("The staging environment is back up and running after the database index rebuild.", "Slack"),
        ("Thank you for the detailed feedback on our seed pitch deck, addressing the TAM breakdown now.", "Gmail"),
        ("Attaching the revised scope of work document with the agreed delivery milestones.", "Gmail"),
        ("Following up on our conversation last Tuesday regarding pilot rollout in Chennai.", "Gmail"),
        ("Confirmed our sync for Friday at 3 PM to review the enterprise security checklist.", "Gmail"),
        ("Sharing the monthly investor update highlighting our product usage telemetry and growth.", "Gmail"),
        ("Thank you for introducing us to the logistics tech lead, reaching out to schedule an intro.", "Gmail"),
        ("Sending over the signed non-disclosure agreement for your legal team to review.", "Gmail"),
        ("Drafting the executive summary for the quarterly review meeting next week.", "Gmail"),
        ("User interviews with site supervisors revealed that noisy ambient environments cause dictation misrecognition.", "Notion"),
        ("Specifying the offline-first sync protocol: local IndexedDB writes take precedence over cloud writes.", "Notion"),
        ("Drafted the product requirement document for the multi-hop memory retrieval engine.", "Notion"),
        ("Customer journey mapping shows a 30% drop-off when hotkey chords conflict with OS defaults.", "Notion"),
        ("Synthesizing competitive teardown notes comparing local dictation latency against cloud assistants.", "Notion"),
        ("Added key user feedback quotes to the product roadmap review document.", "Notion"),
        ("The design spec requires high-contrast status badges for audio capture states.", "Notion"),
        ("Reproduced the audio clipping issue on Windows 11 with low-sample-rate USB microphones.", "Linear"),
        ("Assigned the priority bug for trailing space truncation in text pasting to the desktop track.", "Linear"),
        ("Closed ticket regarding WebSocket handshake retry limit after testing on unstable WiFi.", "Linear"),
        ("Created subtasks for the database index migration across legacy user partitions.", "Linear"),
        ("Documented reproduction steps for the hotkey conflict between Windows Game Bar and Kivi.", "Linear")
    ]

    records = []
    base_time = datetime(2026, 7, 5, 9, 0, 0)
    total_needed = 500

    # 1. Insert factual records
    for raw, fmt, app, t_str in factual_records:
        records.append({
            "id": f"cap_{len(records)+1:04d}",
            "raw_text": raw,
            "formatted_text": fmt,
            "app_name": app,
            "timestamp": t_str,
            "duration": round(random.uniform(3.0, 14.0), 1),
            "mode": "dictate"
        })

    # 2. Fill the rest of the 500 records with rich operational variety
    day_step = 0
    while len(records) < total_needed:
        tmpl, app_default = random.choice(templates_pool)
        app = app_default if random.random() < 0.7 else random.choices([a[0] for a in apps], weights=[a[1] for a in apps])[0]

        delta_hours = random.uniform(1.0, 8.0)
        rec_time = base_time + timedelta(days=day_step, hours=delta_hours)
        if rec_time > datetime(2026, 9, 4, 23, 0, 0):
            day_step = 0
            rec_time = base_time + timedelta(days=day_step, hours=delta_hours)
        else:
            day_step += random.choice([0, 0, 1])

        raw_variant = tmpl
        if random.random() < 0.35:
            raw_variant = raw_variant.replace("the ", "the <uh> ")
            raw_variant = raw_variant.replace("PR", "pr")
            raw_variant = raw_variant.replace("database", "db")

        records.append({
            "id": f"cap_{len(records)+1:04d}",
            "raw_text": raw_variant,
            "formatted_text": tmpl,
            "app_name": app,
            "timestamp": rec_time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration": round(random.uniform(2.5, 16.0), 1),
            "mode": "dictate"
        })

    # Sort strictly chronologically
    records = sorted(records, key=lambda x: x["timestamp"])

    with open(output_path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    print(f"[✓] Generated 500 authentic chronological dictation records at: {output_path}")

if __name__ == "__main__":
    generate_500_corpus("data/corpus_500.jsonl")
