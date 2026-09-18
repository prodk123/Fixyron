import urllib.request
import urllib.parse
import json
import time

API_URL = "http://localhost:8000/api/repositories"

REPOSITORIES = [
    {"url": "https://github.com/tiangolo/fastapi", "bug": "Fix routing issue"},
    {"url": "https://github.com/pallets/flask", "bug": "Session bug"},
    {"url": "https://github.com/expressjs/express", "bug": "Middleware bug"},
    {"url": "https://github.com/reduxjs/redux", "bug": "State management bug"}
]

def post_json(url, data):
    req = urllib.request.Request(url, method="POST")
    req.add_header('Content-Type', 'application/json')
    data_bytes = json.dumps(data).encode('utf-8')
    try:
        response = urllib.request.urlopen(req, data=data_bytes)
        return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')

def get_json(url):
    req = urllib.request.Request(url, method="GET")
    try:
        response = urllib.request.urlopen(req)
        return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')

def run_tests():
    for repo in REPOSITORIES:
        print(f"\n--- Testing {repo['url']} ---")
        
        status_code, data = post_json(f"{API_URL}/analyze", {
            "repository_url": repo["url"],
            "bug_description": repo["bug"]
        })
        
        if status_code != 200:
            print(f"FAILED to start analysis: {status_code} - {data}")
            continue
            
        analysis_id = data["analysis_id"]
        print(f"Analysis started. ID: {analysis_id}")
        
        while True:
            poll_status, poll_data = get_json(f"{API_URL}/{analysis_id}")
            if poll_status != 200:
                print(f"FAILED to poll: {poll_status} - {poll_data}")
                break
                
            status = poll_data["status"]
            print(f"Status: {status}")
            
            if status in ("completed", "failed"):
                print(json.dumps(poll_data, indent=2))
                break
                
            time.sleep(3)

if __name__ == "__main__":
    run_tests()
