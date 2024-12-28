import autogen
from user_proxy_webagent import UserProxyWebAgent
import asyncio


apiKey = "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"
config_list = [{"model": "gpt-4o", "api_key": apiKey}]

llm_config_assistant = {
    "model":"gpt-4o",
    "temperature": 0,
    "config_list": config_list,
        "functions": [
        {
            "name": "ask_expert",
            "description": "Handyman Expert, when provided with issue, he provides a concise report on how to solve the issue",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "Issue Description",
                    }
                },
                "required": ["message"],
            },
        },
    ],
}
llm_config_proxy = {
    "model":"gpt-4o",
    "temperature": 0,
    "config_list": config_list,
}


#############################################################################################
# this is where you put your Autogen logic, here I have a simple 2 agents with a function call
class AutogenChat():
    def __init__(self, chat_id=None, websocket=None):
        self.websocket = websocket
        self.chat_id = chat_id
        self.client_sent_queue = asyncio.Queue()
        self.client_receive_queue = asyncio.Queue()

        self.assistant = autogen.AssistantAgent(
            name="assistant",
            llm_config=llm_config_assistant,
            system_message= """ You are a helpful handyman assistant. Reply TERMINATE when the task is done. If the user has not stated the washer model name or number ask for it. Do not continue gathering information unless you have this information. Ask follow up questions to help gain more insight into the main pain point that is causing the issue, use this to form a detailed report to the tool 'ask_expert(message)'.
                           For instance, if the customer is facing issues with a leak, ask questions like checking the seal of the washing machine door, etc. You can formulate these follow up questions using your know assumptions of the issue. Only ask the 2 questions which will provide you with the most information each time.Use the tool 'ask_expert(message)' to: 1. get a repair cause and solution for fixing the repair, 2. verify the  repair cause and solution of the repair and potentially suggest new repair cause and solution.
                           When you ask a question, always add the word "BRKT" at the end.
                           When you respond with the status add the word TERMINATE """
        )
        self.user_proxy = UserProxyWebAgent(  
            name="user_proxy",
            human_input_mode="ALWAYS", 
            max_consecutive_auto_reply=10,
            is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
            code_execution_config=False,
            function_map={
                "ask_expert": self.ask_expert
            }
        )

        # add the queues to communicate 
        self.user_proxy.set_queues(self.client_sent_queue, self.client_receive_queue)

    async def start(self, message):
        await self.user_proxy.a_initiate_chat(
            self.assistant,
            clear_history=True,
            message=message
        )

    #MOCH Function call 
    def search_db(self, order_number=None, customer_number=None):
        return "Order status: delivered TERMINATE"

    # Define Agent-specific Functions
    def ask_expert(self, message: str) -> str:
        assistant_for_expert = autogen.AssistantAgent(
            name="assistant_for_expert",
            llm_config={
                "temperature": 0,
                "config_list": config_list,
            },
            system_message="You are the handyman Expert, you are an expert at everything regarding fixing samsung washers. When provided with issue, think of possible causes for the issue. When you respond with the status add the word TERMINATE"
        )
        expert = autogen.UserProxyAgent(
            name="expert",
            human_input_mode="NEVER",
            is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
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

