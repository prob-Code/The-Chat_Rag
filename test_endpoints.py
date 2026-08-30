#!/usr/bin/env python3
"""Test RAG endpoints."""
import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_health():
    """Test health endpoint."""
    print("=" * 60)
    print("PHASE 3: HEALTH CHECK")
    print("=" * 60)
    try:
        r = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"Status Code: {r.status_code}")
        print(f"Response Body: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def test_chat(question):
    """Test chat endpoint."""
    print("\n" + "=" * 60)
    print(f"CHAT TEST: {question[:50]}...")
    print("=" * 60)
    try:
        payload = {"question": question}
        r = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
        print(f"Status Code: {r.status_code}")
        
        if r.status_code == 200:
            response_json = r.json()
            print(f"Response Keys: {list(response_json.keys())}")
            
            if "answer" in response_json:
                answer = response_json["answer"]
                print(f"Answer Present: YES")
                print(f"Answer Length: {len(answer)} chars")
                print(f"Answer Sample: {answer[:200]}...")
            else:
                print(f"Answer Present: NO")
            
            if "sources" in response_json:
                print(f"Sources Present: YES")
                print(f"Sources Count: {len(response_json.get('sources', []))}")
            else:
                print(f"Sources Present: NO")
            
            return True
        else:
            print(f"ERROR Response: {r.text}")
            return False
    except requests.exceptions.Timeout:
        print("ERROR: Request timeout (>30s)")
        return False
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}")
        return False

if __name__ == "__main__":
    # Phase 3: Health
    health_ok = test_health()
    
    if not health_ok:
        print("\nHealth check failed. Stopping.")
        sys.exit(1)
    
    # Phase 4: First chat
    q1 = "What is the Bhagavad Gita?"
    chat1_ok = test_chat(q1)
    
    if not chat1_ok:
        print("\nFirst chat failed. Stopping.")
        sys.exit(1)
    
    # Phase 5: Second chat
    q2 = "What does the Bhagavad Gita teach about remaining calm during difficult situations?"
    chat2_ok = test_chat(q2)
    
    print("\n" + "=" * 60)
    print("PHASE 7: FINAL STATUS")
    print("=" * 60)
    print(f"Health: {'PASS' if health_ok else 'FAIL'}")
    print(f"Chat 1: {'PASS' if chat1_ok else 'FAIL'}")
    print(f"Chat 2: {'PASS' if chat2_ok else 'FAIL'}")
    
    if health_ok and chat1_ok and chat2_ok:
        print("\n✓ RAG implementation works locally!")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed.")
        sys.exit(1)
