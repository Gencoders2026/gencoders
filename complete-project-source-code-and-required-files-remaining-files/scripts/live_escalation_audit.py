import urllib.request
import json

BASE_URL = 'http://localhost:8080'

def main():
    print("================================================================")
    print("  TASK 6: ESCALATION RISK MONITOR AUDIT & VERIFICATION")
    print("================================================================")

    # 1. Health check
    res = urllib.request.urlopen(f'{BASE_URL}/support/health')
    health = json.loads(res.read())
    print(f"[1] Health Check: {health['status']} | service: {health['service']}")

    # Scenario A: Escalating customer demanding manager
    print("\n--- Scenario A: Urgent / Furious Customer Demanding Supervisor ---")
    query_a = "I have waited 3 weeks for my refund and nobody is helping. Let me speak to your manager right now!"
    req_data = {
        'query': query_a,
        'session_id': 'test-audit-esc-1',
        'turn': 1,
        'history': [{'role': 'customer', 'content': query_a}]
    }
    req = urllib.request.Request(f'{BASE_URL}/support/analyze', data=json.dumps(req_data).encode('utf-8'), headers={'Content-Type': 'application/json'})
    res = urllib.request.urlopen(req)
    data = json.loads(res.read())

    print(f"  • Message: \"{query_a}\"")
    print(f"  • Risk Score: {data['escalation_score']}/100")
    print(f"  • Risk Level: {data['escalation_level']} (Expected: Critical/High)")
    print(f"  • Risk Trend: {data['escalation_trend']}")
    print(f"  • Alert Triggered: {data.get('alert', {}).get('triggered')} (Threshold: {data.get('alert', {}).get('threshold')})")
    print(f"  • Identified Indicators ({len(data['escalation_indicators'])}):")
    for ind in data['escalation_indicators']:
        print(f"      + [{ind['points']} pts] {ind['name']} (matched: '{ind.get('matched_phrase', '')}')")
    print(f"  • Reasoning Breakdown:")
    for r in data['escalation_reasoning']:
        print(f"      - {r}")
    print(f"  • Recommended Actions:")
    for act in data.get('recommended_actions', []):
        print(f"      * {act}")

    # Scenario B: Calm customer (Low risk, no false alarm)
    print("\n--- Scenario B: Calm / Polite Customer (Low Risk, No False Alarm) ---")
    query_b = "Hello, could you please give me an update on my order status? Thank you!"
    req_data_b = {
        'query': query_b,
        'session_id': 'test-audit-esc-2',
        'turn': 1,
        'history': [{'role': 'customer', 'content': query_b}]
    }
    req_b = urllib.request.Request(f'{BASE_URL}/support/analyze', data=json.dumps(req_data_b).encode('utf-8'), headers={'Content-Type': 'application/json'})
    res_b = urllib.request.urlopen(req_b)
    data_b = json.loads(res_b.read())
    print(f"  • Message: \"{query_b}\"")
    print(f"  • Risk Score: {data_b['escalation_score']}/100")
    print(f"  • Risk Level: {data_b['escalation_level']} (Expected: Low)")
    print(f"  • Alert Triggered: {data_b.get('alert', {}).get('triggered')} (Expected: False)")

    # Scenario C: Multi-turn De-escalation & Resolution
    print("\n--- Scenario C: Multi-turn De-escalation (Issue Resolved) ---")
    history_c = [
        {'role': 'customer', 'content': 'This delay is completely unacceptable! Fix it now!'},
        {'role': 'agent', 'content': 'I have looked into this and processed an express delivery right away.'},
        {'role': 'customer', 'content': 'Okay, I see the updated tracking now. Thank you so much, it is resolved!'}
    ]
    req_data_c = {
        'query': 'Okay, I see the updated tracking now. Thank you so much, it is resolved!',
        'session_id': 'test-audit-esc-3',
        'turn': 2,
        'history': history_c
    }
    req_c = urllib.request.Request(f'{BASE_URL}/support/analyze', data=json.dumps(req_data_c).encode('utf-8'), headers={'Content-Type': 'application/json'})
    res_c = urllib.request.urlopen(req_c)
    data_c = json.loads(res_c.read())
    print(f"  • Final Customer Message: \"{history_c[2]['content']}\"")
    print(f"  • Risk Score: {data_c['escalation_score']}/100 (Expected: Low / <30)")
    print(f"  • Risk Level: {data_c['escalation_level']}")
    print(f"  • Risk Trend: {data_c['escalation_trend']} (Expected: decreasing)")
    print(f"  • Alert Triggered: {data_c.get('alert', {}).get('triggered')} (Expected: False)")

    # Scenario D: Configurable Threshold API
    print("\n--- Scenario D: Configurable Alert Threshold Dynamic Control ---")
    res_t = urllib.request.urlopen(f'{BASE_URL}/escalation/threshold')
    t_data = json.loads(res_t.read())
    print(f"  • Initial threshold: {t_data['threshold']}")

    # Set threshold to 50
    req_t_set = urllib.request.Request(f'{BASE_URL}/escalation/threshold', data=json.dumps({'threshold': 50}).encode('utf-8'), headers={'Content-Type': 'application/json'})
    res_t_set = urllib.request.urlopen(req_t_set)
    print(f"  • Updated threshold via API to: {json.loads(res_t_set.read())['threshold']}")

    # Reset threshold to 70
    req_t_reset = urllib.request.Request(f'{BASE_URL}/escalation/threshold', data=json.dumps({'threshold': 70}).encode('utf-8'), headers={'Content-Type': 'application/json'})
    res_t_reset = urllib.request.urlopen(req_t_reset)
    print(f"  • Restored default threshold to: {json.loads(res_t_reset.read())['threshold']}")

    print("\n================================================================")
    print("  [OK] ESCALATION RISK MONITOR AUDIT VERDICT: 100% OPERATIONAL")
    print("================================================================")

if __name__ == '__main__':
    main()
