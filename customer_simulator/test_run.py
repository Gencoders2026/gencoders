print("Script started...")

try:
    from simulator import CustomerSimulator

    print("Simulator imported successfully")

    sim = CustomerSimulator(
        persona="frustrated",
        scenario="delayed_order",
        initial_emotion="frustrated",
        severity="high",
        patience=4
    )

    print("Simulator created successfully")

    print("=== Customer Simulator Started ===")
    print("Type 'exit' to stop\n")

    first_message = sim.generate_next_message(
        "Hello! Welcome to customer support. How can I help you today?"
    )
    print("Customer:", first_message)

    while True:
        agent_reply = input("\nYou (Support Agent): ")
        
        if agent_reply.lower().strip() == "exit":
            break

        customer_reply = sim.generate_next_message(agent_reply)
        print("Customer:", customer_reply)

    sim.save_conversation()
    print("\nConversation saved successfully!")

except Exception as e:
    print("\n----- ERROR FOUND -----")
    print(e)
    import traceback
    traceback.print_exc()