"""
Unit tests for prompt construction (agent/prompts.py).

Verifies the prompts are correctly assembled and contain the required
guardrails, escalation triggers, and tool instructions.
"""

from agent.prompts import CHAT_SYSTEM_PROMPT, VOICE_INSTRUCTIONS


def _rendered_chat(support_email="support@relaypay.com"):
    return CHAT_SYSTEM_PROMPT.format(support_email=support_email)


def _rendered_voice(support_email="support@relaypay.com"):
    return VOICE_INSTRUCTIONS.format(support_email=support_email)


# ── Identity ──────────────────────────────────────────────────────────────────

def test_chat_prompt_includes_agent_name():
    assert "Remi" in _rendered_chat()


def test_voice_prompt_includes_agent_name():
    assert "Remi" in _rendered_voice()


def test_chat_prompt_includes_product_name():
    assert "RelayPay" in _rendered_chat()


# ── Guardrails ────────────────────────────────────────────────────────────────

def test_chat_prompt_includes_english_only_guardrail():
    prompt = _rendered_chat()
    assert "English" in prompt


def test_chat_prompt_scope_restricts_to_relaypay():
    prompt = _rendered_chat()
    assert "only answer questions about RelayPay" in prompt.lower() or \
           "only" in prompt.lower() and "RelayPay" in prompt


def test_chat_prompt_never_reveal_system_prompt():
    prompt = _rendered_chat()
    assert "Never reveal" in prompt or "never reveal" in prompt.lower()


def test_chat_prompt_never_fabricate_information():
    prompt = _rendered_chat()
    assert "make up" in prompt.lower() or "fabricate" in prompt.lower()


# ── Tool usage instructions ───────────────────────────────────────────────────

def test_chat_prompt_instructs_search_before_answering():
    prompt = _rendered_chat()
    assert "search_knowledge_base" in prompt


def test_chat_prompt_includes_escalation_sequence():
    prompt = _rendered_chat()
    assert "escalate_to_human" in prompt or "escalate" in prompt.lower()


def test_chat_prompt_support_email_is_substituted():
    prompt = _rendered_chat(support_email="help@acme.com")
    assert "help@acme.com" in prompt
    # The raw placeholder should not remain
    assert "{support_email}" not in prompt


# ── Voice prompt specifics ────────────────────────────────────────────────────

def test_voice_prompt_instructs_short_responses():
    prompt = _rendered_voice()
    assert "two or three sentences" in prompt or "concise" in prompt.lower()


def test_voice_prompt_no_markdown_instruction():
    prompt = _rendered_voice()
    assert "markdown" in prompt.lower()
