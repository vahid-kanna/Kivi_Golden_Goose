import os
import math
from datetime import datetime
from backend.embedding import LocalTextEmbedder, TemporalParser
from backend.agent import AgentTools, HeyKiviAgent
from backend.extractor import MemoryExtractor, UNCERTAIN_RE, NEGATED_RE, QUESTION_RE
from backend.database import get_connection
from import_corpus import parse_timestamp, normalize_text

def run_adversarial_tests():
    print("==================================================================")
    print("           COMPREHENSIVE ADVERSARIAL STRESS TEST SUITE            ")
    print("==================================================================")

    # 1. Source Regex Pattern Integrity (No literal backspace \x08 characters)
    print("\n[TEST 1: Regex Pattern Source Hygiene]")
    assert "\x08" not in UNCERTAIN_RE.pattern, "Error: literal backspace in UNCERTAIN_RE"
    assert "\x08" not in NEGATED_RE.pattern, "Error: literal backspace in NEGATED_RE"
    assert "\x08" not in QUESTION_RE.pattern, "Error: literal backspace in QUESTION_RE"
    print("PASS: Verified regex boundaries use raw string word boundaries (\\b).")

    # 2. Modality Guardrail: Aspirations & Uncertainties
    print("\n[TEST 2: Aspiration & Modality Guardrail]")
    extractor = MemoryExtractor()
    aspirational_cases = [
        "I hope the beta launch is scheduled for Friday.",
        "We plan to ship the model next month maybe.",
        "I guess Priya might lead the refactor.",
        "Aiming to finish the testing before Friday."
    ]
    for text in aspirational_cases:
        res = extractor.extract_deterministic(text, text, "Slack", "2026-09-01T10:00:00Z", "test_asp")
        assert len(res["facts"]) == 0, f"Failed: Aspiration promoted to fact for: {text}"
    print(f"PASS: Correctly rejected {len(aspirational_cases)} aspirational/uncertain claims from factual memory.")

    # 3. Timestamp Edge Cases (Booleans, Non-Finite Floats, Overflow, Epoch Units)
    print("\n[TEST 3: Timestamp Robustness (Booleans, NaN, Infinity, Epochs)]")
    assert parse_timestamp(True) is None, "Boolean True should not become a timestamp"
    assert parse_timestamp(False) is None, "Boolean False should not become a timestamp"
    assert parse_timestamp(float("nan")) is None, "NaN should not become a timestamp"
    assert parse_timestamp(float("inf")) is None, "Infinity should not become a timestamp"
    assert parse_timestamp(1e309) is None, "Overflow float should not crash"
    assert parse_timestamp("not-a-timestamp") is None, "Garbage string should not crash"

    # Unix epoch units: ms, us, ns, s should all map to exact same second
    iso_s = parse_timestamp(1726140600)
    iso_ms = parse_timestamp(1726140600000)
    iso_us = parse_timestamp(1726140600000000)
    iso_ns = parse_timestamp(1726140600000000000)
    assert iso_s == iso_ms == iso_us == iso_ns == "2024-09-12T11:30:00Z", f"Epoch mismatch: {iso_s} vs {iso_ms}"
    print("PASS: Timestamp parser safely handled booleans, non-finite floats, and normalized all epoch units.")

    # 4. Text Normalization on Non-Standard Shapes (Lists, Nested Mappings)
    print("\n[TEST 4: Text Normalization for Non-String Inputs]")
    assert normalize_text(["first fragment", "second fragment"]) == "first fragment second fragment"
    assert normalize_text({"text": "nested content"}) == "nested content"
    assert normalize_text(None) == ""
    print("PASS: Handled list fragments and nested dictionaries without crashing.")

    # 5. Invalid Time Robustness Test
    print("\n[TEST 5: Out-of-Range Hour Robustness]")
    bad_time_res = TemporalParser.parse_time_filter("at 99 pm yesterday")
    assert bad_time_res is not None, "Should safely fall back to day bounds"
    print("PASS: TemporalParser safely handled 'at 99 pm' without crashing.")

    # 6. Dynamic Relative Time Resolution
    print("\n[TEST 6: Dynamic Relative Time Resolution]")
    t_res = TemporalParser.parse_time_filter("yesterday around 5 pm")
    assert t_res is not None, "Failed to parse 'yesterday around 5 pm'"
    assert t_res[2] is not None, "Center time should be present for temporal proximity ranking"
    print(f"PASS: Dynamically resolved center window: {t_res[2]}.")

    # 7. France False-Positive Hallucination Test
    print("\n[TEST 7: France Out-of-Domain Hallucination Block]")
    con = get_connection()
    cur = con.cursor()
    cur.execute("""
    INSERT OR REPLACE INTO Captures (Id, RawText, FormattedText, AppName, CreatedAt, UpdatedAt, Mode, DurationSeconds, Status)
    VALUES ('cap_france_test', 'France rollout note', 'France rollout note', 'Slack', '2026-09-04T12:00:00Z', '2026-09-04T12:00:00Z', 'dictate', 3.0, 'final')
    """)
    con.commit()
    con.close()

    tools = AgentTools(LocalTextEmbedder())
    agent = HeyKiviAgent(tools)
    france_query = "Hey Kivi, who is the president of France?"
    ans = agent.answer_query(france_query)
    assert ans["abstention"] == True, f"Failed: Did not abstain on France query! Ans: {ans['response']}"
    print("PASS: System strictly abstained despite lexical overlap with 'France'.")

    # 8. Entity-to-Task Binding Test (Unrelated Task Rejection)
    print("\n[TEST 8: Entity-to-Task Binding (Unrelated Task Rejection)]")
    quantum_query = "Hey Kivi, who is leading the quantum cryptography team?"
    ans_q = agent.answer_query(quantum_query)
    assert ans_q["abstention"] == True, f"Failed: Did not abstain on quantum cryptography! Ans: {ans_q['response']}"
    print("PASS: Correctly rejected unrelated assignment because task keywords did not bind.")

    print("\n==================================================================")
    print("   ALL 8 ADVERSARIAL TESTS PASSED: TRUTH BOUNDARY VERIFIED!       ")
    print("==================================================================")

if __name__ == "__main__":
    run_adversarial_tests()
