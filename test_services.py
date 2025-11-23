"""
End-to-end test script for all services
"""

import requests
import time
import sys
from multiprocessing import Process
import uvicorn

def start_transcription_service():
    """Start transcription service"""
    import sys
    sys.path.insert(0, 'src/python')
    from transcription_service import app
    uvicorn.run(app, host="127.0.0.1", port=38421, log_level="error")

def start_llm_service():
    """Start LLM service"""
    import sys
    sys.path.insert(0, 'src/python')
    from llm_service import app
    uvicorn.run(app, host="127.0.0.1", port=45231, log_level="error")

def start_rag_service():
    """Start RAG service"""
    import sys
    sys.path.insert(0, 'src/python')
    from rag_service import app
    uvicorn.run(app, host="127.0.0.1", port=53847, log_level="error")

def test_service_health(service_name, port):
    """Test if service is healthy"""
    url = f"http://127.0.0.1:{port}/health"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"[OK] {service_name} service is healthy on port {port}")
            print(f"  Response: {response.json()}")
            return True
        else:
            print(f"[FAIL] {service_name} service returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] {service_name} service failed: {e}")
        return False

def main():
    """Main test function"""
    print("=" * 60)
    print("Starting Nexus Assistant Services Test")
    print("=" * 60)

    # Start all services in separate processes
    print("\n[1/4] Starting all services...")
    processes = []

    p1 = Process(target=start_transcription_service)
    p1.start()
    processes.append(p1)

    p2 = Process(target=start_llm_service)
    p2.start()
    processes.append(p2)

    p3 = Process(target=start_rag_service)
    p3.start()
    processes.append(p3)

    print("   Services started in background")

    # Wait for services to start
    print("\n[2/4] Waiting 10 seconds for services to initialize...")
    time.sleep(10)

    # Test each service
    print("\n[3/4] Testing service health endpoints...")
    results = []
    results.append(test_service_health("Transcription", 38421))
    results.append(test_service_health("LLM", 45231))
    results.append(test_service_health("RAG", 53847))

    # Check logs
    print("\n[4/4] Checking log files...")
    import os
    logs_to_check = [
        "logs/transcription.log",
        "logs/llm.log",
        "logs/rag.log",
        "logs/activity.log"
    ]

    for log_file in logs_to_check:
        if os.path.exists(log_file):
            size = os.path.getsize(log_file)
            print(f"[OK] {log_file} exists ({size} bytes)")
        else:
            print(f"[FAIL] {log_file} missing")
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)

    if all(results):
        print("[SUCCESS] All tests PASSED")
        exit_code = 0
    else:
        print("[FAILURE] Some tests FAILED")
        exit_code = 1

    # Cleanup - terminate all processes
    print("\n[Cleanup] Stopping all services...")
    for p in processes:
        p.terminate()
        p.join(timeout=2)
        if p.is_alive():
            p.kill()

    print("Done!")
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
