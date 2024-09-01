import asyncio
import logging
import os
from contextlib import asynccontextmanager  # noqa: E402
from datetime import datetime
from typing import AsyncIterator, Dict, Iterator, List

import uvicorn  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.responses import HTMLResponse  # noqa: E402
from websockets.sync.client import connect as ws_connect

import autogen
from autogen.io.websockets import IOWebsockets

PORT = 8000

# logger = getLogger(__name__)
logger = logging.getLogger("uvicorn")

# config_list = autogen.config_list_from_json(
#     env_or_file="OAI_CONFIG_LIST",
#     filter_dict={
#         "model": ["gpt-4", "gpt-3.5-turbo", "gpt-3.5-turbo-16k"],
#     },
# )

apiKey = "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"
config_list = [{"model": "gpt-4o", "api_key": apiKey}]

def on_connect(iostream: IOWebsockets) -> None:
    print(f" - on_connect(): Connected to client using IOWebsockets {iostream}", flush=True)

    print(" - on_connect(): Receiving message from client.", flush=True)

    # 1. Receive Initial Message
    initial_msg = iostream.input()

    # 2. Instantiate ConversableAgent
    # agent = autogen.ConversableAgent(
    #     name="chatbot",
    #     system_message="Complete a task given to you and reply TERMINATE when the task is done. If asked about the weather, use tool 'weather_forecast(city)' to get the weather forecast for a city.",
    #     llm_config={
    #         "config_list": autogen.config_list_from_json(
    #             env_or_file="OAI_CONFIG_LIST",
    #             filter_dict={
    #                 "model": ["gpt-4", "gpt-3.5-turbo", "gpt-3.5-turbo-16k"],
    #             },
    #         ),
    #         "stream": True,
    #     },
    # )

    agent = autogen.ConversableAgent(
        name="chatbot",
        system_message="Complete a task given to you and reply TERMINATE when the task is done. If asked about the weather, use tool 'weather_forecast(city)' to get the weather forecast for a city.",
        llm_config={
            "config_list": config_list,
            "stream": True,
        },
    )

    # 3. Define UserProxyAgent
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        system_message="A proxy for the user.",
        is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
        human_input_mode="NEVER",
        max_consecutive_auto_reply=10,
        code_execution_config=False,
    )

    # 4. Define Agent-specific Functions
    def weather_forecast(city: str) -> str:
        return f"The weather forecast for {city} at {datetime.now()} is sunny."

    autogen.register_function(
        weather_forecast, caller=agent, executor=user_proxy, description="Weather forecast for a city"
    )

    # 5. Initiate conversation
    print(
        f" - on_connect(): Initiating chat with agent {agent} using message '{initial_msg}'",
        flush=True,
    )

    # student
    user_proxy.initiate_chat(  # noqa: F704
        agent,
        message=initial_msg,
    )

# with IOWebsockets.run_server_in_thread(on_connect=on_connect, port=8765) as uri:
#     print(f" - test_setup() with websocket server running on {uri}.", flush=True)
#
#     with ws_connect(uri) as websocket:
#         print(f" - Connected to server on {uri}", flush=True)
#
#         print(" - Sending message to server.", flush=True)
#         # websocket.send("2+2=?")
#         websocket.send("Check out the weather in Paris and write a poem about it.")
#
#         while True:
#             message = websocket.recv()
#             message = message.decode("utf-8") if isinstance(message, bytes) else message
#
#             print(message, end="", flush=True)
#
#             if "TERMINATE" in message:
#                 print()
#                 print(" - Received TERMINATE message. Exiting.", flush=True)
#                 break

html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Autogen websocket test</title>
    </head>
    <body>
        <h1>WebSocket Chat</h1>
        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off" value="Write a poem about the current wearther in Paris or London, you choose."/>
            <button>Send</button>
        </form>
        <ul id='messages'>
        </ul>
        <script>
            var ws = new WebSocket("ws://localhost:8080/ws");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                message.appendChild(content)
                messages.appendChild(message)
            };
            function sendMessage(event) {
                var input = document.getElementById("messageText")
                ws.send(input.value)
                input.value = ''
                event.preventDefault()
            }
        </script>
    </body>
</html>
"""


@asynccontextmanager
async def run_websocket_server(app: FastAPI) -> AsyncIterator[None]:
    with IOWebsockets.run_server_in_thread(on_connect=on_connect, port=8080) as uri:
        logger.info(f"Websocket server started at {uri}.")

        yield


app = FastAPI(lifespan=run_websocket_server)


@app.get("/")
async def get() -> HTMLResponse:
    return HTMLResponse(html)


async def start_uvicorn() -> None:
    config = uvicorn.Config(app)
    server = uvicorn.Server(config)
    try:
        await server.serve()  # noqa: F704
    except KeyboardInterrupt:
        logger.info("Shutting down server")


if __name__ == "__main__":
    # set the log level to INFO
    logger.setLevel("INFO")
    asyncio.run(start_uvicorn())