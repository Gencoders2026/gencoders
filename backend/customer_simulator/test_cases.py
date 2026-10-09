# Test Cases for AI Customer Support Coaching Assistant


# ============================================================
# POSITIVE / NORMAL TEST CASES
# ============================================================

positive_test_cases = [
    {
        "name": "Angry Customer",
        "persona": "Angry customer",
        "situation": "Customer is upset because their order is delayed.",
        "customer_message": "My order was supposed to arrive yesterday. This is very frustrating!"
    },

    {
        "name": "Confused Customer",
        "persona": "Confused customer",
        "situation": "Customer does not understand how to use the product.",
        "customer_message": "I don't understand how to use this product. Can you help me?"
    },

    {
        "name": "Impatient Customer",
        "persona": "Impatient customer",
        "situation": "Customer wants an immediate solution.",
        "customer_message": "I need this problem fixed right now. I don't have time to wait!"
    },

    {
        "name": "Polite Customer",
        "persona": "Polite customer",
        "situation": "Customer has a simple question.",
        "customer_message": "Hello, could you please help me with my account?"
    },

    {
        "name": "Refund Request",
        "persona": "Customer requesting refund",
        "situation": "Customer wants a refund for a product.",
        "customer_message": "I am not satisfied with the product. I would like to request a refund."
    }
]


# ============================================================
# NEGATIVE TEST CASES
# ============================================================

negative_test_cases = [
    {
        "name": "Empty Customer Message",
        "persona": "Normal customer",
        "situation": "Customer sends an empty message.",
        "customer_message": "",
        "expected": "System should handle empty input safely."
    },

    {
        "name": "Only Spaces",
        "persona": "Normal customer",
        "situation": "Customer sends only spaces.",
        "customer_message": "     ",
        "expected": "System should reject or safely handle blank input."
    },

    {
        "name": "Invalid Emotion",
        "persona": "Customer",
        "situation": "Invalid emotion is provided.",
        "customer_message": "I need help with my order.",
        "emotion": "unknown_emotion",
        "expected": "System should handle invalid emotion safely."
    },

    {
        "name": "Invalid Intensity",
        "persona": "Angry customer",
        "situation": "Invalid intensity value is provided.",
        "customer_message": "I am very unhappy with your service.",
        "intensity": -5,
        "expected": "System should reject or handle invalid intensity."
    },

    {
        "name": "Very Long Message",
        "persona": "Customer",
        "situation": "Customer sends an unusually long message.",
        "customer_message": "This is a test message. " * 100,
        "expected": "System should handle long input without crashing."
    },

    {
        "name": "Missing Customer Message",
        "persona": "Customer",
        "situation": "Customer message is missing.",
        "customer_message": None,
        "expected": "System should handle missing input safely."
    }
]


# ============================================================
# DISPLAY POSITIVE TEST CASES
# ============================================================

def show_positive_test_cases():
    print("\n========== POSITIVE / NORMAL TEST CASES ==========\n")

    for i, test in enumerate(positive_test_cases, start=1):
        print(f"Test Case {i}: {test['name']}")
        print(f"Persona: {test['persona']}")
        print(f"Situation: {test['situation']}")
        print(f"Customer: {test['customer_message']}")
        print("-" * 60)


# ============================================================
# DISPLAY NEGATIVE TEST CASES
# ============================================================

def show_negative_test_cases():
    print("\n========== NEGATIVE TEST CASES ==========\n")

    for i, test in enumerate(negative_test_cases, start=1):
        print(f"Negative Test Case {i}: {test['name']}")
        print(f"Persona: {test['persona']}")
        print(f"Situation: {test['situation']}")
        print(f"Customer: {test['customer_message']}")
        print(f"Expected: {test['expected']}")
        print("-" * 60)


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    show_positive_test_cases()
    show_negative_test_cases()