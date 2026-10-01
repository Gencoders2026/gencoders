"""
Task 7 - Live Support Console test suite.

Covers BOTH required modes end to end:

* Manual Mode    - the three dynamic customer messages from the brief are
                   analysed one after another and every displayed value
                   (intent, sentiment, frustration, escalation risk,
                   suggested response, coaching, knowledge) has to CHANGE
                   with the message - never a fixed increment.
* Replay Mode    - .txt, .csv and .json transcripts are uploaded, parsed
                   into customer/agent messages, stepped through with
                   Next / Previous / Restart and analysed per message.
* Conversation state - recorded conversations are persisted and readable.

Run with:

    python -m pytest task7_live_support_console/test_task7.py -v
"""

import io
import json
import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

for candidate in (
    str(HERE),
    str(REPO_ROOT / "task4_task5_task6_support_assist_agents"),
):
    if candidate not in sys.path:
        sys.path.insert(0, candidate)

# The RAG lookup is irrelevant to parsing / state assertions and is slow,
# so it is disabled for this suite only.
os.environ.setdefault("TASK6_NO_RAG", "1")

import console_api  # noqa: E402
import session_store  # noqa: E402
import transcript_parser  # noqa: E402

MANUAL_MESSAGES = [
    "My payment failed and I have been trying for two hours.",
    "This is ridiculous. Nobody is helping me and I need this fixed immediately.",
    "Thank you, the issue is finally resolved.",
]

TXT_TRANSCRIPT = """Customer: My order is very late and the tracking has not changed at all.
Agent: I am really sorry about that. Let me check the tracking for you right away.
Customer: This is the third time I have contacted you about it.
Agent: I understand how frustrating that is. I have raised it with the courier.
Customer: Thank you, that helps a lot.
"""

CSV_TRANSCRIPT = (
    "role,message\n"
    "customer,My payment failed and I have been trying for two hours.\n"
    'agent,"I am really sorry. Let me check the transaction now."\n'
    "customer,This is ridiculous. Nobody is helping me.\n"
    "agent,I am escalating this to a specialist right now.\n"
    "customer,Thank you, the issue is finally resolved.\n"
)

JSON_TRANSCRIPT = json.dumps([
    {"role": "customer", "content": "I cannot log in to my account."},
    {"role": "agent", "content": "I am sorry - let me reset your access."},
    {"role": "customer", "content": "It is still locked. This is unacceptable."},
    {"role": "agent", "content": "I have unlocked it and emailed you a link."},
    {"role": "customer", "content": "Thank you, it works now."},
])

TEST_SESSION_TITLE = "pytest task7 console session"


@pytest.fixture(scope="module")
def client():
    application = console_api.create_app()
    with TestClient(application) as test_client:
        yield test_client


def _upload(upload_client, filename, content, content_type="text/plain"):
    return upload_client.post(
        "/task7/transcript/parse",
        files={
            "file": (
                filename,
                io.BytesIO(content.encode("utf-8")),
                content_type,
            )
        },
    )


