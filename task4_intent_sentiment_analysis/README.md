# Task 4 — Intent & Sentiment Analysis Agent

## Objective

Analyze every customer message in real time and produce structured insights including intent, emotion, frustration score, sentiment, satisfaction trend, escalation risk, and coaching guidance.

---

## Deliverables

| # | Deliverable | Status |
|---|------------|--------|
| 1 | Intent and emotion classification module | ✅ `analysis_agent.py` |
| 2 | Sentiment analysis module | ✅ `analysis_agent.py` + `task6_support_assist/analysis_core.py` |
| 3 | Frustration scoring mechanism (1-10) | ✅ `detect_emotion()` in analysis_core |
| 4 | Satisfaction trend tracker | ✅ `ConversationHistory.get_satisfaction_trend()` |
| 5 | Escalation-risk detection (4 levels) | ✅ `calculate_escalation_risk()` |
| 6 | Conversation history management | ✅ `ConversationHistory` class |
| 7 | API endpoint for analysis | ✅ `POST /analyze` in `task3_customer_simulator/api.py` |
| 8 | 20 unit test cases | ✅ `test_analysis_agent.py` |
| 9 | Technical documentation | ✅ This README |
| 10 | Multi-turn conversation demo | ✅ Tests 15 & 16 |

---

## Architecture

```
Customer Message
      │
      ▼
detect_intent()          → intent: refund_request / delayed_order / payment_failure /
                                   account_issue / cancellation / general_inquiry
      │
      ▼
detect_emotion()         → emotion_label: Calm / Frustrated / Angry / Furious
                         → frustration_level: 1-10
      │
      ▼
detect_sentiment()       → sentiment: positive / neutral / negative
                         → confidence: 0.0-1.0
      │
      ▼
ConversationHistory      → satisfaction_trend: improving / stable / declining / critical
      │
      ▼
calculate_escalation_risk() → escalation_risk: Low / Medium / High / Critical
      │
      ▼
generate_coaching_guidance() → List[str] of actionable tips
      │
      ▼
Structured JSON Response
```

---

## API Endpoint

### `POST /analyze`

**Request:**
```json
{
  "query": "I'm very frustrated! My refund hasn't been processed after 2 weeks!",
  "persona_hint": "frustrated",
  "scenario_hint": "refund_request"
}
```

**Response:**
```json
{
  "intent": "refund_request",
  "emotion": "Angry",
  "emotion_label": "Angry",
  "frustration_level": 7,
  "sentiment": "negative",
  "satisfaction_trend": "declining",
  "escalation_risk": "High",
  "confidence": 0.85,
  "coaching_guidance": [
    "Show empathy first before providing solutions.",
    "Provide a concrete resolution timeline to rebuild trust.",
    "Clearly state the refund eligibility and processing time."
  ],
  "knowledge_results": []
}
```

---

## Intent Categories

| Intent | Trigger Keywords |
|--------|----------------|
| `refund_request` | refund, money back, return |
| `delayed_order` | late, delay, tracking, delivery, still waiting |
| `payment_failure` | payment, charged, declined, card, transaction |
| `account_issue` | login, password, locked, account |
| `cancellation` | cancel, unsubscribe, stop billing |
| `general_inquiry` | (default — no above keywords) |

---

## Emotion & Frustration Scale

| Frustration | Emotion Label | Description |
|-------------|--------------|-------------|
| 1-3 | Calm | No negative signals or polite request |
| 4-6 | Frustrated | Mild to moderate complaint |
| 7-8 | Angry | Clear anger vocabulary |
| 9-10 | Furious | Severe anger or supervisor demand |

---

## Escalation Risk Levels

| Level | Frustration | Condition |
|-------|------------|-----------|
| Low | 1-3 | Calm, no complaints |
| Medium | 4-6 | Moderate frustration or repeated negative |
| High | 7-8 | High frustration or declining trend |
| Critical | 9-10 | Supervisor demand or extreme frustration |

---

## Running the Tests

```bash
cd task4_intent_sentiment_analysis
python test_analysis_agent.py
```

Expected output: **20/20 tests passed**

---

## Integration with Other Tasks

- **Task 3 (Customer Simulator):** The `/analyze` endpoint in `task3_customer_simulator/api.py` calls the analysis functions and returns results to the frontend.
- **Task 6 (Coaching & Escalation):** `analysis_core.py` in `task6_support_assist/` is the shared module providing `detect_emotion()`, `detect_sentiment()`, and `detect_intent()`.
- **Task 5 (Frontend Dashboard):** The `SupportConsole.jsx` displays all analysis fields in real time.
- **Task 2 (RAG Pipeline):** `knowledge_results` field is populated via `task2_rag_pipeline/retriever.py`.
