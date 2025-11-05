 # livekit/agent.py
import os
import asyncio
from dotenv import load_dotenv
import requests
from typing import AsyncIterable

from livekit import agents
from livekit.agents import Agent, AgentSession, RoomOutputOptions

# Import the FREE Silero TTS and VOSK STT plugins
from livekit.plugins import silero, vosk 

# ── config ─────────────────────────────────────────────────────────────────────
load_dotenv()
BACKEND_BASE = os.getenv("BACKEND_BASE", "http://127.0.0.1:8000")  # Your FastAPI URL

# ── helper: call FastAPI backend and speak the result ──────────────────────────
# This function is now async
async def _call_backend_and_speak(session: AgentSession, text: str, caller_id: str | None):
    text = (text or "").strip()
    if not text:
        return

    try:
        # Use asyncio.to_thread to run the blocking 'requests' call
        # in a separate thread, so it doesn't block the agent.
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

# ── lightweight agent persona ──────────────────────────────────────────────────
class FrontdeskAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are the Frontdesk assistant. Be polite and concise. "
                "Prefer supervisor-provided answers from the backend."
            )
        )

    # --- FIX: This is the correct way to get STT in v1.2.17 ---
    # The 'process' method receives the STT transcripts
    async def process(self, session: AgentSession, input: AsyncIterable[str]) -> None:
        async for text in input:
            print(f"User said: {text}") # Log what the user said
            
            # Get the caller's ID from the session
            caller_id = session.room.local_participant.identity
            
            await _call_backend_and_speak(session, text, caller_id)

# ── worker entrypoint ───────────────────────────────────────────────────────────
async def entrypoint(ctx: agents.JobContext):
    
    session = AgentSession(
        tts=silero.tts.TTS(),       # Free Text-to-Speech
        stt=vosk.STT(),             # Free Speech-to-Text
    )

    await session.start(
        room=ctx.room,
        agent=FrontdeskAgent(), # Pass the agent *instance*
        # --- FIX: Removed room_input_options ---
        # The agent's 'process' method handles STT, not a callback.
        room_output_options=RoomOutputOptions(),
    )

    print("✅ Agent session started. Saying greeting…")
    # 'session.say' is an async function, so it must be awaited
    await session.say("Hi! Im your Frontdesk assistant. How can I help you today?")

# ── cli runner ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))