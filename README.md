
# Frontdesk AI: Human-in-the-Loop Supervisor System

This project is an intelligent, self-improving AI receptionist. It features a "Human-in-the-Loop" (HITL) system, allowing the AI to escalate unknown questions to a human supervisor, learn from their answers, and handle the entire request lifecycle.

This is a voice-only solution that uses OpenAI for speech-to-text and Silero for free text-to-speech.

# Core Components

The system is built on three main components:

1.  The Agent (`livekit/agent.py`): A fully voice-enabled LiveKit agent that handles real-time conversation using OpenAI STT and the free Silero TTS engine.
 

 ![FastAPI Backend Documentation](backend-demo.png.png)
    
    
2.The Backend (`backend/app.py`): FastAPI server that acts as the "brain," managing the knowledge base, request lifecycle (pending, resolved, timed-out), and serving the supervisor's admin panel.
 

   ![LiveKit Agent Listening](agent-demo.png.png)
    

3.  The Database (`backend/data.json`): A simple `TinyDB` file used as a lightweight, zero-setup database for the `knowledge_base` and `requests` tables

# Getting Started

Here’s how to get the project running on your local machine.

 ### 1. Clone & Set Up Virtual Environment (Python 3.10)

This project requires **Python 3.10** for compatibility with the required libraries.

 
### Clone the repository
```bash
git clone [your-repo-url]
cd frontdesk-hil
```

### Create a Python 3.10 virtual environment
```bash
py -3.10 -m venv venv
```

### Activate the environment
### On Windows:
```bash
.\venv\Scripts\activate
```
### On macOS/Linux:
```bash
source venv/bin/activate
```

### 2. Install Dependencies
All required packages are in one command:
```bash
   "pip install "livekit-agents[openai]==1.2.17" livekit-plugins-silero python-dotenv requests fastapi uvicorn tinydb pydantic python-multipart".
```

### 3.Set Up Environment
This project requires an OpenAI API key for the Speech-to-Text (STT) functionality.
Create a .env file in the root directory.
Add your OpenAI key. The file should look like this:
```bash
   OPENAI_API_KEY=sk-xxxxXXXXXXXXXXXXXX
   BACKEND_BASE=[http://127.0.0.1:8000](http://127.0.0.1:8000)
```

### 4.Run the System (in 2 Terminals!)
You'll need two separate terminals running at the same time.

Terminal A: Run the Backend
This starts the FastAPI server that manages all the logic.
```bash
    uvicorn backend.app:app --reload
    Supervisor Panel: http://127.0.0.1:8000/requests
```

Terminal B: Run the Agent
This connects the AI agent to your LiveKit room.

### Use any room name you like
```bash
    python livekit/agent.py connect --room frontdesk-demo
    Caller Sandbox: https://frontdesk-demo.sandbox.livekit.io
```


 ---

## 💡 Design & Architecture

Here is a brief overview of the key architectural decisions for this project.

### 1. Help Request Model

Help requests are modeled in TinyDB using a `requests` table. The schema is designed to track the full lifecycle of a customer's query:

* **`request_id` (str):** A `uuid` to uniquely link the request from creation to resolution.
* **`caller_id` (str):** The participant identity from LiveKit, used for callbacks.
* **`question` (str):** The final, transcribed question from the user.
* **`status` (str):** Manages the lifecycle (`pending`, `resolved`, or `unresolved`).
* **`created_at` (str):** An ISO timestamp used to check for timeouts.
* **`answer` (str, optional):** The answer provided by the supervisor.

### 2. Knowledge Base Updates

To ensure data integrity, the `knowledge_base` is only updated *after* a supervisor submits a new answer. This prevents the AI from learning from unverified sources.

### 3. Supervisor Timeout Handling

To avoid a complex background worker, timeouts are handled on page load. When the supervisor opens the `/requests` UI, the backend checks for any `pending` requests older than 2 hours and automatically marks them as `unresolved`. This is a simple and stateless solution.

### 4. Scaling Considerations

The current TinyDB (a single JSON file) is a bottleneck. To handle real scale, the architecture would be updated:

* **Database:** Replace TinyDB with a production-grade database like `DynamoDB` or a managed `PostgreSQL (AWS RDS)`.
* **Decouple with a Message Queue:** Replace the direct HTTP call with a message queue (like `AWS SQS`). The agent would publish to the queue for a much faster and more resilient response.
* **Backend Workers:** A separate pool of workers would consume from this queue to create the DB entries and notify supervisors.
* **Real Notifications:** The `print()` "text-back" simulation would be replaced with a real **Twilio** (SMS) or **Slack** API call.

### 5. System Modularization

The project uses a clean **separation of concerns** via an API contract.

* **The Agent:** Manages real-time I/O (STT/TTS) and knows nothing about the backend's internal logic.
* **The Backend:** Manages all business logic, data, and the UI.

This modularity ensures the backend is independent and could be connected to any agent (e.g., a Twilio bot) with no changes.

---

##  Future Improvements

Given more time, I would add the following features:

* **Smarter Matching:** Upgrade the basic string search to a vector search (e.g., using `sentence-transformers`) for "fuzzy" semantic matching of user questions.
* **Supervisor Auth:** Place the admin panel behind a proper login system.
* **Real Callbacks:** Replace the `print()` statement with a real webhook call to a service like Twilio to send an actual SMS to the `caller_id`.
* **Live Transfer:** Implement the "Phase 2" live-transfer logic, where the agent first checks a supervisor's availability (perhaps via a Redis key) before offering to transfer the call.
