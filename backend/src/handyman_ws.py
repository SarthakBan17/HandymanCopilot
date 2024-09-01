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

    # assistant_for_student
    agent = autogen.ConversableAgent(
        name="chatbot",
        system_message="You are a helpful handyman assistant. Reply TERMINATE when the task is done. If the user has not stated the washer model name or number ask for it. Do not continue gathering information unless you have this information. Ask follow up questions to help gain more insight into the main pain point that is causing the issue, use this to form a detailed report to the tool 'ask_expert(message)'."
                        "For instance, if the customer is facing issues with a leak, ask questions like checking the seal of the washing machine door, etc. You can formulate these follow up questions using your know assumptions of the issue. Only ask the 2 questions which will provide you with the most information each time.Use the tool 'ask_expert(message)' to: 1. get a repair cause and solution for fixing the repair, 2. verify the  repair cause and solution of the repair and potentially suggest new repair cause and solution.",
        llm_config={
            "config_list": config_list,
            "stream": True,
        },
    )

    # assistant_for_student = AssistantAgent(
    #     name="assistant_for_student",
    #     system_message="You are a helpful handyman assistant. Reply TERMINATE when the task is done. If the user has not stated the washer model name or number ask for it. Do not continue gathering information unless you have this information. Ask follow up questions to help gain more insight into the main pain point that is causing the issue, use this to form a detailed report to ask the expert."
    #                    "For instance, if the customer is facing issues with a leak, ask questions like checking the seal of the washing machine door, etc. You can formulate these follow up questions using your know assumptions of the issue. Only ask the 2 questions which will provide you with the most information each time. Use the tool ask expert to: 1. get a repair cause and solution for fixing the repair, 2. verify the  repair cause and solution of the repair and potentially suggest new repair cause and solution.",
    #     llm_config={
    #         "timeout": 600,
    #         "cache_seed": 42,
    #         "config_list": config_list,
    #         "temperature": 0,
    #         "functions": [
    #             {
    #                 "name": "ask_expert",
    #                 "description": "ask expert to: 1. get a repair cause and solution for fixing the repair, 2. verify the  repair cause and solution of the repair and potentially suggest new repair cause and solution.",
    #                 "parameters": {
    #                     "type": "object",
    #                     "properties": {
    #                         "message": {
    #                             "type": "string",
    #                             "description": "Complete report to ask expert. Ensure the report includes enough context, such as information about error code and any further diagnostics. The expert does not know the conversation between you and the user unless you share the conversation with the expert.",
    #                         },
    #                     },
    #                     "required": ["message"],
    #                 },
    #             }
    #         ],
    #     },
    # )

    # 3. Define UserProxyAgent
    # user_proxy = autogen.UserProxyAgent(
    #     name="user_proxy",
    #     system_message="A proxy for the user.",
    #     is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
    #     human_input_mode="NEVER",
    #     max_consecutive_auto_reply=10,
    #     code_execution_config=False,
    # )

    # student
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        system_message="A STUDENT proxy for the user.",
        is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
        human_input_mode="TERMINATE",
        max_consecutive_auto_reply=3,
        code_execution_config=False,
    )
    # old code
    # student = UserProxyAgent(
    #     name="student",
    #     human_input_mode="TERMINATE",
    #     max_consecutive_auto_reply=3,
    #     code_execution_config={
    #         "work_dir": "student",
    #         "use_docker": False,
    #     },
    #     # Please set use_docker=True if docker is available to run the generated code. Using docker is safer than running the generated code directly.
    #     function_map={"ask_expert": ask_expert},
    # )

    # 4. Define Agent-specific Functions
    def weather_forecast(city: str) -> str:
        return f"The weather forecast for {city} at {datetime.now()} is sunny."

    autogen.register_function(
        weather_forecast, caller=agent, executor=user_proxy, description="Weather forecast for a city"
    )

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
        ask_expert, caller=agent, executor=user_proxy, description="Expert for Washing Machine Repair Causes and Solutions"
    )

    # student
    user_proxy.initiate_chat(  # noqa: F704
        agent,
        message=initial_msg,
    )

    # # the assistant receives a message from the student, which contains the task description
    # student.initiate_chat(
    #     assistant_for_student,
    #     message="""My washer is not spinning.""",
    # )

with IOWebsockets.run_server_in_thread(on_connect=on_connect, port=8765) as uri:
    print(f" - test_setup() with websocket server running on {uri}.", flush=True)

    with ws_connect(uri) as websocket:
        print(f" - Connected to server on {uri}", flush=True)

        print(" - Sending message to server.", flush=True)
        # websocket.send("2+2=?")
        # websocket.send("Check out the weather in Paris and write a poem about it.")
        websocket.send("Samsung Washer is not spinning.")

        while True:
            message = websocket.recv()
            message = message.decode("utf-8") if isinstance(message, bytes) else message

            print(message, end="", flush=True)

            if "TERMINATE" in message:
                print()
                print(" - Received TERMINATE message. Exiting.", flush=True)
                break
