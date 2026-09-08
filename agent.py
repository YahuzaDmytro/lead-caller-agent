import os
from typing import Any

import httpx
from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    RunContext,
    WorkerOptions,
    cli,
    function_tool,
    inference,
)
from livekit.plugins import respeecher, silero

load_dotenv()

INSTRUCTIONS = """
You are a bank phone agent. Speak English only. Keep it short and polite.

1. Greet the person and introduce yourself as a bank employee.
2. Confirm you reached the right person and ask for their name.
3. Learn their needs and interest. Qualify them. Do not close a sale.
4. When the outcome is clear, call finish_call:
   - qualified: they have a need and should become a lead
   - not_interested: they do not want to continue
   - no_answer: they did not really talk
   - callback: they asked to be called later
5. Then say goodbye.

Do not mention Viber or other messengers.
""".strip()


def message_body(item: Any) -> str:
    content = getattr(item, "text_content", None) or getattr(item, "content", "")
    if isinstance(content, list):
        return " ".join(str(part) for part in content)
    return str(content)


def transcript_from(session: AgentSession) -> list[dict[str, str]]:
    turns: list[dict[str, str]] = []
    for item in getattr(session.history, "items", []):
        role = getattr(item, "role", None)
        if role not in ("user", "assistant"):
            continue
        body = message_body(item).strip()
        if body:
            turns.append({"role": role, "body": body})
    return turns


@function_tool
async def finish_call(
    context: RunContext,
    outcome: str,
    summary: str,
    first_name: str = "",
    last_name: str = "",
    needs: str = "",
    next_step: str = "",
) -> str:
    """Save the call result. outcome must be qualified, not_interested, no_answer, or callback."""
    async with httpx.AsyncClient(
        verify=os.getenv("LARAVEL_VERIFY_SSL", "true").lower() != "false",
        timeout=20.0,
    ) as client:
        response = await client.post(
            f"{os.environ['LARAVEL_WEBHOOK_URL']}/api/calls/{int(context.session.room.name.removeprefix('call-'))}/complete",
            headers={"Authorization": f"Bearer {os.environ['LARAVEL_API_KEY']}"},
            json={
                "first_name": first_name,
                "last_name": last_name,
                "outcome": outcome,
                "needs": needs,
                "next_step": next_step,
                "summary": summary,
                "transcript": transcript_from(context.session),
            },
        )
        response.raise_for_status()

    if outcome == "qualified":
        return "Saved. They are now a lead. Say goodbye."
    if outcome == "callback":
        return "Saved. Confirm you will call back later and say goodbye."
    return "Saved. Thank them and say goodbye."


async def entrypoint(ctx: JobContext):
    await ctx.connect()

    session = AgentSession(
        stt=inference.STT(
            model=os.getenv("LIVEKIT_STT_MODEL", "cartesia/ink-whisper"),
            language=os.getenv("LIVEKIT_STT_LANGUAGE", "en"),
        ),
        llm=inference.LLM(model=os.getenv("LIVEKIT_LLM_MODEL", "google/gemma-4-31b-it")),
        tts=respeecher.TTS(
            model=os.getenv("RESPEECHER_TTS_MODEL", "/public/tts/ua-rt"),
            voice_id=os.getenv("RESPEECHER_VOICE_ID", "olesia-conversation"),
        ),
        vad=silero.VAD.load(),
    )

    await session.start(
        agent=Agent(instructions=INSTRUCTIONS, tools=[finish_call]),
        room=ctx.room,
    )


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
