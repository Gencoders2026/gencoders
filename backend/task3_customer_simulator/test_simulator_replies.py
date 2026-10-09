"""
Tests for the Customer Simulator Agent (Task 3).

Focus areas:

* the customer actually REACTS to what the support agent replied
  (information request, confirmation, timeline, apology, vague, generic);
* the same agent reply produces a different customer message depending on
  the emotional band;
* base customer lines are never repeated while unused lines remain, even
  when a persona prefix is prepended;
* every scenario / persona / band combination works, including long
  conversations where a reply pool is exhausted.
"""

import pytest

from simulator import (
    SCENARIOS,
    CustomerSimulator,
    get_band,
)
from contextual_replies import CONTEXTUAL_REPLIES


# ==========================================================
# HELPERS
# ==========================================================

REPLY_SAMPLES = {
    "asks_for_info": "Could you please provide your order number?",
    "asks_confirmation": "Can you confirm the email address on the account?",
    "gives_timeline": "We will process this within 24 hours and email you.",
    "apology_only": "I am really sorry about this inconvenience.",
    "vague": "Thanks for reaching out, we will look into this for you.",
    "offers_help": "Is there anything else I can help you with today?",
}

TONES = ["calm", "concerned", "frustrated", "angry", "furious"]


def strip_prefix(text):
    """
    Remove a persona prefix so the underlying BASE line can be compared.
    """
    for prefixes in CustomerSimulator.PERSONA_PREFIXES.values():
        for prefix in prefixes:
            if text.startswith(prefix):
                return text[len(prefix):]
    return text


def pool_for(scenario, kind, band):
    """
    Base lines valid for a scenario / agent-reply-kind / band combination.
    """
    return [
        text
        for tone, text in CONTEXTUAL_REPLIES[scenario][kind]
        if tone in (band, "any")
    ]


class Conversation:
    """
    Small helper that starts the conversation and then feeds the
    simulator a sequence of agent replies.
    """

    def __init__(self, **kwargs):
        self.simulator = CustomerSimulator(**kwargs)
        # The opening line is the customer's first (non-reactive) message.
        self.opening = self.simulator.start()["customer_message"]
        self.turns = []

    def say(self, agent_message):
        message = self.simulator.respond(
            agent_message=agent_message
        )["customer_message"]
        self.turns.append(message)
        return message

    def bases(self):
        return [strip_prefix(m) for m in self.turns]


# ==========================================================
# AGENT REPLY CLASSIFICATION
# ==========================================================

class TestAgentReplyClassification:

    @pytest.mark.parametrize(
        "agent_message,expected",
        [
            ("Could you please provide your order number?",
             "asks_for_info"),
            ("Can you confirm the email address on the account?",
             "asks_confirmation"),
            ("We will process this within 24 hours and email you.",
             "gives_timeline"),
            ("I am really sorry about this inconvenience.",
             "apology_only"),
            ("Thanks for reaching out, we will look into this for you.",
             "vague"),
            ("Is there anything else I can help you with today?",
             "offers_help"),
        ]
    )
    def test_classifies_each_reply_kind(self, agent_message, expected):
        simulator = CustomerSimulator(frustration_level=5)
        assert simulator._agent_reply_kind(agent_message) == expected

    def test_blank_reply_is_treated_as_vague(self):
        """
        An empty agent reply carries no commitment at all, so it is
        classified as a vague stall.
        """
        simulator = CustomerSimulator(frustration_level=5)
        assert simulator._agent_reply_kind("") == "vague"
        assert simulator._agent_reply_kind(None) == "vague"

    def test_every_kind_has_replies_in_every_scenario(self):
        """
        Every classification the simulator can produce must have a reply
        pool in every scenario, otherwise replies silently fall back to
        the generic band pool.
        """
        for scenario in SCENARIOS:
            kinds = CONTEXTUAL_REPLIES[scenario]
            for kind in REPLY_SAMPLES:
                assert kinds.get(kind), (scenario, kind)

    def test_every_band_has_usable_lines_for_each_kind(self):
        """
        Every band must be able to pick at least one line for every
        agent-reply kind, either from its own tone or from an "any" line.
        """
        for scenario, kinds in CONTEXTUAL_REPLIES.items():
            for kind, lines in kinds.items():
                for tone in TONES:
                    usable = [
                        text for line_tone, text in lines
                        if line_tone in (tone, "any")
                    ]
                    assert usable, (scenario, kind, tone)

    def test_unknown_kind_returns_empty_pool(self):
        simulator = CustomerSimulator(frustration_level=5)
        assert simulator._contextual_replies("nonsense") == []


# ==========================================================
# REPLY-AWARE RESPONSES
# ==========================================================

