 # backend/app.py
import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from tinydb import TinyDB, Query
from pydantic import BaseModel
import uuid
from datetime import datetime, timedelta # New imports

# --- Database Setup ---
# Using TinyDB as a lightweight, free database
db = TinyDB('backend/data.json')
knowledge_base = db.table('knowledge')
requests_db = db.table('requests')

# --- Data Models ---
class IngestRequest(BaseModel):
    caller_id: str
    transcript: str

# --- FastAPI App ---
app = FastAPI()
Req = Query() # Define Query object once

# --- Agent Route (Deliverable 2) ---
@app.post("/agent/ingest")
def handle_agent_ingest(req: IngestRequest):
    """
    Called by the LiveKit agent.
    Checks knowledge base. If answer isn't known, creates a help request.
    """
    print(f"Backend: Received query from {req.caller_id}: '{req.transcript}'")

    # 1. Check Knowledge Base
    result = knowledge_base.search(Req.question.matches(req.transcript, case_sensitive=False))

    if result:
        answer = result[0]['answer']
        print(f"Backend: Found answer: '{answer}'")
        return {"known": True, "answer": answer}
    else:
        # 2. If UNKNOWN: Create a pending help request
        print("Backend: Answer not found. Creating help request.")
        request_id = str(uuid.uuid4())
        requests_db.insert({
            "request_id": request_id,
            "caller_id": req.caller_id,
            "question": req.transcript,
            "status": "pending",
            "created_at": datetime.now().isoformat() # <-- ADDED TIMESTAMP
        })
        
        print(f"SUPERVISOR ALERT: Help needed for question: '{req.transcript}'")
        
        return {"known": False, "request_id": request_id}

# --- Supervisor Routes (Deliverable 3 & 4) ---
@app.post("/resolve")
def handle_supervisor_response(request_id: str = Form(...), answer: str = Form(...)):
    """
    Called when the supervisor submits an answer from the UI.
    """
    print(f"Backend: Supervisor resolving request {request_id} with answer: '{answer}'")
    
    updated_reqs = requests_db.update({"status": "resolved", "answer": answer}, Req.request_id == request_id)
    
    if updated_reqs:
        original_req = requests_db.get(Req.request_id == request_id)
        question = original_req['question']
        knowledge_base.insert({'question': question, 'answer': answer})
        print(f"Backend: Knowledge base updated.")

        caller_id = original_req['caller_id']
        print(f"CALLER ALERT ({caller_id}): 'Hi! Regarding your question '{question}', the answer is: {answer}'")
    
    return RedirectResponse(url="/requests", status_code=303)

@app.get("/requests", response_class=HTMLResponse)
def get_supervisor_ui(request: Request):
    """
    Serves the simple HTML UI for the supervisor
    """
    
    # --- NEW: Handle Timeouts ---
    # Check for requests older than 2 hours and mark them 'unresolved'
    timeout_threshold = datetime.now() - timedelta(hours=2)
    pending = requests_db.search(Req.status == 'pending')
    
    for req in pending:
        req_time = datetime.fromisoformat(req['created_at'])
        if req_time < timeout_threshold:
            print(f"Backend: Request {req['request_id']} timed out. Marking 'unresolved'.")
            requests_db.update({"status": "unresolved"}, Req.request_id == req['request_id'])
    # --- End Timeout Handling ---

    # Get all requests
    pending_requests = requests_db.search(Req.status == 'pending')
    resolved_requests = requests_db.search(Req.status == 'resolved')
    unresolved_requests = requests_db.search(Req.status == 'unresolved') # New
    
    # Generate simple HTML
    html = """
    <html>
        <head><title>Supervisor Panel</title></head>
        <body style="font-family: sans-serif; padding: 20px;">
            <h1>Supervisor Panel</h1>
            
            <h2>Pending Requests</h2>
    """
    if not pending_requests:
        html += "<p>No pending requests.</p>"
    else:
        for req in pending_requests:
            html += f"""
            <div style="border: 1px solid #ccc; padding: 10px; margin-bottom: 10px;">
                <p><strong>Question:</strong> {req['question']}</p>
                <p><strong>From:</strong> {req['caller_id']}</p>
                <p><strong>Received:</strong> {datetime.fromisoformat(req['created_at']).strftime('%Y-%m-%d %H:%M')}</p>
                <form action="/resolve" method="post">
                    <input type="hidden" name="request_id" value="{req['request_id']}">
                    <input type="text" name="answer" placeholder="Type answer here..." style="width: 300px;">
                    <button type="submit">Submit Answer</button>
                </form>
            </div>
            """
            
    html += "<h2>Resolved Requests</h2>"
    if not resolved_requests:
        html += "<p>No resolved requests.</p>"
    else:
        html += "<ul style='list-style-type: none; padding-left: 0;'>"
        for req in resolved_requests:
            html += f"""
            <li style="background: #f4f4f4; padding: 10px; margin-bottom: 5px;">
                <p><strong>Question:</strong> {req['question']}</p>
                <p><strong>Answer:</strong> {req['answer']}</p>
            </li>
            """
        html += "</ul>"

    # --- NEW: Unresolved Section ---
    html += "<h2>Unresolved (Timed-Out) Requests</h2>"
    if not unresolved_requests:
        html += "<p>No unresolved requests.</p>"
    else:
        html += "<ul style='list-style-type: none; padding-left: 0;'>"
        for req in unresolved_requests:
            html += f"""
            <li style="background: #fff0f0; border: 1px solid #d00; color: #555; padding: 10px; margin-bottom: 5px;">
                <p><strong>Question:</strong> {req['question']}</p>
                <p><strong>From:</strong> {req['caller_id']}</p>
                <p><strong>Timed Out:</strong> {datetime.fromisoformat(req['created_at']).strftime('%Y-%m-%d %H:%M')}</p>
            </li>
            """
        html += "</ul>"
            
    html += "</body></html>"
    return HTMLResponse(content=html)

# --- Main entrypoint ---
if __name__ == "__main__":
    if not knowledge_base.all():
        knowledge_base.insert({'question': 'What are your hours?', 'answer': 'We are open 9 AM to 5 PM, Monday to Friday.'})
    
    uvicorn.run(app, host="127.0.0.1", port=8000)