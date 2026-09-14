"""
Quick interactive test (no API key needed).
Usage:  python test_run.py
"""

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
    print(f"Emotion: {result['emotion']}")
    print(f"Customer: {result['customer_message']}\n")

    while not result.get("finished"):
        agent = input("You (agent) > ").strip()
        if not agent:
            continue
        if agent.lower() in ("quit", "exit", "q"):
            break
        result = sim.respond(agent)
        print(f"\nEmotion: {result['emotion']}")
        print(f"Customer: {result['customer_message']}\n")
        if result.get("finished"):
            print("--- Conversation resolved ---")
            break

    print(f"\nLog file: {sim.logger.get_log_path()}")


if __name__ == "__main__":
    main()