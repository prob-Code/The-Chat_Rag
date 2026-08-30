#!/usr/bin/env python3
"""Test RAG chat endpoints and write results to file."""
import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"
OUTPUT_FILE = "test_results.txt"

def write_result(msg):
    """Append message to output file."""
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

# Clear file
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    f.write("")

write_result("=" * 70)
write_result("PHASE 4 & 5: CHAT ENDPOINT TESTS")
write_result("=" * 70)

# Test 1: First question
q1 = "What is the Bhagavad Gita?"
write_result(f"\nTest 1: {q1}")
write_result("-" * 70)

try:
    payload = {"question": q1}
    r = requests.post(f"{BASE_URL}/chat", json=payload, timeout=60)
    write_result(f"Status Code: {r.status_code}")
    
    if r.status_code == 200:
        try:
            resp_json = r.json()
            write_result(f"Response Keys: {list(resp_json.keys())}")
            write_result(f"Answer Present: {'answer' in resp_json}")
            if "answer" in resp_json and resp_json["answer"]:
                write_result(f"Answer Length: {len(resp_json['answer'])} chars")
                write_result(f"Answer (first 300 chars): {resp_json['answer'][:300]}")
            write_result(f"Sources Present: {'sources' in resp_json}")
            if "sources" in resp_json:
                write_result(f"Sources Count: {len(resp_json.get('sources', []))}")
            write_result("RESULT: PASS")
        except json.JSONDecodeError as e:
            write_result(f"JSON Decode Error: {e}")
            write_result(f"Raw Response: {r.text[:500]}")
            write_result("RESULT: FAIL")
    else:
        write_result(f"Error Response: {r.text[:500]}")
        write_result("RESULT: FAIL")
except Exception as e:
    write_result(f"Exception: {type(e).__name__}: {e}")
    write_result("RESULT: FAIL")

# Test 2: Second question
q2 = "What does the Bhagavad Gita teach about remaining calm during difficult situations?"
write_result(f"\n\nTest 2: {q2[:70]}...")
write_result("-" * 70)

try:
    payload = {"question": q2}
    r = requests.post(f"{BASE_URL}/chat", json=payload, timeout=60)
    write_result(f"Status Code: {r.status_code}")
    
    if r.status_code == 200:
        try:
            resp_json = r.json()
            write_result(f"Response Keys: {list(resp_json.keys())}")
            write_result(f"Answer Present: {'answer' in resp_json}")
            if "answer" in resp_json and resp_json["answer"]:
                write_result(f"Answer Length: {len(resp_json['answer'])} chars")
                write_result(f"Answer (first 300 chars): {resp_json['answer'][:300]}")
            write_result(f"Sources Present: {'sources' in resp_json}")
            if "sources" in resp_json:
                write_result(f"Sources Count: {len(resp_json.get('sources', []))}")
            write_result("RESULT: PASS")
        except json.JSONDecodeError as e:
            write_result(f"JSON Decode Error: {e}")
            write_result(f"Raw Response: {r.text[:500]}")
            write_result("RESULT: FAIL")
    else:
        write_result(f"Error Response: {r.text[:500]}")
        write_result("RESULT: FAIL")
except Exception as e:
    write_result(f"Exception: {type(e).__name__}: {e}")
    write_result("RESULT: FAIL")

write_result("\n" + "=" * 70)
write_result("Tests complete. Results written to this file.")
print("Test script executed. Check test_results.txt")
