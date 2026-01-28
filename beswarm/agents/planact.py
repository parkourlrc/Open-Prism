import os
import re
import copy
import json
import difflib
import asyncio
import tomllib
from pathlib import Path
from typing import List, Dict, Union

from ..broker import MessageBroker
from ..aient.aient.models import chatgpt
from ..aient.aient.plugins import get_function_call_list, registry
from ..prompt import worker_system_prompt, instruction_system_prompt, Goal
from ..utils import extract_xml_content, get_current_screen_image_message, register_mcp_tools, setup_logger
from ..aient.aient.models.chatgpt import ModelNotFoundError, TaskComplete, RetryFailedError, InputTokenCountExceededError, BadRequestError
from ..aient.aient.architext.architext import Messages, UserMessage, Texts

try:
    from importlib import metadata
    version = metadata.version("beswarm")
except metadata.PackageNotFoundError:
    try:
        beswarm_dir = Path(__file__).parent.parent.parent
        with open(beswarm_dir / "pyproject.toml", "rb") as f:
            pyproject_data = tomllib.load(f)
            version = pyproject_data["project"]["version"]
    except FileNotFoundError:
        version = "unknown"

class BaseAgent:
    """Base class for agents, handling common initialization and disposal."""
    def __init__(self, goal: str, tools_json: List, agent_config: Dict, work_dir: str, cache_messages: Union[bool, List[Dict]], broker: MessageBroker, listen_topic: str, publish_topic: str, status_topic: str):
        self.goal = goal
        self.tools_json = tools_json
        self.work_dir = work_dir
        self.pkl_file = Path(work_dir) / ".beswarm" / "history.pkl"
        self.cache_file = Path(work_dir) / ".beswarm" / "work_agent_conversation_history.json"
        self.config = agent_config
        self.logger = agent_config.get("logger", None)
        self.cache_messages = cache_messages
        if cache_messages and isinstance(cache_messages, bool) and cache_messages:
            self.cache_messages = Messages.load(self.pkl_file)
        self.broker = broker
        self.listen_topic = listen_topic
        self.error_topic = listen_topic + ".error"
        self.publish_topic = publish_topic
        self.status_topic = status_topic

        self._subscription = self.broker.subscribe(self.handle_message, [self.listen_topic, self.error_topic])

        self.graph_tree = None

    async def handle_message(self, message: Dict):
        """Process incoming messages. Must be implemented by subclasses."""
        raise NotImplementedError

    def dispose(self):
        """Cancels the subscription and cleans up resources."""
        if self._subscription:
            self._subscription.dispose()


