import os
import httpx
from dotenv import load_dotenv

from livekit.agents import (
    Agent, AgentSession, JobContext, WorkerOptions, cli, function_tool,
    RunContext,
    UserInputTranscribedEvent, ConversationItemAddedEvent, tokenize,
)
from livekit.agents.llm import ChatMessage
from livekit.agents.tts import StreamAdapter
from livekit.plugins import silero, respeecher

load_dotenv()

LARAVEL_WEBHOOK_URL = os.environ["LARAVEL_WEBHOOK_URL"]
LARAVEL_API_KEY = os.environ["LARAVEL_API_KEY"]


def extract_call_id(room_name: str) -> int:
    return int(room_name.removeprefix("call-"))


async def entrypoint(ctx: JobContext):
    print("=== LiveKit entrypoint started ===")

    await ctx.connect()
    print(f"Room name: {ctx.room.name}")

    call_id = extract_call_id(ctx.room.name)

    @function_tool
    async def save_lead_name(context: RunContext, first_name: str, last_name: str):
        """Called once the caller has provided both their first and last name."""
        print(f">>> save_lead_name called: {first_name} {last_name}")

        url = f"{LARAVEL_WEBHOOK_URL}/api/calls/{call_id}/complete"

        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {LARAVEL_API_KEY}"},
                json={"first_name": first_name, "last_name": last_name},
            )
            print(f"Laravel response status: {response.status_code}")
            print(f"Laravel response body: {response.text}")
            response.raise_for_status()

        return "Saved, you may say goodbye now."

    respeecher_tts = respeecher.TTS(model="/public/tts/en-rt", voice_id="samantha")

    # оборачиваем, чтобы форсировать chunked-режим (.synthesize())
    # вместо родного (пока нестабильного) WebSocket-стриминга Respeecher
    tts = StreamAdapter(
        tts=respeecher_tts,
        sentence_tokenizer=tokenize.basic.SentenceTokenizer(),
    )

    session = AgentSession(
        stt="deepgram/nova-3",
        llm="openai/gpt-4o-mini",
        tts=tts,
        vad=silero.VAD.load(),
    )

    @session.on("user_input_transcribed")
    def on_user_transcribed(event: UserInputTranscribedEvent):
        if event.is_final:
            print(f"[LEAD]: {event.transcript}")

    @session.on("conversation_item_added")
    def on_item_added(event: ConversationItemAddedEvent):
        if isinstance(event.item, ChatMessage) and event.item.role == "assistant":
            print(f"[AGENT]: {event.item.text_content}")

    @session.on("agent_state_changed")
    def on_state_changed(event):
        print(f"[AGENT STATE]: {event.new_state}")

    agent = Agent(
        instructions=(
            "You are calling a bank customer on behalf of the bank. "
            "Greet them, briefly introduce yourself, and politely ask for "
            "their first and last name. As soon as you have both — call "
            "save_lead_name and say a polite goodbye."
        ),
        tools=[save_lead_name],
    )

    await session.start(agent=agent, room=ctx.room)


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
