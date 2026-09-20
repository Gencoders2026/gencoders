"""
Interactive test for the Customer Simulator Agent.

Runs the rule-based engine (no API key required) so the conversation
can be exercised from the terminal.

Usage:
    python test_run.py
"""

try:  # package-relative imports
    from .simulator import CustomerSimulator
except ImportError:  # flat imports when run directly
    from simulator import CustomerSimulator


def main():
    print("=== Customer Simulator – Interactive Test (rule-based) ===\n")

    sim = CustomerSimulator(
        persona="angry",
        scenario="refund_request",
        initial_emotion="angry",
        issue_severity=8,
        patience_level=3,
        use_llm=False,
    )

    result = sim.start()
    print(f"Session: {result['session_id']}")
    print(f"Emotion: {result['emotion']} ({result['frustration_level']}/10)")
    print(f"Customer: {result['customer_message']}\n")

    while not result.get("finished"):
        agent = input("You (agent) > ").strip()
        if not agent:
            continue
        if agent.lower() in ("quit", "exit", "q"):
            break

        result = sim.respond(agent)
        print(
            f"\nEmotion: {result['emotion']} "
            f"({result['frustration_level']}/10)"
        )
        print(f"Customer: {result['customer_message']}\n")

        if result.get("finished"):
            print("--- Conversation resolved ---")
            break

    print(f"\nLog file: {sim.logger.get_log_path()}")


if __name__ == "__main__":
    main()