class InstructionAgent(BaseAgent):
    """Generates instructions and publishes them to a message broker."""
    def __init__(self, goal: str, tools_json: List, agent_config: Dict, work_dir: str, cache_messages: Union[bool, List[Dict]], broker: MessageBroker, listen_topic: str, publish_topic: str, status_topic: str):
        super().__init__(goal, tools_json, agent_config, work_dir, cache_messages, broker, listen_topic, publish_topic, status_topic)

        self.last_instruction = None
        self.agent = chatgpt(**self.config)

        self.goal_diff = None

        if self.cache_messages and self.cache_messages.provider("goal"):
            old_goal = self.cache_messages.provider("goal").content
            if old_goal.strip() != goal.strip():
                diff_generator = difflib.ndiff(old_goal.splitlines(), goal.splitlines())
                changed_lines = []
                for line in diff_generator:
                    if (line.startswith('+ ') or line.startswith('- ')) and line[2:].strip():
                        changed_lines.append(line)
                self.goal_diff = '\n'.join(changed_lines).strip()

    async def get_conversation_history(self, raw_conversation_history: List[Dict]):
        conversation_history = copy.deepcopy(raw_conversation_history)
        conversation_history.save(self.pkl_file)
        self.cache_file.write_text(json.dumps(await conversation_history.render_latest(), ensure_ascii=False, indent=4), encoding="utf-8")
        latest_file_content = conversation_history.pop("files")
        conversation_history.pop(0)
        if conversation_history and latest_file_content:
            conversation_history[0] = latest_file_content + conversation_history[0]

        return conversation_history

    async def handle_message(self, message: Dict):
        """Receives a worker response, generates the next instruction, and publishes it."""
        goal = await message["conversation"].provider("goal").render() if message["conversation"].provider("goal") else Goal(self.goal)

        instruction_prompt = "".join([
                "</work_agent_conversation_end>\n\n",
                f"任务目标: {goal}\n\n",
                f"任务目标新变化：\n{self.goal_diff}\n\n" if self.goal_diff else "",
                "在 tag <work_agent_conversation_start>...</work_agent_conversation_end> 之前的对话历史都是工作智能体的对话历史。\n\n",
                "根据以上对话历史和目标，请生成下一步指令。如果任务已完成，指示工作智能体调用task_complete工具。\n\n",
            ])
        if self.last_instruction and "HTTP Error', 'status_code'" not in self.last_instruction:
            instruction_prompt = (
                f"{instruction_prompt}\n\n"
                "你生成的指令格式错误，必须把给assistant的指令放在<instructions>...</instructions>标签内。请重新生成格式正确的指令。"
                f"这是你上次给assistant的错误格式的指令：\n{self.last_instruction}"
            )

        self.agent.conversation["default"][1:] = await self.get_conversation_history(message["conversation"])

        if "find_and_click_element" in json.dumps(self.tools_json):
            instruction_prompt = await get_current_screen_image_message(instruction_prompt)

        try:
            raw_response = await self.agent.ask_async(instruction_prompt)
        except ModelNotFoundError as e:
            raise Exception(str(e))
        except RetryFailedError:
            self.logger.error("❌ Commander retry failed, retrying...")
            self.broker.publish(message, self.error_topic)
            return
        except InputTokenCountExceededError:
            self.broker.publish({"status": "error", "result": "The request body is too long, please try again."}, self.status_topic)
            return
        except BadRequestError:
            self.broker.publish({"status": "error", "result": "Bad request error!"}, self.status_topic)
            return

        self.broker.publish({"status": "new_message", "result": "\n🤖 指令智能体:\n" + raw_response}, self.status_topic)

        instruction = extract_xml_content(raw_response, "instructions")
        if instruction:
            if len(message["conversation"]) == 1:
                instruction = re.sub(r'^<task_complete>([\D\d\s]+)<\/task_complete>$', '', instruction, flags=re.MULTILINE)
                instruction = (
                    "任务描述：\n"
                    f"{goal}\n\n"
                    "你作为指令的**执行者**，而非任务的**规划师**，你必须严格遵循以下单步工作流程：\n"
                    "**执行指令**\n"
                    "   - **严格遵从：** 只执行我当前下达的明确指令。在我明确给出下一步指令前，绝不擅自行动或推测、执行任何未明确要求的后续步骤。\n"
                    "   - **严禁越权：** 禁止执行任何我未指定的步骤。`<goal>` 标签中的内容仅为背景信息，不得据此进行任务规划或推测。\n"
                    "**汇报结果**\n"
                    "   - **聚焦单步：** 指令完成后，仅汇报该步骤的执行结果与产出。\n"
                    "**暂停等待**\n"
                    "   - **原地待命：** 汇报后，任务暂停。在收到我新的指令前，严禁发起任何新的工具调用或操作。\n"
                    "   - **请求指令：** 回复的最后必须明确请求我提供下一步指令。\n"
                    "**注意：** 禁止完成超出下面我未规定的步骤，`<goal>` 标签中的内容仅为背景信息。"
                    "现在开始执行第一步：\n"
                    f"{instruction}"
                )
            self.broker.publish({"instruction": instruction, "conversation": message["conversation"]}, self.publish_topic)
            self.last_instruction = None
        else:
            self.logger.error("\n❌ 指令智能体生成的指令不符合要求，正在重新生成。")
            self.broker.publish(message, self.error_topic)
            self.last_instruction = raw_response


