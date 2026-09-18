import urllib.request
import urllib.parse
import json
import time

API_URL = "http://localhost:8000/api"

def post_json(url, data):
    req = urllib.request.Request(url, method="POST")
    req.add_header('Content-Type', 'application/json')
    data_bytes = json.dumps(data).encode('utf-8')
    try:
        response = urllib.request.urlopen(req, data=data_bytes)
        return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))

def get_json(url):
    req = urllib.request.Request(url, method="GET")
    try:
        response = urllib.request.urlopen(req)
        return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))

def run_tests():
    # 1. Analyze repo
    print(f"\n--- Starting Analysis for Flask ---")
    status_code, data = post_json(f"{API_URL}/repositories/analyze", {
        "repository_url": "https://github.com/pallets/flask",
        "bug_description": "Flask.session returns 500 when accessing it before request context"
    })
    
    if status_code != 200:
        print(f"FAILED to start analysis: {status_code} - {data}")
        return
        
    analysis_id = data["analysis_id"]
    print(f"Analysis started. ID: {analysis_id}")
    
    while True:
        poll_status, poll_data = get_json(f"{API_URL}/repositories/{analysis_id}")
        status = poll_data["status"]
        print(f"Analysis Status: {status}")
        if status in ("completed", "failed"):
            break
        time.sleep(3)
        
    if status == "failed":
        print("Analysis failed.")
        return
        
    # 2. Run existing tests
    print(f"\n--- Running Existing Tests ---")
    status_code, data = post_json(f"{API_URL}/qa/tests/run", {
        "analysis_id": analysis_id
    })
    
    while True:
        status_code, runs = get_json(f"{API_URL}/qa/tests/analysis/{analysis_id}")
        if len(runs) > 0:
            run = runs[0]
            print(f"Test Run Status: {run['status']}")
            if run['status'] != "running":
                print(f"Test Run completed: Passed: {run['tests_passed']}, Failed: {run['tests_failed']}")
                break
        time.sleep(3)
        
    # 3. Reproduce Bug
    print(f"\n--- Reproducing Bug ---")
    status_code, data = post_json(f"{API_URL}/qa/reproduction", {
        "analysis_id": analysis_id,
        "bug_description": "Flask.session returns 500 when accessing it before request context"
    })
    
    reproduction_id = data["id"]
    while True:
        status_code, repro = get_json(f"{API_URL}/qa/reproduction/{reproduction_id}")
        print(f"Reproduction Status: {repro['classification']}")
        if repro['classification'] != "pending":
            print(f"Final Classification: {repro['classification']}")
            print(f"Confidence: {repro.get('confidence')}")
            break
        time.sleep(5)
        
if __name__ == "__main__":
    run_tests()
