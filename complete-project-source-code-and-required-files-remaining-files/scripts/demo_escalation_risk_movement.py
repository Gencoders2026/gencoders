import json, urllib.request, random
B = 'http://127.0.0.1:8000'
def post(payload):
    req = urllib.request.Request(B + '/support/analyze', data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'}, method='POST')
    # Generous timeout: the first request after a server restart loads the
    # embedding model / knowledge index and can take a while.
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)
def fmt(d):
    return f"emotion={d.get('emotion'):<10} frust={d.get('frustration_level')}/10 risk={d.get('escalation_score'):>3} {d.get('escalation_level'):<8} trend={d.get('escalation_trend','?'):<13} sat={d.get('satisfaction_trend','?')}"
# Same session: angry -> mild -> neutral -> calm -> resolved -> angry again (content-driven, not turn-driven)
sid = 'e2e-' + str(random.randint(1000,9999))
turns = [
 'This is absolutely unacceptable and ridiculous! I demand a supervisor immediately!',
 "I'm a bit annoyed that my order is late. Can you check?",
 'My order number is 12345.',
 'Okay, I understand. Thank you for checking, I appreciate the help.',
 "Perfect, that's resolved. Thank you so much!",
 'Still nothing resolved! Nobody has helped me! Get me a manager NOW!',
]
hist = []
for i, t in enumerate(turns, 1):
    hist.append({'role':'customer','content':t})
    d = post({'query': t, 'session_id': sid, 'turn': i, 'history': list(hist)})
    print(f'T{i}: {fmt(d)}')
    print(f'    msg: {t[:70]}')
