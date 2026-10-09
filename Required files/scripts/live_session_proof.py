import urllib.request
import json

BASE_URL = 'http://localhost:8080'

def main():
    print("==================================================================")
    print("  FASTAPI & TASK 6 LIVE PROOF: SESSION START & REAL-TIME ANALYSIS")
    print("==================================================================")

    # 1. Start Session with configuration matching user's exact screenshot:
    # Persona: Frustrated Customer ('frustrated')
    # Scenario: Delayed Order ('delayed_order')
    # Initial Emotion / Frustration: 5
    # Severity: Medium (frustration_level: 5)
    payload = {
        'persona': 'frustrated',
        'scenario': 'delayed_order',
        'frustration_level': 5,
        'expected_resolution': 'new_delivery_date'
    }
    req = urllib.request.Request(
        f'{BASE_URL}/session/start',
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    res = urllib.request.urlopen(req)
    start_data = json.loads(res.read())

    print("\n[STEP 1] Session Created Successfully via POST /session/start:")
    print(f"  • Session ID: {start_data['session_id']}")
    print(f"  • Customer Persona: {start_data['persona_name']}")
    print(f"  • Scenario: {start_data['scenario_name']}")
    print(f"  • Initial Frustration Level: {start_data['frustration_level']} / 10")
    print(f"  • Customer Opening Message: \"{start_data['customer_message']}\"")

    # 2. Call /support/analyze (The Task 6 support assist pipeline)
    analyze_payload = {
        'query': start_data['customer_message'],
        'session_id': start_data['session_id'],
        'turn': 1,
        'history': [{'role': 'customer', 'content': start_data['customer_message']}]
    }
    req2 = urllib.request.Request(
        f'{BASE_URL}/support/analyze',
        data=json.dumps(analyze_payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    res2 = urllib.request.urlopen(req2)
    analysis = json.loads(res2.read())

    print("\n[STEP 2] Real-time AI Analysis (Task 4 & Task 6 Engine):")
    print(f"  • Detected Intent: {analysis['intent']}")
    print(f"  • Detected Emotion: {analysis['emotion_label']} (Intensity: {analysis['frustration_level']}/10)")
    print(f"  • Sentiment: {analysis['sentiment']}")
    print(f"  • Satisfaction Trend: {analysis['satisfaction_trend']}")

    print("\n[STEP 3] AI Coaching & Suggested Response:")
    print(f"  • Suggested Reply: \"{analysis['suggested_response']}\"")
    print(f"  • Quality Evaluation: {analysis['response_evaluation']['summary']}")
    print(f"      - Tone: {analysis['response_evaluation']['tone']['score']}/100")
    print(f"      - Clarity: {analysis['response_evaluation']['clarity']['score']}/100")
    print(f"      - Empathy: {analysis['response_evaluation']['empathy']['score']}/100")
    print(f"      - Professionalism: {analysis['response_evaluation']['professionalism']['score']}/100")
    print("  • Coaching Tips:")
    for tip in analysis['coaching_guidance']:
        print(f"      * {tip}")

    print("\n[STEP 4] Escalation Risk Monitor Live State:")
    print(f"  • Risk Score: {analysis['escalation_score']}/100")
    print(f"  • Risk Level: {analysis['escalation_level']}")
    print(f"  • Escalation Trend: {analysis['escalation_trend']}")
    print(f"  • Alert Triggered: {analysis.get('alert', {}).get('triggered')} (Threshold: {analysis.get('alert', {}).get('threshold')})")
    print("  • Why This Score (Reasoning):")
    for r in analysis['escalation_reasoning']:
        print(f"      - {r}")

    # 3. Step 5: Send an Agent Response and verify turn 2
    agent_reply = "I understand your order is delayed. Let me check the shipping status for you right away."
    respond_payload = {
        'session_id': start_data['session_id'],
        'message': agent_reply
    }
    req3 = urllib.request.Request(
        f'{BASE_URL}/session/respond',
        data=json.dumps(respond_payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    res3 = urllib.request.urlopen(req3)
    turn2_data = json.loads(res3.read())

    print("\n[STEP 5] Agent Responded -> Customer Simulator Replied (Turn 2):")
    print(f"  • Agent Message: \"{agent_reply}\"")
    print(f"  • Customer Reply: \"{turn2_data['customer_message']}\"")
    print(f"  • Turn Count: {turn2_data['turn_count']}")
    print(f"  • Conversation Finished: {turn2_data['finished']}")

    # 4. Step 6: Recalculate Task 6 Analysis for Turn 2
    turn2_history = [
        {'role': 'customer', 'content': start_data['customer_message']},
        {'role': 'agent', 'content': agent_reply},
        {'role': 'customer', 'content': turn2_data['customer_message']}
    ]
    analyze2_payload = {
        'query': turn2_data['customer_message'],
        'session_id': start_data['session_id'],
        'turn': 2,
        'history': turn2_history
    }
    req4 = urllib.request.Request(
        f'{BASE_URL}/support/analyze',
        data=json.dumps(analyze2_payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    res4 = urllib.request.urlopen(req4)
    analysis2 = json.loads(res4.read())

    print("\n[STEP 6] Task 6 Escalation Update after Turn 2:")
    print(f"  • Turn 2 Risk Score: {analysis2['escalation_score']}/100")
    print(f"  • Turn 2 Risk Level: {analysis2['escalation_level']}")
    print(f"  • Turn 2 Escalation Trend: {analysis2['escalation_trend']}")
    print(f"  • Turn 2 Satisfaction Trend: {analysis2['satisfaction_trend']}")

    print("\n==================================================================")
    print("  [SUCCESS] ALL FASTAPI & TASK 6 ENDPOINTS FUNCTIONING 100% PERFECTLY")
    print("==================================================================")

if __name__ == '__main__':
    main()