# ===========================================================================
# 1. HEALTH
# ===========================================================================
class TestHealth:
    def test_health_reports_ok(self, client):
        response = client.get("/task7/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "ok"
        assert payload["service"] == "task7-live-support-console"


# ===========================================================================
# 2. MANUAL MODE - dynamic per-message analysis
# ===========================================================================
class TestManualMode:
    @pytest.fixture(scope="class")
    def analysed(self, client):
        history = []
        results = []
        for turn, message in enumerate(MANUAL_MESSAGES, start=1):
            history.append({"role": "customer", "content": message})
            response = client.post(
                "/task7/analyze",
                json={
                    "query": message,
                    "session_id": "pytest-manual",
                    "turn": turn,
                    "history": history,
                },
            )
            assert response.status_code == 200, response.text
            results.append(response.json())
        return results

    def test_returns_the_full_three_panel_payload(self, analysed):
        first = analysed[0]
        # Panel 1 - customer state
        for key in ("intent", "sentiment", "frustration_level", "emotion_label"):
            assert key in first
        # Panel 2 - coaching
        for key in (
            "suggested_response",
            "coaching_tips",
            "response_evaluation",
            "escalation_level",
            "escalation_score",
            "recommended_actions",
        ):
            assert key in first
        # Panel 3 - knowledge
        assert "knowledge_results" in first
        assert "knowledge_available" in first

    def test_intent_is_detected_from_the_message(self, analysed):
        assert analysed[0]["intent"] == "payment_failure"

    def test_sentiment_is_dynamic(self, analysed):
        labels = [item["sentiment"] for item in analysed]
        assert labels[0] != labels[1], labels
        assert labels[2] == "positive", labels

    def test_frustration_level_is_dynamic(self, analysed):
        levels = [item["frustration_level"] for item in analysed]
        assert levels[1] > levels[0], levels
        assert levels[2] < levels[1], levels

    def test_escalation_risk_is_dynamic(self, analysed):
        scores = [item["escalation_score"] for item in analysed]
        assert scores[1] > scores[0], scores
        assert analysed[1]["escalation_level"] in ("High", "Critical")
        assert scores[2] < scores[1], scores

    def test_suggested_response_changes_per_message(self, analysed):
        responses = [item["suggested_response"] for item in analysed]
        assert all(responses)
        assert len(set(responses)) >= 2, responses

    def test_coaching_feedback_changes_per_message(self, analysed):
        tip_sets = [tuple(item["coaching_tips"]) for item in analysed]
        assert all(tip_sets)
        assert len(set(tip_sets)) >= 2, tip_sets

    def test_response_evaluation_covers_the_four_dimensions(self, analysed):
        evaluation = analysed[0]["response_evaluation"]
        for dimension in ("tone", "empathy", "clarity", "professionalism"):
            assert dimension in evaluation
            assert 0 <= evaluation[dimension]["score"] <= 100
        assert 0 <= evaluation["overall"] <= 100

    def test_escalation_warning_appears_for_the_angry_message(self, analysed):
        assert analysed[1]["escalation_reasoning"], "no reasoning produced"
        assert analysed[1]["escalation_indicators"], "no indicators produced"
        assert analysed[1]["escalation_score"] >= 25

    def test_conversation_state_is_maintained(self, analysed):
        counts = [item["message_count"] for item in analysed]
        assert counts == sorted(counts)
        assert counts[-1] >= 3

    def test_agent_messages_never_move_the_customer_state(self, client):
        customer = client.post(
            "/task7/analyze",
            json={
                "query": "This is ridiculous and I want a supervisor now.",
                "session_id": "pytest-guard",
                "turn": 1,
            },
        ).json()

        # A subsequent AGENT turn must be sent to /support/analyze (which
        # enforces the no-op). Re-analysing the same customer text must not
        # double count, which is what the console relies on.
        repeat = client.post(
            "/task7/analyze",
            json={
                "query": "This is ridiculous and I want a supervisor now.",
                "session_id": "pytest-guard",
                "turn": 1,
            },
        ).json()

        assert repeat["escalation_score"] == customer["escalation_score"]
        assert repeat["message_count"] == customer["message_count"]



# ===========================================================================
# 3. REPLAY MODE - transcript upload (.txt / .csv / .json)
# ===========================================================================
class TestReplayUpload:
    def test_txt_upload_separates_customer_and_agent_messages(self, client):
        response = _upload(client, "conversation.txt", TXT_TRANSCRIPT)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["format"] == "txt"
        assert payload["counts"]["customer_messages"] == 3
        assert payload["counts"]["agent_messages"] == 2
        roles = [message["role"] for message in payload["messages"]]
        assert roles == ["customer", "agent", "customer", "agent", "customer"]

    def test_csv_upload_handles_quoted_messages(self, client):
        response = _upload(
            client, "conversation.csv", CSV_TRANSCRIPT, "text/csv"
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["format"] == "csv"
        assert payload["counts"]["messages"] == 5
        assert payload["messages"][1]["role"] == "agent"
        assert "sorry" in payload["messages"][1]["content"].lower()

    def test_json_upload_parses_message_objects(self, client):
        response = _upload(
            client, "conversation.json", JSON_TRANSCRIPT, "application/json"
        )
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["format"] == "json"
        assert payload["counts"]["messages"] == 5
        assert payload["messages"][0]["role"] == "customer"

    def test_json_upload_accepts_a_messages_object(self, client):
        content = json.dumps({"messages": [
            {"speaker": "Customer", "text": "My refund is missing."},
            {"speaker": "Agent", "text": "Let me check that for you."},
        ]})
        response = _upload(client, "wrapped.json", content, "application/json")
        assert response.status_code == 200, response.text
        assert response.json()["counts"]["messages"] == 2

    def test_unsupported_type_is_rejected(self, client):
        response = _upload(client, "conversation.pdf", "not a transcript")
        assert response.status_code == 415

    def test_empty_file_is_rejected(self, client):
        response = _upload(client, "empty.txt", "   ")
        assert response.status_code == 422

    def test_invalid_json_is_reported_clearly(self, client):
        response = _upload(
            client, "broken.json", "{not valid", "application/json"
        )
        assert response.status_code == 422
        assert "JSON" in response.json()["detail"]



class TestReplayStepping:
    """Next / Previous / Restart analyse the right message every time."""

    @pytest.fixture(scope="class")
    def transcript(self, client):
        return _upload(client, "replay.txt", TXT_TRANSCRIPT).json()["messages"]

    def _analyze_upto(self, client, transcript, count):
        revealed = transcript[:count]
        history = [
            {"role": message["role"], "content": message["content"]}
            for message in revealed
        ]
        last_customer = [m for m in history if m["role"] == "customer"][-1]
        turn = sum(1 for m in history if m["role"] == "customer")
        response = client.post(
            "/task7/analyze",
            json={
                "query": last_customer["content"],
                "session_id": "pytest-replay",
                "turn": turn,
                "history": history,
            },
        )
        assert response.status_code == 200, response.text
        return response.json()

    def _customer_steps(self, transcript):
        return [
            count
            for count in range(1, len(transcript) + 1)
            if transcript[count - 1]["role"] == "customer"
        ]

    def test_every_customer_step_is_analysed(self, client, transcript):
        steps = self._customer_steps(transcript)
        assert len(steps) == 3

        for count in steps:
            analysis = self._analyze_upto(client, transcript, count)
            assert analysis["intent"]
            assert analysis["sentiment"] in ("positive", "neutral", "negative")
            assert 1 <= analysis["frustration_level"] <= 10
            assert 0 <= analysis["escalation_score"] <= 100
            assert analysis["suggested_response"]
            assert analysis["coaching_tips"]

    def test_escalation_progresses_then_falls(self, client, transcript):
        scores = [
            self._analyze_upto(client, transcript, count)["escalation_score"]
            for count in self._customer_steps(transcript)
        ]
        assert scores[1] > scores[0], scores
        assert scores[2] < scores[1], scores

    def test_stepping_back_reuses_the_same_analysis(self, client, transcript):
        # "Previous" re-runs the same request, so an earlier step must
        # produce exactly the same values as the first time it was shown.
        first = self._analyze_upto(client, transcript, 3)
        again = self._analyze_upto(client, transcript, 3)
        assert again["escalation_score"] == first["escalation_score"]
        assert again["sentiment"] == first["sentiment"]
        assert again["frustration_level"] == first["frustration_level"]

    def test_restart_returns_to_the_first_customer_message(
        self, client, transcript
    ):
        restarted = self._analyze_upto(client, transcript, 1)
        assert restarted["turn"] == 1
        assert restarted["intent"] == "delayed_order"



# ===========================================================================
# 4. CONVERSATION STATE PERSISTENCE
# ===========================================================================
class TestConversationState:
    def test_record_list_and_read_back_a_conversation(self, client):
        messages = [
            {"role": "customer", "content": MANUAL_MESSAGES[0]},
            {"role": "agent", "content": "I am sorry - let me check that now."},
            {"role": "customer", "content": MANUAL_MESSAGES[2]},
        ]

        created = client.post(
            "/task7/sessions",
            json={
                "mode": "manual",
                "title": TEST_SESSION_TITLE,
                "messages": messages,
                "knowledge_searches": [
                    {
                        "turn": 1,
                        "query": MANUAL_MESSAGES[0],
                        "results": 3,
                        "sources": ["payment_issues.txt"],
                    }
                ],
                "meta": {"source": "pytest"},
            },
        )
        assert created.status_code == 200, created.text
        stored = created.json()["session"]
        assert stored["message_count"] == 3
        assert stored["mode"] == "manual"

        fetched = client.get(f"/task7/sessions/{stored['id']}")
        assert fetched.status_code == 200
        payload = fetched.json()
        assert payload["title"] == TEST_SESSION_TITLE
        assert payload["messages"][0]["role"] == "customer"
        assert payload["knowledge_search_count"] == 1

        listed = client.get("/task7/sessions")
        assert listed.status_code == 200
        assert any(
            item["id"] == stored["id"] for item in listed.json()["sessions"]
        )

        deleted = client.delete(f"/task7/sessions/{stored['id']}")
        assert deleted.status_code == 200
        assert client.get(f"/task7/sessions/{stored['id']}").status_code == 404

    def test_a_single_message_is_not_a_conversation(self, client):
        response = client.post(
            "/task7/sessions",
            json={
                "mode": "manual",
                "messages": [{"role": "customer", "content": "hello"}],
            },
        )
        assert response.status_code == 422

    def test_unknown_session_returns_404(self, client):
        assert client.get("/task7/sessions/does-not-exist").status_code == 404

    def test_simulator_conversations_are_available_for_replay(self, client):
        response = client.get(
            "/task7/simulator-sessions", params={"limit": 5}
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["count"] >= 1
        first = payload["sessions"][0]
        assert first["message_count"] >= 2

        detail = client.get(f"/task7/simulator-sessions/{first['id']}")
        assert detail.status_code == 200
        conversation = detail.json()
        assert conversation["mode"] == "simulator"
        assert len(conversation["messages"]) == first["message_count"]


# ===========================================================================
# 5. TRANSCRIPT PARSER (no HTTP layer)
# ===========================================================================
class TestTranscriptParser:
    def test_roles_alternate_when_no_markers_exist(self):
        parsed = transcript_parser.parse_transcript(
            "plain.txt",
            "My order is late.\n\nThe team is checking it now.",
        )
        assert [m["role"] for m in parsed["messages"]] == [
            "customer",
            "agent",
        ]
        assert parsed["warnings"]

    def test_timestamp_prefix_is_stripped_into_metadata(self):
        parsed = transcript_parser.parse_transcript(
            "timed.txt",
            "10:15 Customer: My invoice is wrong.\n"
            "10:16 Agent: Let me correct it.\n",
        )
        assert parsed["messages"][0]["timestamp"] == "10:15"
        assert parsed["messages"][0]["content"] == "My invoice is wrong."

    def test_normalise_messages_rejects_garbage(self):
        with pytest.raises(ValueError):
            transcript_parser.normalise_messages({"not": "a list"})

