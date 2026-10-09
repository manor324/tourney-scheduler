"""
Tests for nl_to_config.py -- everything EXCEPT the actual network call
to the Claude API or a real Ollama server. These tests simulate what a
model response would look like (including realistic imperfections like
markdown fences, and omitted optional fields) and confirm the
validation logic -- and the deterministic default-filling logic -- work
correctly regardless of backend.
"""

import sys
import os
import json
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from nl_to_config import _strip_markdown_fences, _apply_missing_field_defaults, translate


def test_strip_markdown_fences_with_json_tag():
    text = '```json\n{"mode": "round_robin"}\n```'
    assert _strip_markdown_fences(text) == '{"mode": "round_robin"}'


def test_strip_markdown_fences_without_json_tag():
    text = '```\n{"mode": "round_robin"}\n```'
    assert _strip_markdown_fences(text) == '{"mode": "round_robin"}'


def test_strip_markdown_fences_no_fences_present():
    text = '{"mode": "round_robin"}'
    assert _strip_markdown_fences(text) == '{"mode": "round_robin"}'


VALID_ROUND_ROBIN_RESPONSE = json.dumps({
    "mode": "round_robin",
    "teams": ["Falcons", "Wolves", "Hawks", "Bears"],
    "double_round": True,
    "constraints": {"season_days": 40, "max_consecutive_away": 2, "max_consecutive_home": 3, "min_rest_days": 1},
    "optimize": False,
})

VALID_IPL_CALENDAR_RESPONSE = json.dumps({
    "mode": "ipl_calendar",
    "group_a": ["T1", "T2", "T3", "T4", "T5"],
    "group_b": ["T6", "T7", "T8", "T9", "T10"],
    "row_pairs": {"T1": "T6", "T2": "T7", "T3": "T8", "T4": "T9", "T5": "T10"},
    "constraints": {"max_consecutive_away": 2, "max_consecutive_home": 3},
    "calendar": {"season_days": 70, "opening_weekday": "Saturday", "min_rest_hours": 48, "defending_champion": "T1"},
    "optimize": False,
})

IPL_CALENDAR_NO_CHAMPION_RESPONSE = json.dumps({
    "mode": "ipl_calendar",
    "group_a": ["T1", "T2", "T3", "T4", "T5"],
    "group_b": ["T6", "T7", "T8", "T9", "T10"],
    "constraints": {"max_consecutive_away": 2, "max_consecutive_home": 3},
    "calendar": {"season_days": 70, "opening_weekday": "Saturday", "min_rest_hours": 48},
    "optimize": False,
})

FENCED_RESPONSE = f"```json\n{VALID_ROUND_ROBIN_RESPONSE}\n```"

INVALID_MODE_RESPONSE = json.dumps({"mode": "not_a_real_mode", "teams": ["A", "B"]})

WRONG_GROUP_SIZE_RESPONSE = json.dumps({
    "mode": "ipl_calendar",
    "group_a": ["T1", "T2", "T3"],
    "group_b": ["T6", "T7", "T8", "T9", "T10"],
})

NOT_JSON_RESPONSE = "Sure! Here's a schedule for your teams: Team A plays Team B..."


def test_defaults_fill_missing_defending_champion():
    raw = {
        "mode": "ipl_calendar",
        "group_a": ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"],
        "group_b": ["Zeta", "Eta", "Theta", "Iota", "Kappa"],
        "calendar": {"season_days": 70},
    }
    filled, notes = _apply_missing_field_defaults(raw)
    assert filled["calendar"]["defending_champion"] == "Alpha"
    assert len(notes) == 1
    assert "Alpha" in notes[0]


def test_defaults_leave_explicit_champion_untouched():
    raw = {
        "mode": "ipl_calendar",
        "group_a": ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"],
        "group_b": ["Zeta", "Eta", "Theta", "Iota", "Kappa"],
        "calendar": {"defending_champion": "Beta"},
    }
    filled, notes = _apply_missing_field_defaults(raw)
    assert filled["calendar"]["defending_champion"] == "Beta"
    assert notes == []


def test_defaults_no_op_for_non_ipl_calendar_modes():
    raw = {"mode": "round_robin", "teams": ["A", "B"]}
    filled, notes = _apply_missing_field_defaults(raw)
    assert "calendar" not in filled
    assert notes == []


