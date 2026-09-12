from backend.embedding import LocalTextEmbedder
from backend.agent import AgentTools, HeyKiviAgent

tools = AgentTools(LocalTextEmbedder())
agent = HeyKiviAgent(tools)

tests = [
    # 1. Sarvam's exact prompt example: Temporal + Slack + Polish
    ("Sarvam Example: Temporal Slack & Polish",
     "Hey Kivi, find the dictation I did around 5 PM yesterday in Slack and polish it for the meeting I'm walking into."),
    
    # 2. Multi-hop relational resolution
    ("Multi-hop Knowledge Graph Traversal",
     "Hey Kivi, who is leading the frontend redesign for RailRaksha and when is the field pilot?"),

    # 3. Invariant Metric
    ("Quantitative Invariant Metric",
     "Hey Kivi, what is our site delay holding cost per day in SyncPro?"),

    # 4. Invariant Ratio
    ("SaaS Unit Economics Metric",
     "Hey Kivi, what are the gross margins and LTV to CAC ratio for SyncPro?"),

    # 5. Ambiguity detection
    ("Calibrated Clarification on Ambiguity",
     "Hey Kivi, find what I told Aditya about the review"),

    # 6. Anti-Hallucination Guardrail
    ("Anti-Hallucination Guardrail Refusal",
     "Hey Kivi, who won the 2026 FIFA World Cup final?")
]

print("==================================================================")
print("             KIVI ENGINE ADVANCED CAPABILITY TEST                 ")
print("==================================================================")

for name, query in tests:
    print(f"\n[TEST: {name}]")
    print(f"QUERY: \"{query}\"")
    res = agent.answer_query(query)
    print("RESPONSE:\n" + res["response"])
    print(f"Abstention: {res['abstention']} | Latency: {res['latency_ms']}ms")
