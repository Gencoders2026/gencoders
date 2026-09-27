"""
Task 4 — Intent & Sentiment Analysis Agent
==========================================

A dedicated module that:
  - Detects customer intent (5 categories)
  - Classifies emotion (Calm / Frustrated / Angry / Furious)
  - Scores frustration on a 1-10 scale
  - Detects sentiment (positive / neutral / negative)
  - Tracks satisfaction trend (improving / stable / declining / critical)
  - Calculates escalation risk (Low / Medium / High / Critical)
  - Maintains conversation history for multi-turn analysis
  - Returns a full structured analysis object

This module is integrated with Task 3 (Customer Simulator) and Task 6
(Coaching & Escalation Risk Monitoring) via the shared /analyze endpoint.
"""

import sys
from pathlib import Path

# Make task6 analysis_core importable from here
TASK6_DIR = Path(__file__).resolve().parent.parent / "task6_support_assist"
if TASK6_DIR.exists() and str(TASK6_DIR) not in sys.path:
    sys.path.insert(0, str(TASK6_DIR))

from analysis_core import (
    detect_intent,
    detect_emotion,
    detect_sentiment,
    emotion_label_for_level,
)


# ==========================================================
# CONVERSATION HISTORY MANAGER
# ==========================================================
class ConversationHistory:
    """Tracks multi-turn conversation for trend analysis."""

    def __init__(self):
        self.turns = []          # list of {"role", "text", "frustration", "sentiment"}
        self.frustration_history = []
        self.sentiment_history = []

    def add_turn(self, role: str, text: str, frustration: int, sentiment: str):
        self.turns.append({
            "role": role,
            "text": text,
            "frustration": frustration,
            "sentiment": sentiment,
        })
        if role == "customer":
            self.frustration_history.append(frustration)
            self.sentiment_history.append(sentiment)

    def get_satisfaction_trend(self) -> str:
        """Calculate satisfaction trend from last 3 customer turns."""
        hist = self.frustration_history
        if len(hist) < 2:
            return "stable"
        recent = hist[-3:] if len(hist) >= 3 else hist
        if recent[-1] < recent[0] - 1:
            return "improving"
        elif recent[-1] > recent[0] + 1:
            if recent[-1] >= 8:
                return "critical"
            return "declining"
        return "stable"

    def get_negative_streak(self) -> int:
        """Return count of consecutive negative customer turns at the end."""
        streak = 0
        for s in reversed(self.sentiment_history):
            if s == "negative":
                streak += 1
            else:
                break
        return streak


# ==========================================================
# ESCALATION RISK CALCULATOR
# ==========================================================
def calculate_escalation_risk(
    frustration: int,
    sentiment_label: str,
    trend: str,
    negative_streak: int,
    text_lower: str,
) -> dict:
    """
    Calculate escalation risk level and score.

    Risk levels:
      Low      — frustration 1-3, positive/neutral, no complaints
      Medium   — frustration 4-6, some negative sentiment
      High     — frustration 7-8, negative, declining trend
      Critical — frustration 9-10, demand for supervisor, or critical trend

    Returns: {"level": str, "score": float, "reason": str}
    """
    # Explicit escalation demand keywords
    escalation_demands = any(w in text_lower for w in [
        "supervisor", "manager", "escalate", "human agent", "real person",
        "someone else", "speak to a", "talk to a", "higher department"
    ])

    if escalation_demands or frustration >= 9:
        level = "Critical"
        score = 0.95
        reason = "Customer is demanding supervisor/escalation or extremely frustrated"
    elif frustration >= 7 or trend == "critical":
        level = "High"
        score = 0.75
        reason = f"High frustration ({frustration}/10) with {trend} trend"
    elif frustration >= 5 or (sentiment_label == "negative" and negative_streak >= 2):
        level = "Medium"
        score = 0.50
        reason = f"Moderate frustration ({frustration}/10) or sustained negative sentiment"
    else:
        level = "Low"
        score = 0.20
        reason = "Customer appears calm with manageable concern"

    return {"level": level, "score": score, "reason": reason}