def test_defaults_handle_missing_calendar_key_entirely():
    raw = {
        "mode": "ipl_calendar",
        "group_a": ["Alpha", "Beta", "Gamma", "Delta", "Epsilon"],
        "group_b": ["Zeta", "Eta", "Theta", "Iota", "Kappa"],
    }
    filled, notes = _apply_missing_field_defaults(raw)
    assert filled["calendar"]["defending_champion"] == "Alpha"
    assert len(notes) == 1


def test_translate_accepts_valid_round_robin_response():
    with patch("nl_to_config._call_claude", return_value=VALID_ROUND_ROBIN_RESPONSE):
        config, notes = translate("4 teams, simple round robin")
    assert config["mode"] == "round_robin"
    assert len(config["teams"]) == 4
    assert notes == []


def test_translate_accepts_valid_ipl_calendar_response():
    with patch("nl_to_config._call_claude", return_value=VALID_IPL_CALENDAR_RESPONSE):
        config, notes = translate("IPL season with defending champion T1")
    assert config["mode"] == "ipl_calendar"
    assert config["calendar"]["defending_champion"] == "T1"
    assert notes == []


def test_translate_fills_missing_champion_end_to_end():
    with patch("nl_to_config._call_claude", return_value=IPL_CALENDAR_NO_CHAMPION_RESPONSE):
        config, notes = translate("10-team IPL calendar season")
    assert config["calendar"]["defending_champion"] == "T1"
    assert len(notes) == 1
    assert "T1" in notes[0]


def test_translate_strips_markdown_fences_from_response():
    with patch("nl_to_config._call_claude", return_value=FENCED_RESPONSE):
        config, notes = translate("4 teams, simple round robin")
    assert config["mode"] == "round_robin"


def test_translate_rejects_invalid_mode():
    with patch("nl_to_config._call_claude", return_value=INVALID_MODE_RESPONSE):
        raised = False
        try:
            translate("something weird")
        except ValueError:
            raised = True
        assert raised, "expected ValueError for invalid mode from model"


def test_translate_rejects_wrong_group_size():
    with patch("nl_to_config._call_claude", return_value=WRONG_GROUP_SIZE_RESPONSE):
        raised = False
        try:
            translate("IPL with 3 teams in group A")
        except ValueError:
            raised = True
        assert raised, "expected ValueError for wrong IPL group size"


def test_translate_rejects_non_json_response():
    with patch("nl_to_config._call_claude", return_value=NOT_JSON_RESPONSE):
        raised = False
        try:
            translate("anything")
        except ValueError:
            raised = True
        assert raised, "expected ValueError for non-JSON model response"


def test_missing_api_key_raises_clear_error():
    from nl_to_config import _call_claude
    old_key = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        raised = False
        try:
            _call_claude("test", "claude-sonnet-4-5")
        except RuntimeError as e:
            raised = True
            assert "ANTHROPIC_API_KEY" in str(e)
        assert raised, "expected RuntimeError when API key is missing"
    finally:
        if old_key is not None:
            os.environ["ANTHROPIC_API_KEY"] = old_key


def test_translate_uses_ollama_backend_when_selected():
    with patch("nl_to_config._call_ollama", return_value=VALID_ROUND_ROBIN_RESPONSE) as mock_ollama, \
         patch("nl_to_config._call_claude") as mock_claude:
        config, notes = translate("4 teams, simple round robin", backend="ollama")
    assert config["mode"] == "round_robin"
    mock_ollama.assert_called_once()
    mock_claude.assert_not_called()


def test_translate_ollama_validates_same_as_claude():
    with patch("nl_to_config._call_ollama", return_value=INVALID_MODE_RESPONSE):
        raised = False
        try:
            translate("something weird", backend="ollama")
        except ValueError:
            raised = True
        assert raised, "expected ValueError for invalid mode from ollama backend too"


def test_translate_ollama_also_gets_champion_default():
    with patch("nl_to_config._call_ollama", return_value=IPL_CALENDAR_NO_CHAMPION_RESPONSE):
        config, notes = translate("10-team IPL calendar season", backend="ollama")
    assert config["calendar"]["defending_champion"] == "T1"
    assert len(notes) == 1


