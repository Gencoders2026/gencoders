"""Live verification of frustration dynamics, repetition and resolution."""
from simulator import CustomerSimulator, SCENARIOS

print("TEST 1: frustration DECREASES with helpful replies (furious, lvl 9)")
sim = CustomerSimulator(persona="furious", scenario="refund_request",
                        frustration_level=9, use_llm=False)
r = sim.start()
seen = {r["customer_message"]}
print(f"  start: lvl={r['frustration_level']} | {r['customer_message'][:60]}")
for i in range(5):
    r = sim.respond("Your full refund has been processed and confirmed. "
                    "The tracking shows it will arrive in 3-5 business days.")
    msg = r["customer_message"]
    dup = "DUPLICATE!" if msg in seen else "ok"
    seen.add(msg)
    print(f"  turn{i+1}: lvl={r['frustration_level']} "
          f"emotion={r['emotion']['label']} finished={r['finished']} "
          f"{dup} | {msg[:55]}")
    if r["finished"]:
        break

print()
print("TEST 2: frustration INCREASES with poor replies (calm, lvl 2)")
sim2 = CustomerSimulator(persona="polite", scenario="delayed_order",
                         frustration_level=2, use_llm=False)
r2 = sim2.start()
print(f"  start: lvl={r2['frustration_level']}")
for i in range(5):
    r2 = sim2.respond("I cannot help with that right now, please wait, maybe later.")
    print(f"  turn{i+1}: lvl={r2['frustration_level']} "
          f"emotion={r2['emotion']['label']} | {r2['customer_message'][:55]}")

print()
print("TEST 3: resolution detection for each scenario")
resolutions = {
    "refund_request": "Your refund has been processed and the full refund is confirmed.",
    "delayed_order": "Good news, the delivery date is confirmed and your order delivered tomorrow.",
    "payment_failure": "The payment is successful now and the issue is fixed.",
    "account_issue": "Your account access is restored, you can log in now.",
    "cancellation": "Your cancellation is confirmed and the subscription is cancelled.",
}
for scen, res in resolutions.items():
    s = CustomerSimulator(persona="frustrated", scenario=scen,
                          frustration_level=3, use_llm=False)
    s.start()
    r3 = s.respond(res)
    print(f"  {scen}: lvl={r3['frustration_level']} finished={r3['finished']} "
          f"| {r3['customer_message'][:50]}")

print()
print("TEST 4: repetition check - long conversation, same band")
sim4 = CustomerSimulator(persona="angry", scenario="payment_failure",
                         frustration_level=7, use_llm=False)
r4 = sim4.start()
msgs = [r4["customer_message"]]
for i in range(8):
    r4 = sim4.respond("Let me check on that for you.")
    msgs.append(r4["customer_message"])
dups = len(msgs) - len(set(msgs))
print(f"  {len(msgs)} messages, duplicates={dups}")
for m in msgs:
    print("   -", m[:75])
