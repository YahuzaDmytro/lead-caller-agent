import os
import httpx
from dotenv import load_dotenv

from livekit.agents import JobContext, WorkerOptions, cli

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

    print(f"CALL ID: {call_id}")

    url = f"{LARAVEL_WEBHOOK_URL}/api/calls/{call_id}/complete"

    print(f"Laravel URL: {url}")

    print(f"временно без сертификата")
    async with httpx.AsyncClient(verify=False) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {LARAVEL_API_KEY}",
            },
            json={
                "status": "connected",
            },
        )

        print(f"Laravel response status: {response.status_code}")
        print(f"Laravel response body: {response.text}")

        response.raise_for_status()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
        )
    )


# import os
# import httpx
# from dotenv import load_dotenv
#
# from livekit.agents import (
#     Agent, AgentSession, JobContext, WorkerOptions, cli, function_tool
# )
# from livekit.plugins import openai, deepgram, silero
#
# load_dotenv()
#
# LARAVEL_WEBHOOK_URL = os.environ["LARAVEL_WEBHOOK_URL"]
# LARAVEL_API_KEY = os.environ["LARAVEL_API_KEY"]
#
#
# def extract_call_id(room_name: str) -> int:
#     # room_name у нас в формате "call-{id}", как задали в Laravel
#     return int(room_name.removeprefix("call-"))
#
#
# @function_tool
# async def save_lead_name(context, first_name: str, last_name: str):
#     """Вызывается, когда агент получил от лида имя и фамилию."""
#     call_id = extract_call_id(context.session.room.name)
#
#     async with httpx.AsyncClient() as client:
#         await client.post(
#             f"{LARAVEL_WEBHOOK_URL}/api/calls/{call_id}/complete",
#             headers={"Authorization": f"Bearer {LARAVEL_API_KEY}"},
#             json={"first_name": first_name, "last_name": last_name},
#         )
#
#     return "Данные сохранены, можно прощаться."
#
#
# async def entrypoint(ctx: JobContext):
#     await ctx.connect()
#
#     session = AgentSession(
#         stt=deepgram.STT(),
#         llm=openai.LLM(model="gpt-4o-mini"),
#         tts=openai.TTS(),  # временно — обычный TTS, Respeecher подключим позже
#         vad=silero.VAD.load(),
#     )
#
#     agent = Agent(
#         instructions=(
#             "Ты звонишь клиенту банка. Поздоровайся, представься коротко, "
#             "вежливо спроси имя и фамилию. Как только получишь оба значения "
#             "— вызови save_lead_name и вежливо попрощайся."
#         ),
#         tools=[save_lead_name],
#     )
#
#     await session.start(agent=agent, room=ctx.room)
#
#
# if __name__ == "__main__":
#     cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))