"""
Automated test suite for the Customer Simulator Agent.

Covers different customer behaviours:
  * persona configuration
  * scenario configuration
  * emotion / state management
  * turn-by-turn response generation
  * emotional progression (increase and decrease)
  * strict persona rules (no polite words for angry/furious)
  * context maintenance
  * resolution detection
  * logging

Run with:
    python test_simulator.py
or:
    python -m pytest test_simulator.py -v
"""

import os
import sys
import unittest

# ----------------------------------------------------------
# Import path handling (works both as package and standalone)
# ----------------------------------------------------------
try:
    from .simulator import (
        CustomerSimulator,
        get_band,
        get_emotion_label,
        POLITE_WORDS,
    )
    from .personas import PERSONAS, list_personas
    from .scenarios import SCENARIOS, list_scenarios
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from simulator import (
        CustomerSimulator,
        get_band,
        get_emotion_label,
        POLITE_WORDS,
    )
    from personas import PERSONAS, list_personas
    from scenarios import SCENARIOS, list_scenarios


def _sim(**kwargs):
    """Create a rule-based simulator (no LLM) for deterministic testing."""

    kwargs.setdefault("use_llm", False)
    return CustomerSimulator(**kwargs)


class TestPersonas(unittest.TestCase):
    """Persona configuration."""

    def test_all_personas_available(self):
        expected = {"calm", "confused", "frustrated", "angry", "impatient", "polite"}
        self.assertTrue(expected.issubset(set(list_personas())))

    def test_unknown_persona_falls_back(self):
        sim = _sim(persona="does_not_exist")
        self.assertIn(sim.persona_name, PERSONAS)


class TestScenarios(unittest.TestCase):
    """Scenario configuration."""

    def test_all_scenarios_available(self):
        expected = {
            "refund_request",
            "delayed_order",
            "payment_failure",
            "account_issue",
            "cancellation",
        }
        self.assertTrue(expected.issubset(set(list_scenarios())))

    def test_unknown_scenario_falls_back(self):
        sim = _sim(scenario="unknown_scenario")
        self.assertIn(sim.scenario_name, SCENARIOS)


class TestEmotionBands(unittest.TestCase):
    """Emotion mapping."""

    def test_band_boundaries(self):
        self.assertEqual(get_band(1), "calm")
        self.assertEqual(get_band(2), "calm")
        self.assertEqual(get_band(4), "concerned")
        self.assertEqual(get_band(6), "frustrated")
        self.assertEqual(get_band(8), "angry")
        self.assertEqual(get_band(10), "furious")

    def test_emotion_labels(self):
        self.assertEqual(get_emotion_label(2), "Calm")
        self.assertEqual(get_emotion_label(10), "Furious")


class TestConfigurableParameters(unittest.TestCase):
    """Initial emotion, issue severity, patience, expected resolution."""

    def test_initial_emotion_sets_level(self):
        sim = _sim(initial_emotion="furious")
        self.assertEqual(sim.frustration_level, 10)
        self.assertEqual(sim.get_current_band(), "furious")

    def test_issue_severity_and_patience_stored(self):
        sim = _sim(issue_severity=9, patience_level=2)
        self.assertEqual(sim.issue_severity, 9)
        self.assertEqual(sim.patience_level, 2)

    def test_expected_resolution_stored(self):
        sim = _sim(expected_resolution="store_credit")
        self.assertEqual(sim.expected_resolution, "store_credit")


class TestTurnByTurnGeneration(unittest.TestCase):
    """Turn-by-turn message generation & context."""

    def test_start_returns_customer_message(self):
        sim = _sim(persona="frustrated", scenario="refund_request")
        result = sim.start()
        self.assertTrue(result["customer_message"])
        self.assertEqual(result["turn_count"], 1)

    def test_agent_reply_produces_customer_message(self):
        sim = _sim()
        sim.start()
        result = sim.respond("I can help, let me check that for you.")
        self.assertTrue(result["customer_message"])
        self.assertGreaterEqual(result["turn_count"], 3)

    def test_context_is_maintained(self):
        sim = _sim()
        sim.start()
        sim.respond("We are looking into your refund.")
        history = sim.get_history()
        roles = [entry["role"] for entry in history]
        self.assertIn("customer", roles)
        self.assertIn("agent", roles)
        self.assertGreaterEqual(len(history), 3)


