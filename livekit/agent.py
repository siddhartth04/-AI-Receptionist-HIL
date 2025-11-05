 # livekit/agent.py
import os
import asyncio
from dotenv import load_dotenv
import requests

from livekit import agents
# --- FIX: This is the correct import for the event ---
from livekit.agents import AgentSession, RoomOutputOptions, UserInputTranscribedEvent

# Use OpenAI for STT, and the free Silero for TTS
from livekit.plugins import openai, silero 

# ── config ─────────────────────────────────────────────────────────────────────
load_dotenv()
BACKEND_BASE = os.getenv("BACKEND_BASE", "http://127.0.0.1:8000")  # Your FastAPI URL

# ── helper: call FastAPI backend and speak the result ──────────────────────────
async def _call_backend_and_speak(session: AgentSession, text: str, caller_id: str | None):
    text = (text or "").strip()
    if not text:
        return

    try:
        def blocking_post():
            return requests.post(
                f"{BACKEND_BASE}/agent/ingest",
                json={"caller_id": caller_id or "caller1", "transcript": text},
                timeout=10,
            )
        
        r = await asyncio.to_thread(blocking_post)
        r.raise_for_status()
        data = r.json()

    except Exception as e:
        print("Backend error:", e)
        await session.interrupt()
        await session.say("Sorry, my supervisor system is not reachable right now.")
        return

    if data.get("known"):
        await session.interrupt()
        await session.say(data["answer"])
    else:
        await session.interrupt()
        await session.say("Let me check with my supervisor and get back to you.")
        print(f"Help request created: {data.get('request_id')}")

# ── worker entrypoint ───────────────────────────────────────────────────────────
async def entrypoint(ctx: agents.JobContext):
    
    session = AgentSession(
        tts=silero.tts.TTS(),       # Free Text-to-Speech
        stt=openai.stt.STT(),       # OpenAI Speech-to-Text
    )

    # --- FIX: This is the correct way to get STT results in v1.2.17 ---
    # We define a new function and tell the session to call it
    # when it hears the user.
    @session.on("user_input_transcribed")
    async def on_user_input(event: UserInputTranscribedEvent):
        if event.is_final:
            print(f"User said: {event.transcript}")
            caller_id = event.participant.identity
            await _call_backend_and_speak(session, event.transcript, caller_id)
    # --- End of fix ---

    await session.start(
        room=ctx.room,
        # We don't need a custom Agent class anymore
        # We also don't need room_input_options
        room_output_options=RoomOutputOptions(),
    )

    print("✅ Agent session started. Saying greeting…")
    await session.say("Hi! I’m your Frontdesk assistant. How can I help you today?")

# ── cli runner ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))