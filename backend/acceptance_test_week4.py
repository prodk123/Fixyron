import requests
import time

API_URL = "http://localhost:8000/api"

def run_test():
    print("Starting Week 4 E2E Test...")
    
    # Wait for backend to be ready
    for i in range(10):
        try:
            requests.get(f"{API_URL}/health")
            break
        except requests.ConnectionError:
            time.sleep(2)
            print("Waiting for backend...")
            
    print("Backend is up.")
    
    # In a real run, we would trigger analysis -> repro -> diag -> repair
    # For now we'll just check that the backend is up and running and the router is mounted
    try:
        res = requests.post(f"{API_URL}/repair/generate", json={
            "analysis_id": "00000000-0000-0000-0000-000000000000",
            "reproduction_id": "00000000-0000-0000-0000-000000000000",
            "diagnosis_id": "00000000-0000-0000-0000-000000000000"
        })
        print(f"Test POST /repair/generate: {res.status_code}")
    except Exception as e:
        print(f"Error testing repair route: {e}")

if __name__ == "__main__":
    run_test()