# ==========================================================
# COACHING GUIDANCE GENERATOR
# ==========================================================
def generate_coaching_guidance(
    intent: str,
    emotion: str,
    frustration: int,
    escalation_level: str,
    trend: str,
) -> list:
    """
    Generate actionable coaching tips for the support agent
    based on the current analysis of the customer message.
    """
    tips = []

    # Empathy first when customer is frustrated/angry
    if frustration >= 7:
        tips.append("Start with a sincere apology: acknowledge the customer's frustration explicitly.")
    elif frustration >= 5:
        tips.append("Show empathy first before providing solutions.")

    # Escalation-specific guidance
    if escalation_level == "Critical":
        tips.append("ALERT: High escalation risk — consider transferring to a senior agent.")
        tips.append("Do NOT offer generic solutions; address the specific complaint directly.")
    elif escalation_level == "High":
        tips.append("Provide a concrete resolution timeline to rebuild trust.")

    # Intent-specific guidance
    intent_tips = {
        "refund_request": "Clearly state the refund eligibility and processing time.",
        "delayed_order": "Provide the current order status and a revised delivery date.",
        "payment_failure": "Confirm the payment status and clarify any charges.",
        "account_issue": "Guide the customer through account recovery steps.",
        "cancellation": "Acknowledge the cancellation request and confirm the timeline.",
        "general_inquiry": "Ask clarifying questions to understand the customer's exact need.",
    }
    if intent in intent_tips:
        tips.append(intent_tips[intent])

    # Trend-specific guidance
    if trend == "declining":
        tips.append("Satisfaction is declining — act urgently to turn this around.")
    elif trend == "improving":
        tips.append("Good progress — continue empathetic, solution-focused responses.")

    # Default tip if no tips generated
    if not tips:
        tips.append("Stay calm, acknowledge concerns, and provide clear next steps.")

    return tips


# ==========================================================
# MAIN ANALYSIS FUNCTION
# ==========================================================
def analyze_message(
    text: str,
    history: "ConversationHistory | None" = None,
    persona_hint: str = "",
    scenario_hint: str = "",
) -> dict:
    """
    Full intent & sentiment analysis of a customer message.

    Args:
        text: The raw customer message text.
        history: Optional ConversationHistory for multi-turn trend tracking.
        persona_hint: Optional customer persona context.
        scenario_hint: Optional scenario context.

    Returns a structured dict with all analysis fields:
        intent, emotion, emotion_label, frustration_level, sentiment,
        satisfaction_trend, escalation_risk, confidence, coaching_guidance,
        knowledge_results (empty list — filled by RAG integration).
    """
    if not text or not text.strip():
        return {
            "intent": "general_inquiry",
            "emotion": "Calm",
            "emotion_label": "Calm",
            "frustration_level": 1,
            "sentiment": "neutral",
            "satisfaction_trend": "stable",
            "escalation_risk": "Low",
            "confidence": 0.5,
            "coaching_guidance": ["Ask the customer how you can help."],
            "knowledge_results": [],
        }

    text_lower = text.lower()

    # --- Core analysis ---
    intent = detect_intent(text_lower)
    emotion_label, frustration = detect_emotion(text_lower)
    sentiment_result = detect_sentiment(text_lower)
    sentiment = sentiment_result["label"]
    confidence = sentiment_result["confidence"]

    # --- Trend analysis (uses history if available) ---
    if history is not None:
        history.add_turn("customer", text, frustration, sentiment)
        trend = history.get_satisfaction_trend()
        negative_streak = history.get_negative_streak()
    else:
        trend = _simple_trend(frustration, sentiment)
        negative_streak = 1 if sentiment == "negative" else 0

    # --- Escalation risk ---
    risk_data = calculate_escalation_risk(
        frustration, sentiment, trend, negative_streak, text_lower
    )

    # --- Coaching guidance ---
    coaching = generate_coaching_guidance(
        intent, emotion_label, frustration, risk_data["level"], trend
    )

    return {
        # Intent
        "intent": intent,

        # Emotion
        "emotion": emotion_label,
        "emotion_label": emotion_label,
        "customer_emotion": emotion_label,

        # Frustration (1-10)
        "frustration_level": frustration,
        "frustration_score": frustration,
        "frustration": frustration,

        # Sentiment
        "sentiment": sentiment,
        "sentiment_score": sentiment_result["score"],

        # Trend
        "satisfaction_trend": trend,

        # Escalation Risk
        "escalation_risk": risk_data["level"],
        "escalation_score": risk_data["score"],
        "escalation_reason": risk_data["reason"],

        # Confidence
        "confidence": confidence,

        # Coaching
        "coaching_guidance": coaching,
        "coaching_suggestions": coaching,
        "suggestions": coaching,

        # RAG knowledge (filled by caller when RAG is available)
        "knowledge_results": [],

        # Context hints
        "persona_hint": persona_hint,
        "scenario_hint": scenario_hint,
        "query": text,
    }


def _simple_trend(frustration: int, sentiment: str) -> str:
    """Estimate trend from a single message when no history is available."""
    if frustration >= 9:
        return "critical"
    elif frustration >= 7 or sentiment == "negative":
        return "declining"
    elif frustration <= 3 and sentiment == "positive":
        return "improving"
    return "stable"
