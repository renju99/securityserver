import requests
import json
import time

API_URL = "http://localhost:8000"

def test_email_flow():
    # 1. Create Draft
    payload = {
        "template_name": "Capex_Template_New.docx",
        "department": "IT",
        "doc_type": "Capex",
        "form_data": {
            "staff_name": "Test User",
            "justification": "Test Request for Email Log"
        },
        "requester_email": "test@berkeleyuae.com"
    }
    
    print("Creating draft...")
    res = requests.post(f"{API_URL}/requests", json=payload)
    if res.status_code != 200:
        print(f"Failed to create draft: {res.text}")
        # Try finding a template that exists if this fails
        return
    
    req_id = res.json()["id"]
    print(f"Created Request ID: {req_id}")
    
    # 2. Submit Request
    print(f"Submitting request {req_id}...")
    res = requests.post(f"{API_URL}/requests/{req_id}/submit")
    if res.status_code != 200:
        print(f"Submit failed: {res.text}")
        return
    print("Submit success.")
    
    # 3. Check Email Logs
    print("Checking email logs...")
    time.sleep(2) 
    res = requests.get(f"{API_URL}/email-logs")
    if res.status_code != 200:
        print(f"Failed to get logs: {res.text}")
        return
        
    logs = res.json()
    found_log = False
    # Sort logs by id desc usually, but just find matches
    for log in logs:
        # Check against request_id
        if log.get("request_id") == req_id:
            print(f"Found Log: ID={log['id']}, Recipient={log['recipient']}, Status={log['status']}, Error={log.get('error_message')}")
            found_log = True
            break
            
    if found_log:
        print("SUCCESS: Email log entry verified.")
    else:
        print("FAILURE: No email log found for this request.")
        print("Recent logs:", logs[:3])

if __name__ == "__main__":
    test_email_flow()
