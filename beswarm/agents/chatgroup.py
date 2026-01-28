"""
A simplified, declarative implementation of the Beswarm worker agent system,
built using the custom MessageBroker for a high-level pub/sub architecture.
"""
import os
import sys
import uuid
import json
import copy
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Union

from ..broker import MessageBroker
from ..bemcp.bemcp import MCPManager
from ..utils import register_mcp_tools
from ..aient.aient.models import chatgpt
from ..aient.aient.plugins import get_function_call_list, registry

worker_system_prompt = """
你是{name}。帮助用户头脑风暴。请分析不同用户的观点，并给出你的观点。
你的回答必须是 @用户名字开头。后面接上你的回复。如果你觉得无需回答的时候，请直接回复<stop>。
"""

class BaseAgent:
    """Base class for agents, handling common initialization and disposal."""
    def __init__(self, name: str, tools_json: List, agent_config: Dict, work_dir: str, cache_messages: Union[bool, List[Dict]], broker: MessageBroker, listen_topic: str, publish_topic: str, status_topic: str):

        self.id = str(uuid.uuid4())
        self.name = name
        self.tools_json = tools_json
        self.work_dir = work_dir
        self.cache_file = Path(work_dir) / ".beswarm" / "work_agent_conversation_history.json"
        self.config = copy.deepcopy(agent_config)
        self.cache_messages = cache_messages
        if cache_messages and isinstance(cache_messages, bool) and cache_messages == True:
            self.cache_messages = json.loads(self.cache_file.read_text(encoding="utf-8"))
        self.broker = broker
        self.listen_topic = listen_topic
        self.error_topic = listen_topic + ".error"
        self.publish_topic = publish_topic
        self.status_topic = status_topic
        self._subscription = self.broker.subscribe(self.handle_message, [self.listen_topic, self.error_topic])

    async def handle_message(self, message: Dict):
        """Process incoming messages. Must be implemented by subclasses."""
        raise NotImplementedError

    def dispose(self):
        """Cancels the subscription and cleans up resources."""
        if self._subscription:
            self._subscription.dispose()


class WorkerAgent(BaseAgent):
    """Executes instructions and publishes results to a message broker."""
    def __init__(self, name: str, tools_json: List, agent_config: Dict, work_dir: str, cache_messages: Union[bool, List[Dict]], broker: MessageBroker, listen_topic: str, publish_topic: str, status_topic: str):
        super().__init__(name, tools_json, agent_config, work_dir, cache_messages, broker, listen_topic, publish_topic, status_topic)

        self.config["system_prompt"] = self.config["system_prompt"].format(name=self.name)
        self.agent = chatgpt(**self.config)

    async def handle_message(self, message: Dict):
        """Receives an instruction, executes it, and publishes the response."""

        if message.get("id") == self.id:
            return

        instruction = message["result"]
        response = await self.agent.ask_async(instruction)

        if '<stop>' in response.strip():
            if response.replace('<stop>', '').strip() != '':
                self.broker.publish({"id": self.id, "status": "new_message", "result": f"{self.name}: {response.replace('<stop>', '')}\n\n"}, self.status_topic)
            return

        if response.strip() == '':
            print("\n❌ 工作智能体回复为空，请重新生成指令。")
            self.broker.publish(message, self.error_topic)
        else:
            self.broker.publish({"id": self.id, "status": "new_message", "result": f"{self.name}: {response}\n\n"}, self.status_topic)
            self.broker.publish({
                "id": self.id,
                "result": f"{self.name}: {response}"
            }, self.publish_topic)

class Tee:
    def __init__(self, *files):
        self.files = files

    def write(self, obj):
        for f in self.files:
            f.write(obj)
            f.flush()

    def flush(self):
        for f in self.files:
            f.flush()

