import os
from ..aient.aient.plugins import register_tool, get_function_call_list

from ..aient.aient.models import chatgpt
from ..aient.aient.prompt import planner_system_prompt

@register_tool()
async def planner(goal, tools, work_dir):
    tools_json = [value for _, value in get_function_call_list(tools).items()]
    instruction_agent_config = {
        "api_key": os.getenv("API_KEY"),
        "api_url": os.getenv("BASE_URL"),
        "engine": os.getenv("MODEL"),
        "system_prompt": planner_system_prompt.format(worker_tool_use_rules=tools_json, workspace_path=work_dir),
        "print_log": False,
        "max_tokens": 4000,
        "temperature": 0.7,
        "use_plugins": True,
    }

    # 指令agent初始化
    instruction_agent = chatgpt(**instruction_agent_config)

    instruction_prompt = f"""
任务目标: {goal}

请生成一个详细的任务计划，包括每个步骤的详细描述、所需的工具和预期结果。然后调用worker工具来完成每个步骤。
    """
    # 让指令agent分析对话历史并生成新指令
    next_instruction = await instruction_agent.ask_async(instruction_prompt)
    print("\n🤖 指令智能体生成的下一步指令:", next_instruction)

    return "任务已完成"