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

apiKey = "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"
config_list = [{"model": "gpt-4o", "api_key": apiKey}]


def on_connect(iostream: IOWebsockets) -> None:
    print(f" - on_connect(): Connected to client using IOWebsockets {iostream}", flush=True)
    print(" - on_connect(): Receiving message from client.", flush=True)

    # 1. Receive Initial Message
    initial_msg = iostream.input()

    # 2. Instantiate ConversableAgent

    # assistant_for_student
    agent = autogen.ConversableAgent(
        name="handyman-co",
        system_message="You are a helpful handyman assistant. Reply TERMINATE when the task is done. If the user has not stated the washer model name or number ask for it. Do not continue gathering information unless you have this information. Ask follow up questions to help gain more insight into the main pain point that is causing the issue, use this to form a detailed report to the tool 'ask_expert(message)'."
                       "For instance, if the customer is facing issues with a leak, ask questions like checking the seal of the washing machine door, etc. You can formulate these follow up questions using your know assumptions of the issue. Only ask the 2 questions which will provide you with the most information each time.Use the tool 'ask_expert(message)' to: 1. get a repair cause and solution for fixing the repair, 2. verify the  repair cause and solution of the repair and potentially suggest new repair cause and solution.",
        llm_config={
            "config_list": config_list,
            "stream": True,
        },
    )



    # 3. Define UserProxyAgent

    # student
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        system_message="A STUDENT proxy for the user.",
        is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
        human_input_mode="TERMINATE",
        max_consecutive_auto_reply=1,
        code_execution_config=False,
    )

    # 4. Define Agent-specific Functions
    def ask_expert(message: str) -> str:
        assistant_for_expert = autogen.AssistantAgent(
            name="assistant_for_expert",
            llm_config={
                "temperature": 0,
                "config_list": config_list,
            },
            system_message="You are the handyman Expert, you are an expert at everything regarding fixing samsung washers. When provided with issue, think of possible causes for the issue"
        )
        expert = autogen.UserProxyAgent(
            name="expert",
            human_input_mode="ALWAYS",
            code_execution_config=False,
            # Please set use_docker=True if docker is available to run the generated code. Using docker is safer than running the generated code directly.
        )

        expert.initiate_chat(assistant_for_expert, message=message)
        expert.stop_reply_at_receive(assistant_for_expert)
        # expert.human_input_mode, expert.max_consecutive_auto_reply = "NEVER", 0
        # final message sent from the expert
        expert.send("summarize the issue in an easy-to-understand way and professional way", assistant_for_expert)
        # return the last message the expert received
        return expert.last_message()["content"]

    # 5. Initiate conversation
    print(
        f" - on_connect(): Initiating chat with agent {agent} using message '{initial_msg}'",
        flush=True,
    )

    autogen.register_function(
        ask_expert, caller=agent, executor=user_proxy,
        description="Expert for Washing Machine Repair Causes and Solutions"
    )

    # student
    user_proxy.initiate_chat(  # noqa: F704
        agent,
        message=initial_msg,
    )




html = """
<!DOCTYPE html>
<html>
    <head>
        <title>Handyman Copilot websocket HTML</title>
    </head>
    <body>
        <h1>Handyman Copilot WebSocket Chat</h1>

        <p id='messages'>
        </p>

        <form action="" onsubmit="sendMessage(event)">
            <input type="text" id="messageText" autocomplete="off"/>
            <button>Send</button>
        </form>

        <script>
            var ws = new WebSocket("ws://localhost:8080/ws");
            ws.onmessage = function(event) {
                var messages = document.getElementById('messages')
                // var message = document.createElement('li')
                var content = document.createTextNode(event.data)
                messages.appendChild(content)
                // messages.appendChild(message) 

                // Check if the message contains the word "break"
                if (event.data.includes('--------------------------------------------------------------------------------')){
                    // If it contains the string, append a line break
                    messages.appendChild(document.createElement('br'));
                }

                // messages.appendChild(document.createElement('br'));
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