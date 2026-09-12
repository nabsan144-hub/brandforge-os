"""Week-4 regressions: robust TOOL_CALL parsing, tool-result accumulation,
per-client memory namespacing."""

# ---------- P3: tool-call parsing & accumulation ----------

def test_parse_tool_call_multiline_and_nested():
    """Regression: models pretty-print TOOL_CALL JSON across lines; the old
    non-greedy regex rejected those, so no tool ran and raw TOOL_CALL text
    leaked to the user."""
    from engines.ai_engine import AIEngine

    multi = 'Sure!\nTOOL_CALL: {\n  "name": "roi_calculator",\n  "args": {"monthly_spend": 200}\n}\nHope that helps.'
    assert AIEngine._parse_tool_call(multi) == ("roi_calculator", {"monthly_spend": 200})

    nested = 'TOOL_CALL: {"name": "x", "args": {"a": {"b": [1, 2]}}} trailing text'
    assert AIEngine._parse_tool_call(nested) == ("x", {"a": {"b": [1, 2]}})

    assert AIEngine._parse_tool_call("no directive here") is None
    assert AIEngine._parse_tool_call("TOOL_CALL: {broken json") is None


def test_tool_loop_accumulates_all_results(monkeypatch):
    """Regression: each iteration overwrote the context with only the latest
    tool result — earlier findings were dropped in multi-tool chains."""
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test_key_12345")
    from engines.ai_engine import get_engine
    eng = get_engine(provider="groq")

    responses = [
        'TOOL_CALL: {\n "name": "roi_calculator",\n "args": {"monthly_spend": 100}\n}',
        'TOOL_CALL: {"name": "roi_calculator", "args": {"monthly_spend": 200}}',
        'FINAL ANSWER',
    ]
    seen = []

    def fake(prompt, system_prompt, max_tokens):
        seen.append(prompt)
        return responses[len(seen) - 1]

    monkeypatch.setattr(eng, "_call_groq_api", fake)
    out = eng._route_generate_with_tools("the prompt", "sys", 100, True)

    assert out == "FINAL ANSWER"
    assert len(seen) == 3
    assert seen[1].count("[TOOL RESULT") == 1
    assert seen[2].count("[TOOL RESULT") == 2, "earlier tool results must be kept"


# ---------- P6: per-client memory namespacing ----------

def test_memory_namespaced_per_client():
    """Regression: get_all_memories_for_prompt used GLOBAL recent history and
    one shared long-term file — client A's confidential notes leaked into
    client B's prompts (verified in audit)."""
    from modules.memory_manager import MemoryManager
    mm = MemoryManager()
    mm.add_chat("user", "SECRET-A: client alpha launch numbers", client_id="client_a")
    mm.add_chat("user", "hello from beta", client_id="client_b")
    mm.save_long_term("Alpha note", "alpha-only strategy details", client_id="client_a")

    mem_b = mm.get_all_memories_for_prompt(client_id="client_b")
    assert "SECRET-A" not in mem_b
    assert "alpha-only strategy" not in mem_b

    mem_a = mm.get_all_memories_for_prompt(client_id="client_a")
    assert "SECRET-A" in mem_a
    assert "alpha-only strategy" in mem_a

    # default client keeps the original shared file path
    assert mm._long_term_path("default") == mm.long_term_file
    assert mm._long_term_path("client_a") != mm.long_term_file


def test_engine_prompt_memory_scoped_to_client(monkeypatch):
    from engines.ai_engine import get_engine
    eng = get_engine(provider="offline")
    eng.memory.add_chat("user", "ZZTOP-SECRET client A info", client_id="client_a")

    captured = {}
    orig = eng._compose_system_prompt

    def spy(system_prompt, context, client_id="default"):
        out = orig(system_prompt, context, client_id)
        captured["sys"] = out
        return out

    monkeypatch.setattr(eng, "_compose_system_prompt", spy)
    eng.generate_text("campaign test", context={"agent": "strategist", "product": "P"},
                      client_id="client_b")
    assert "ZZTOP-SECRET" not in captured["sys"]
