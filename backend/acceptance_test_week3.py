import urllib.request
import urllib.parse
import json
import time
import sys

API_BASE_URL = "http://localhost:8000/api"
REPO_URL = "https://github.com/pallets/flask" 
BUG_DESC = "Flask.session returns 500 when accessing it before request context"

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

def wait_for_status(url, target_status, timeout=300):
    start = time.time()
    while time.time() - start < timeout:
        status_code, data = get_json(url)
        if status_code != 200:
            raise Exception(f"Failed to fetch status: {status_code} - {data}")
            
        status = data.get("status")
        print(f"Current status of {url}: {status}")
        
        if status in target_status:
            return data
        if status == "failed":
            raise Exception(f"Task failed: {data}")
            
        time.sleep(5)
    raise TimeoutError(f"Timeout waiting for {target_status} on {url}")

def test_week3_workflow():
    print(f"Starting E2E Week 3 Workflow Test on {REPO_URL}")
    
    # 1. Start Analysis
    print("1. Starting Repository Analysis...")
    status_code, data = post_json(f"{API_BASE_URL}/repositories/analyze", {
        "repository_url": REPO_URL,
        "bug_description": BUG_DESC
    })
    
    if status_code != 200:
        print(f"Failed to start analysis: {data}")
        sys.exit(1)
        
    analysis_id = data["analysis_id"]
    
    analysis = wait_for_status(f"{API_BASE_URL}/repositories/{analysis_id}", ["completed"])
    print(f"Analysis completed: {analysis['repository']['primary_language']} framework: {analysis['testing']['framework']}")
    
    # 2. Trigger Bug Reproduction
    print("2. Triggering Bug Reproduction...")
    status_code, data = post_json(f"{API_BASE_URL}/qa/reproduction", {
        "analysis_id": analysis_id,
        "bug_description": BUG_DESC
    })
    
    if status_code != 200:
        print(f"Failed to trigger reproduction: {data}")
        sys.exit(1)
        
    repro_id = data["id"]
    
    # QA classification is stored in a different field
    start = time.time()
    repro = None
    while time.time() - start < 300:
        status_code, data = get_json(f"{API_BASE_URL}/qa/reproduction/{repro_id}")
        if status_code != 200:
             raise Exception(f"Failed to fetch repro: {status_code} - {data}")
        
        classification = data.get("classification")
        print(f"Current repro classification: {classification}")
        if classification in ["reproduced", "not_reproduced", "inconclusive"]:
             repro = data
             break
        time.sleep(5)
        
    if not repro:
         raise TimeoutError("Timeout waiting for reproduction to complete")
         
    print(f"Reproduction completed: {repro['classification']} with confidence {repro.get('confidence')}")
    
    # Check if we can proceed to diagnosis
    if repro['classification'] == "inconclusive" or not repro.get('evidence'):
        print("Reproduction inconclusive or missing evidence, skipping diagnosis in this test run.")
        return
        
    # 3. Trigger Diagnosis
    print("3. Triggering Diagnosis...")
    status_code, data = post_json(f"{API_BASE_URL}/diagnosis/analyze", {
        "analysis_id": analysis_id,
        "reproduction_id": repro_id
    })
    
    if status_code != 200:
        print(f"Failed to trigger diagnosis: {data}")
        sys.exit(1)
        
    diag_id = data["id"]
    
    diag = wait_for_status(f"{API_BASE_URL}/diagnosis/{diag_id}", ["completed", "inconclusive"])
    print(f"Diagnosis completed: {diag['status']}")
    if diag['status'] == 'completed':
        print(f"Root Cause: {diag['root_cause']}")
        print(f"Confidence: {diag['confidence']} ({diag['confidence_level']})")
        print(f"Affected Files: {diag['affected_files']}")
    
    print("Week 3 E2E Test Passed Successfully!")

if __name__ == "__main__":
    test_week3_workflow()