class WorkerAgent(BaseAgent):
    """Executes instructions and publishes results to a message broker."""
    def __init__(self, goal: str, tools_json: List, agent_config: Dict, work_dir: str, cache_messages: Union[bool, List[Dict]], broker: MessageBroker, listen_topic: str, publish_topic: str, status_topic: str):
        super().__init__(goal, tools_json, agent_config, work_dir, cache_messages, broker, listen_topic, publish_topic, status_topic)

        if self.cache_messages and isinstance(self.cache_messages, Messages) and len(self.cache_messages) > 1:
            if self.cache_messages.provider("goal"):
                self.cache_messages.provider("goal").update(goal)
            else:
                self.cache_messages[1].insert(0, Goal(goal))
            self.config["cache_messages"] = self.cache_messages

        self.agent = chatgpt(**self.config)

    async def handle_message(self, message: Dict):
        """Receives an instruction, executes it, and publishes the response."""

        if message.get("instruction") == "Initial kickoff":
            self.broker.publish({
                "conversation": self.agent.conversation["default"]
            }, self.publish_topic)
            return

        instruction = message["instruction"]
        if "find_and_click_element" in json.dumps(self.tools_json):
            instruction = await get_current_screen_image_message(instruction)

        try:
            response = await self.agent.ask_async(UserMessage(instruction, Texts("\n\nYour message **must** end with [done] to signify the end of your output.", name="done")))
        except TaskComplete as e:
            self.broker.publish({"status": "finished", "result": e.completion_message}, self.status_topic)
            return
        except InputTokenCountExceededError:
            self.broker.publish({"status": "error", "result": "The request body is too long, please try again."}, self.status_topic)
            return
        except BadRequestError:
            self.broker.publish({"status": "error", "result": "Bad request error!"}, self.status_topic)
            return
        except RetryFailedError:
            self.logger.error("❌ Worker retry failed, retrying...")
            self.broker.publish(message, self.error_topic)
            return

        if response.strip() == '':
            self.logger.error("\n❌ Worker response is empty, retrying...")
            self.broker.publish(message, self.error_topic)
        else:
            self.broker.publish({"status": "new_message", "result": "\n✅ 工作智能体:\n" + response}, self.status_topic)
            if self.agent.conversation["default"][-1].role == "user":
                self.agent.conversation["default"][-1].rstrip(Texts)
            self.broker.publish({
                "conversation": self.agent.conversation["default"]
            }, self.publish_topic)