class TestReplyAwareResponses:

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    @pytest.mark.parametrize("kind", list(REPLY_SAMPLES))
    def test_customer_uses_pool_for_that_kind(self, scenario, kind):
        """
        The generated line must come from the pool for the classified
        agent-reply kind, not from the generic band pool.
        """
        conversation = Conversation(
            scenario=scenario, frustration_level=7
        )
        message = conversation.say(REPLY_SAMPLES[kind])
        band = get_band(conversation.simulator.frustration_level)
        assert strip_prefix(message) in pool_for(scenario, kind, band)

    def test_different_kinds_produce_different_responses(self):
        conversation = Conversation(frustration_level=7)
        replies = {
            strip_prefix(conversation.say(agent_message))
            for agent_message in REPLY_SAMPLES.values()
        }
        assert len(replies) == len(REPLY_SAMPLES)

    def test_same_kind_differs_by_emotional_band(self):
        """
        A furious and a calm customer must not answer identically.
        """
        produced = {}
        for level in (1, 3, 5, 7, 9):
            conversation = Conversation(frustration_level=level)
            produced[get_band(level)] = strip_prefix(
                conversation.say(REPLY_SAMPLES["apology_only"])
            )
        assert len(set(produced.values())) == len(produced)

    def test_opening_does_not_react_to_an_agent_message(self):
        """
        The first customer message opens the conversation and comes from
        the band pool, so no agent-reply kind is recorded for it.
        """
        simulator = CustomerSimulator(frustration_level=7)
        opening = simulator.start()["customer_message"]
        assert simulator._last_agent_kind is None
        assert opening

    def test_information_request_gets_details(self):
        """
        When the agent asks for details the customer supplies them
        instead of restating the complaint.
        """
        conversation = Conversation(frustration_level=5)
        base = strip_prefix(
            conversation.say(REPLY_SAMPLES["asks_for_info"])
        )
        assert base in pool_for(
            "refund_request", "asks_for_info", "frustrated"
        )



# ==========================================================
# NO-REPEAT PROTECTION
# ==========================================================

class TestNoRepeat:

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_consecutive_base_lines_differ(self, scenario):
        """
        The customer must never say the same base line twice in a row,
        even when a persona prefix changes the visible text.
        """
        conversation = Conversation(scenario=scenario, frustration_level=7)
        agent_replies = list(REPLY_SAMPLES.values())
        for turn in range(20):
            conversation.say(agent_replies[turn % len(agent_replies)])
        bases = conversation.bases()
        for previous, current in zip(bases, bases[1:]):
            assert previous != current, (scenario, previous)

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_unused_lines_are_preferred(self, scenario):
        """
        A line must not come back around while the conversation can
        still reach an unused one, so the customer keeps saying new
        things instead of looping.
        """
        conversation = Conversation(scenario=scenario, frustration_level=5)
        seen = {strip_prefix(conversation.opening)}

        for _ in range(8):
            base = strip_prefix(
                conversation.say(REPLY_SAMPLES["vague"])
            )
            assert base not in seen, (scenario, base)
            seen.add(base)

        # The scenario's reactive pools plus the band pool must give a
        # genuinely varied conversation, not one line on repeat.
        assert len(seen) >= 8, (scenario, len(seen))

    @pytest.mark.parametrize(
        "persona", list(CustomerSimulator.PERSONA_PREFIXES)
    )
    def test_no_repeat_for_every_persona(self, persona):
        conversation = Conversation(
            persona=persona,
            scenario="payment_failure",
            frustration_level=5,
        )
        for _ in range(12):
            conversation.say(REPLY_SAMPLES["vague"])
        bases = conversation.bases()
        for previous, current in zip(bases, bases[1:]):
            assert previous != current, (persona, previous)

    def test_prefix_alone_does_not_count_as_a_new_line(self):
        """
        A persona prefix must not be able to disguise a repeated line:
        every base line said is recorded exactly once.
        """
        conversation = Conversation(
            persona="frustrated", frustration_level=5
        )
        for _ in range(10):
            conversation.say(REPLY_SAMPLES["vague"])

        said = [strip_prefix(conversation.opening)] + conversation.bases()
        assert set(said) == conversation.simulator.used_bases

    def test_long_conversation_survives_pool_exhaustion(self):
        """
        Once a reply pool is exhausted the simulator must switch to
        another pool instead of repeating the previous line.
        """
        conversation = Conversation(
            scenario="delayed_order", frustration_level=9
        )
        for _ in range(60):
            conversation.say(REPLY_SAMPLES["vague"])
        bases = conversation.bases()
        assert len(bases) == 60
        for previous, current in zip(bases, bases[1:]):
            assert previous != current



# ==========================================================
# COVERAGE
# ==========================================================

class TestCoverage:

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    @pytest.mark.parametrize("level", [1, 3, 5, 7, 9])
    def test_all_scenarios_and_bands(self, scenario, level):
        conversation = Conversation(
            scenario=scenario, frustration_level=level
        )
        for kind in REPLY_SAMPLES:
            message = conversation.say(REPLY_SAMPLES[kind])
            assert isinstance(message, str) and message.strip()

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_long_conversation_keeps_working(self, scenario):
        conversation = Conversation(
            scenario=scenario, frustration_level=8
        )
        agent_replies = list(REPLY_SAMPLES.values())
        for turn in range(40):
            assert conversation.say(
                agent_replies[turn % len(agent_replies)]
            )

    def test_unknown_scenario_and_persona_fall_back(self):
        simulator = CustomerSimulator(
            scenario="does_not_exist",
            persona="does_not_exist",
            frustration_level=5,
        )
        assert simulator.scenario_name == "refund_request"
        assert simulator.persona_name == "frustrated"
        assert simulator.start()["customer_message"]
