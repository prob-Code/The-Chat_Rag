# Test script for RagGita API
"""
Test your deployed RagGita API before going live.
"""
import requests
import sys
import json


def test_api(base_url: str):
    """Test all API endpoints"""
    results = {"passed": 0, "failed": 0, "tests": []}

    # Test 1: Health check
    print("\n1. Testing health endpoint...")
    try:
        response = requests.get(f"{base_url}/health", timeout=30)
        if response.status_code == 200:
            print(f"   PASS - Health check: {response.json()}")
            results["passed"] += 1
        else:
            print(f"   FAIL - Status: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   FAIL - Error: {e}")
        results["failed"] += 1

    # Test 2: Root endpoint
    print("\n2. Testing root endpoint...")
    try:
        response = requests.get(f"{base_url}/", timeout=30)
        if response.status_code == 200:
            print(f"   PASS - Root: {response.json()}")
            results["passed"] += 1
        else:
            print(f"   FAIL - Status: {response.status_code}")
            results["failed"] += 1
    except Exception as e:
        print(f"   FAIL - Error: {e}")
        results["failed"] += 1

    # Test 3: Chat endpoint
    print("\n3. Testing chat endpoint...")
    try:
        response = requests.post(
            f"{base_url}/chat",
            json={"question": "What is the purpose of life according to the Gita?"},
            timeout=120
        )
        if response.status_code == 200:
            data = response.json()
            answer = data.get("answer", "")[:100] + "..." if len(data.get("answer", "")) > 100 else data.get("answer", "")
            print(f"   PASS - Chat response received")
            print(f"   Preview: {answer}")
            results["passed"] += 1
        else:
            print(f"   FAIL - Status: {response.status_code}, Body: {response.text}")
            results["failed"] += 1
    except Exception as e:
        print(f"   FAIL - Error: {e}")
        results["failed"] += 1

    # Summary
    print("\n" + "=" * 50)
    print(f"Results: {results['passed']} passed, {results['failed']} failed")
    print("=" * 50)

    return results["failed"] == 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test RagGita API")
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)"
    )
    args = parser.parse_args()

    print(f"Testing API at: {args.url}")
    success = test_api(args.url)
    sys.exit(0 if success else 1)