class BrokerWorker:
    """The 'glue' class that orchestrates agents via a MessageBroker."""
    def __init__(self, goal: str, tools: List[Union[str, Dict]], work_dir: str, cache_messages: Union[bool, List[Dict]] = None, broker = None, mcp_manager = None, task_manager = None, kgm = None):
        self.goal = goal
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

        self.channel = self.broker.request_channel()
        self.INSTRUCTION_TOPIC = self.channel + ".instructions"
        self.WORKER_RESPONSE_TOPIC = self.channel + ".worker_responses"
        self.TASK_STATUS_TOPIC =self.channel +  ".task_status"

    async def setup(self):
        cache_dir = self.work_dir / ".beswarm"
        cache_dir.mkdir(parents=True, exist_ok=True)
        await self.task_manager.set_root_path(self.work_dir)
        self.kgm.set_root_path(self.work_dir)
        self.cache_file = cache_dir / "work_agent_conversation_history.json"
        if not self.cache_file.exists():
            self.cache_file.write_text("[]", encoding="utf-8")

        # 创建一个文件处理器，将日志写入任务自己的目录
        log_file_path = cache_dir / "agent.log"
        self.logger = setup_logger(str(log_file_path.parent.parent.absolute()), log_file_path)
        self.logger.info(f"beswarm version: {version}")
        self.logger.info(f"Logger for task '{self.goal}' initialized. Log file: {log_file_path}")

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
        if "task_complete" not in self.tools:
            self.tools.append("task_complete")
        self.tools_json = [value for _, value in get_function_call_list(self.tools).items()]

    def _task_status_subscriber(self, message: Dict):
        """Subscriber for task status changes."""
        if message.get("status") == "finished":
            self.logger.info("Task completed: " + message.get("result"))
            self.final_result = message.get("result")
            self.task_completion_event.set()

        if message.get("status") == "error":
            self.logger.error(message.get("result"))
            self.final_result = message.get("result")
            self.task_completion_event.set()

        if message.get("status") == "new_message":
            self.logger.info(message.get("result"))

    def _setup_agents(self):
        instruction_system_prompt.provider("tools").update(self.tools_json)
        instruction_system_prompt.provider("workspace_path").update(str(self.work_dir))
        instruction_agent_config = {
            "api_key": os.getenv("API_KEY"), "api_url": os.getenv("BASE_URL"),
            "engine": os.getenv("MODEL"),
            "system_prompt": copy.deepcopy(instruction_system_prompt),
            "print_log": os.getenv("DEBUG", "false").lower() in ("true", "1", "t", "yes"),
            "temperature": 0.7, "use_plugins": False, "logger": self.logger
        }

        worker_system_prompt.provider("tools").update(self.tools_json)
        worker_system_prompt.provider("workspace_path").update(str(self.work_dir))
        worker_agent_config = {
            "api_key": os.getenv("API_KEY"), "api_url": os.getenv("BASE_URL"),
            "engine": os.getenv("FAST_MODEL") or os.getenv("MODEL"),
            "system_prompt": copy.deepcopy(worker_system_prompt),
            "print_log": True, "temperature": 0.5, "function_call_max_loop": 100, "logger": self.logger,
            "check_done": os.getenv("CHECK_DONE", "true").lower() in ("true", "1", "t", "yes")
        }

        instruction_agent = InstructionAgent(
            goal=self.goal, tools_json=self.tools_json, agent_config=instruction_agent_config, work_dir=self.work_dir, cache_messages=self.cache_messages,
            broker=self.broker, listen_topic=self.WORKER_RESPONSE_TOPIC,
            publish_topic=self.INSTRUCTION_TOPIC, status_topic=self.TASK_STATUS_TOPIC,
        )

        worker_agent = WorkerAgent(
            goal=self.goal, tools_json=self.tools_json, agent_config=worker_agent_config, work_dir=self.work_dir, cache_messages=self.cache_messages,
            broker=self.broker, listen_topic=self.INSTRUCTION_TOPIC,
            publish_topic=self.WORKER_RESPONSE_TOPIC, status_topic=self.TASK_STATUS_TOPIC,
        )
        return instruction_agent, worker_agent

    async def run(self):
        """Sets up subscriptions and starts the workflow."""
        await self.setup()
        os.chdir(self.work_dir.absolute())
        await self._configure_tools()

        instruction_agent, worker_agent = self._setup_agents()

        self.broker.publish({"instruction": "Initial kickoff"}, self.INSTRUCTION_TOPIC)

        self._status_subscription = self.broker.subscribe(self._task_status_subscriber, self.TASK_STATUS_TOPIC)
        await self.task_completion_event.wait()

        instruction_agent.dispose()
        worker_agent.dispose()
        self._status_subscription.dispose()
        await self.mcp_manager.cleanup()
        return self.final_result

    async def stream_run(self):
        """Runs the workflow and yields status messages."""
        await self.setup()
        os.chdir(self.work_dir.absolute())
        await self._configure_tools()

        instruction_agent, worker_agent = self._setup_agents()

        self.broker.publish({"instruction": "Initial kickoff"}, self.INSTRUCTION_TOPIC)

        try:
            async for message in self.broker.iter_topic(self.TASK_STATUS_TOPIC):
                if message.get("status") == "new_message":
                    yield message.get("result")
                elif message.get("status") == "finished":
                    yield message.get("result")
                    break
                elif message.get("status") == "error":
                    self.logger.error(message.get("result"))
                    self.final_result = message.get("result")
                    self.task_completion_event.set()
        finally:
            instruction_agent.dispose()
            worker_agent.dispose()
            await self.mcp_manager.cleanup()