class ChatGroupWorker:
    """The 'glue' class that orchestrates agents via a MessageBroker."""
    def __init__(self, tools: List[Union[str, Dict]], work_dir: str, cache_messages: Union[bool, List[Dict]] = None, broker: MessageBroker = None, mcp_manager: MCPManager = None, task_manager = None, kgm = None):
        self.tools = tools
        self.work_dir = Path(work_dir)
        self.cache_messages = cache_messages

        self.broker = broker
        self.mcp_manager = mcp_manager
        self.task_manager = task_manager
        self.kgm = kgm
        self.task_completion_event = asyncio.Event()
        self.final_result = None
        self._status_subscription = None
        self.agents = []
        self.setup()

        self.channel = self.broker.request_channel()
        self.WORKER_RESPONSE_TOPIC = self.channel + ".worker_responses"
        self.TASK_STATUS_TOPIC =self.channel +  ".task_status"

    def setup(self):
        cache_dir = self.work_dir / ".beswarm"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.task_manager.set_root_path(self.work_dir)
        self.kgm.set_root_path(self.work_dir)
        self.cache_file = cache_dir / "work_agent_conversation_history.json"
        if not self.cache_file.exists():
            self.cache_file.write_text("[]", encoding="utf-8")

        DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "t", "yes")
        if DEBUG:
            log_file = open(cache_dir / "history.log", "a", encoding="utf-8")
            log_file.write(f"========== {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ==========\n")
            original_stdout = sys.stdout
            original_stderr = sys.stderr
            sys.stdout = Tee(original_stdout, log_file)
            sys.stderr = Tee(original_stderr, log_file)

    async def _configure_tools(self):
        mcp_list = [item for item in self.tools if isinstance(item, dict)]
        if mcp_list:
            for mcp_item in mcp_list:
                mcp_name, mcp_config = list(mcp_item.items())[0]
                await self.mcp_manager.add_server(mcp_name, mcp_config)
                client = self.mcp_manager.clients.get(mcp_name)
                await register_mcp_tools(client, registry)
            all_mcp_tools = await self.mcp_manager.get_all_tools()
            self.tools.extend([tool.name for tool in sum(all_mcp_tools.values(), [])])
        self.tools = [item for item in self.tools if not isinstance(item, dict)]
        if "task_complete" not in self.tools: self.tools.append("task_complete")
        self.tools_json = [value for _, value in get_function_call_list(self.tools).items()]

    def _task_status_subscriber(self, message: Dict):
        """Subscriber for task status changes."""
        if message.get("status") == "finished":
            self.final_result = message.get("result")
            self.task_completion_event.set()

        if message.get("status") == "error":
            raise Exception(message.get("result"))

        if message.get("status") == "new_message":
            print(message.get("result"))
            chat_window = open(self.work_dir / ".beswarm" / "chat_window.md", "a", encoding="utf-8")
            chat_window.write("# " + message.get("result") + "\n")

    def _setup_agents(self):
        worker_agent_config = {
            "api_key": os.getenv("API_KEY"), "api_url": os.getenv("BASE_URL"),
            "engine": os.getenv("FAST_MODEL") or os.getenv("MODEL"),
            "system_prompt": worker_system_prompt,
            "print_log": True, "temperature": 0.5, "function_call_max_loop": 100
        }

        chat_agent1 = WorkerAgent(
            name="数学家", tools_json=self.tools_json, agent_config=worker_agent_config, work_dir=self.work_dir, cache_messages=self.cache_messages,
            broker=self.broker, listen_topic=self.WORKER_RESPONSE_TOPIC,
            publish_topic=self.WORKER_RESPONSE_TOPIC, status_topic=self.TASK_STATUS_TOPIC
        )

        chat_agent2 = WorkerAgent(
            name="哲学家", tools_json=self.tools_json, agent_config=worker_agent_config, work_dir=self.work_dir, cache_messages=self.cache_messages,
            broker=self.broker, listen_topic=self.WORKER_RESPONSE_TOPIC,
            publish_topic=self.WORKER_RESPONSE_TOPIC, status_topic=self.TASK_STATUS_TOPIC
        )
        self.agents = [chat_agent1, chat_agent2]

    async def run(self):
        """Sets up subscriptions and starts the workflow, waiting for user input."""
        os.chdir(self.work_dir.absolute())
        await self._configure_tools()

        self._setup_agents()

        self._status_subscription = self.broker.subscribe(self._task_status_subscriber, self.TASK_STATUS_TOPIC)

        print("开启群聊, 请输入内容开始对话, 输入 'exit' 或 'quit' 结束:")
        loop = asyncio.get_running_loop()

        async def user_input_loop():
            while True:
                try:
                    line = await loop.run_in_executor(None, sys.stdin.readline)
                    line = line.strip()
                    if not line:
                        continue
                    if line.lower() in ['exit', 'quit']:
                        self.task_completion_event.set()
                        break

                    self.broker.publish({"id": "user", "result": f"小蓝: {line}"}, self.WORKER_RESPONSE_TOPIC)
                    self.broker.publish({"id": "user", "status": "new_message", "result": f"小蓝: {line}\n\n"}, self.TASK_STATUS_TOPIC)
                except asyncio.CancelledError:
                    break

        input_task = asyncio.create_task(user_input_loop())

        await self.task_completion_event.wait()

        if not input_task.done():
            input_task.cancel()

        self.cleanup()
        return self.final_result

    async def run_for_web(self):
        """Sets up agents and subscriptions for web-based interaction, then yields messages."""
        os.chdir(self.work_dir.absolute())
        await self._configure_tools()
        self._setup_agents()

        self._status_subscription = self.broker.subscribe(self._task_status_subscriber, self.TASK_STATUS_TOPIC)

        print("Web chat group is running. Waiting for messages...")
        await self.task_completion_event.wait()
        print("Web chat group finished.")
        self.cleanup()

    def cleanup(self):
        """Cleans up resources like agent subscriptions and MCP manager."""
        print("Cleaning up resources...")
        for agent in self.agents:
            agent.dispose()
        if self._status_subscription:
            self._status_subscription.dispose()

        # This needs to be async, so we run it in a new event loop if needed
        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                loop.create_task(self.mcp_manager.cleanup())
            else:
                asyncio.run(self.mcp_manager.cleanup())
        except RuntimeError: # No running loop
            asyncio.run(self.mcp_manager.cleanup())

    async def stream_run(self):
        """Runs the workflow and yields status messages."""
        os.chdir(self.work_dir.absolute())
        await self._configure_tools()

        instruction_agent, worker_agent = self._setup_agents()

        try:
            async for message in self.broker.iter_topic(self.TASK_STATUS_TOPIC):
                if message.get("status") == "new_message":
                    yield message.get("result")
                elif message.get("status") == "finished":
                    yield message.get("result")
                    break
                elif message.get("status") == "error":
                    raise Exception(message.get("result"))
        finally:
            instruction_agent.dispose()
            worker_agent.dispose()
            await self.mcp_manager.cleanup()