class TestPersonaRules(unittest.TestCase):
    """Angry / furious customers must not use polite language."""

    def test_angry_no_polite_words(self):
        for level in (7, 8, 9, 10):
            sim = _sim(persona="angry", scenario="refund_request", frustration_level=level)
            message = sim.start()["customer_message"].lower()
            violations = [w for w in POLITE_WORDS if w in message]
            self.assertEqual(violations, [], f"Angry level {level}: {violations}")

    def test_furious_no_polite_words(self):
        sim = _sim(persona="furious", scenario="delayed_order", frustration_level=10)
        message = sim.start()["customer_message"].lower()
        violations = [w for w in POLITE_WORDS if w in message]
        self.assertEqual(violations, [])

    def test_polite_persona_allowed_polite_words(self):
        sim = _sim(persona="polite", scenario="refund_request", frustration_level=2)
        # Should not crash; polite persona may contain polite words.
        self.assertTrue(sim.start()["customer_message"])


class TestEmotionalProgression(unittest.TestCase):
    """Emotion should increase or decrease based on the agent reply."""

    def test_helpful_reply_calms_customer(self):
        sim = _sim(persona="frustrated", scenario="refund_request", frustration_level=8)
        start_level = sim.frustration_level
        sim.respond(
            "I understand how frustrating this is. I have processed your refund "
            "within 2 business days. Sorry for the inconvenience."
        )
        self.assertLess(sim.frustration_level, start_level)

    def test_unhelpful_reply_increases_frustration(self):
        sim = _sim(persona="frustrated", scenario="refund_request", frustration_level=5)
        start_level = sim.frustration_level
        sim.respond("You cannot get a refund. Please wait, try again later.")
        self.assertGreater(sim.frustration_level, start_level)

    def test_resolution_ends_conversation(self):
        sim = _sim(persona="frustrated", scenario="refund_request", frustration_level=4)
        sim.start()
        result = sim.respond("Your refund has been processed. Here is the confirmation.")
        self.assertTrue(result.get("finished") or result["frustration_level"] <= 3)


class TestDifferentPersonaEmotions(unittest.TestCase):
    """Different personas/levels must produce different messages."""

    def test_different_levels_different_messages(self):
        low = _sim(persona="frustrated", scenario="refund_request", frustration_level=2)
        high = _sim(persona="frustrated", scenario="refund_request", frustration_level=10)
        low_msg = low.start()["customer_message"]
        high_msg = high.start()["customer_message"]
        self.assertNotEqual(low_msg, high_msg)


class TestLogging(unittest.TestCase):
    """Conversation logging."""

    def test_log_file_created(self):
        sim = _sim()
        sim.start()
        path = sim.logger.get_log_path()
        self.assertTrue(os.path.exists(path))

    def test_log_contains_config_and_turns(self):
        sim = _sim(persona="angry", scenario="payment_failure")
        sim.start()
        sim.respond("I can help you with that payment issue right away.")
        full = sim.logger.get_full_log()
        self.assertIn("config", full["meta"])
        self.assertGreaterEqual(len(full["conversation"]), 3)


class TestNegativeCases(unittest.TestCase):
    """Robustness / edge cases."""

    def test_empty_agent_message(self):
        sim = _sim()
        sim.start()
        result = sim.respond("")
        self.assertTrue(result["customer_message"])

    def test_invalid_frustration_level(self):
        sim = _sim()
        self.assertEqual(sim.set_frustration_level(999), 10)
        self.assertEqual(sim.set_frustration_level(-5), 1)

    def test_very_long_agent_message(self):
        sim = _sim()
        sim.start()
        result = sim.respond("This is a long message. " * 200)
        self.assertTrue(result["customer_message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)