def test_ollama_connection_error_raises_clear_message():
    from nl_to_config import _call_ollama
    import requests as requests_module

    with patch("nl_to_config.requests.post", side_effect=requests_module.exceptions.ConnectionError()):
        raised = False
        try:
            _call_ollama("test", "qwen2.5:7b-instruct")
        except RuntimeError as e:
            raised = True
            assert "Ollama" in str(e)
            assert "ollama pull" in str(e)
        assert raised, "expected RuntimeError with a clear message when Ollama is unreachable"


def test_ollama_missing_model_raises_clear_message():
    from nl_to_config import _call_ollama

    class FakeResponse:
        status_code = 404

    with patch("nl_to_config.requests.post", return_value=FakeResponse()):
        raised = False
        try:
            _call_ollama("test", "some-model-not-pulled")
        except RuntimeError as e:
            raised = True
            assert "ollama pull some-model-not-pulled" in str(e)
        assert raised, "expected RuntimeError with pull instructions for a missing model"


def test_call_model_rejects_unknown_backend():
    from nl_to_config import _call_model
    raised = False
    try:
        _call_model("test", "not_a_real_backend", "some-model", "http://localhost:11434")
    except ValueError:
        raised = True
    assert raised, "expected ValueError for an unknown backend name"


def test_translate_defaults_model_per_backend():
    from nl_to_config import DEFAULT_CLAUDE_MODEL, DEFAULT_OLLAMA_MODEL

    with patch("nl_to_config._call_claude", return_value=VALID_ROUND_ROBIN_RESPONSE) as mock_claude:
        translate("test", backend="claude")
    assert mock_claude.call_args[0][1] == DEFAULT_CLAUDE_MODEL

    with patch("nl_to_config._call_ollama", return_value=VALID_ROUND_ROBIN_RESPONSE) as mock_ollama:
        translate("test", backend="ollama")
    assert mock_ollama.call_args[0][1] == DEFAULT_OLLAMA_MODEL


if __name__ == "__main__":
    test_strip_markdown_fences_with_json_tag()
    print("test_strip_markdown_fences_with_json_tag passed")
    test_strip_markdown_fences_without_json_tag()
    print("test_strip_markdown_fences_without_json_tag passed")
    test_strip_markdown_fences_no_fences_present()
    print("test_strip_markdown_fences_no_fences_present passed")
    test_defaults_fill_missing_defending_champion()
    print("test_defaults_fill_missing_defending_champion passed")
    test_defaults_leave_explicit_champion_untouched()
    print("test_defaults_leave_explicit_champion_untouched passed")
    test_defaults_no_op_for_non_ipl_calendar_modes()
    print("test_defaults_no_op_for_non_ipl_calendar_modes passed")
    test_defaults_handle_missing_calendar_key_entirely()
    print("test_defaults_handle_missing_calendar_key_entirely passed")
    test_translate_accepts_valid_round_robin_response()
    print("test_translate_accepts_valid_round_robin_response passed")
    test_translate_accepts_valid_ipl_calendar_response()
    print("test_translate_accepts_valid_ipl_calendar_response passed")
    test_translate_fills_missing_champion_end_to_end()
    print("test_translate_fills_missing_champion_end_to_end passed")
    test_translate_strips_markdown_fences_from_response()
    print("test_translate_strips_markdown_fences_from_response passed")
    test_translate_rejects_invalid_mode()
    print("test_translate_rejects_invalid_mode passed")
    test_translate_rejects_wrong_group_size()
    print("test_translate_rejects_wrong_group_size passed")
    test_translate_rejects_non_json_response()
    print("test_translate_rejects_non_json_response passed")
    test_missing_api_key_raises_clear_error()
    print("test_missing_api_key_raises_clear_error passed")
    test_translate_uses_ollama_backend_when_selected()
    print("test_translate_uses_ollama_backend_when_selected passed")
    test_translate_ollama_validates_same_as_claude()
    print("test_translate_ollama_validates_same_as_claude passed")
    test_translate_ollama_also_gets_champion_default()
    print("test_translate_ollama_also_gets_champion_default passed")
    test_ollama_connection_error_raises_clear_message()
    print("test_ollama_connection_error_raises_clear_message passed")
    test_ollama_missing_model_raises_clear_message()
    print("test_ollama_missing_model_raises_clear_message passed")
    test_call_model_rejects_unknown_backend()
    print("test_call_model_rejects_unknown_backend passed")
    test_translate_defaults_model_per_backend()
    print("test_translate_defaults_model_per_backend passed")
    print("\nAll tests passed.")
