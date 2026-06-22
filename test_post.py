import requests

try:
    r = requests.post('http://127.0.0.1:8000/chat_fast', json={'question':'Hello, what does the Gita say about worry?'}, timeout=30)
    print('STATUS', r.status_code)
    print(r.text)
except Exception as e:
    import traceback
    traceback.print_exc()
    print('EXC', type(e), e)
