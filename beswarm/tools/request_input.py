from ..aient.aient.plugins import register_tool

@register_tool()
def request_admin_input(prompt: str) -> str:
    """
    当缺少必要信息（如 API Key、配置等）时，调用此工具向管理员发起请求以获取输入。

    这个工具会向管理员显示一个提示问题 (`prompt`)，并同步等待管理员的文本输入。
    它主要用于解决因信息不足而导致任务中断的情况，作为一个与外部操作人员交互的桥梁。

    Args:
        prompt (str): 需要向管理员显示的、用于请求信息的具体问题。

    Returns:
        str: 管理员输入的文本信息。
    """
    # 打印一个清晰的提示，告知管理员需要提供信息
    print(f"\n[❗️] 智能体需要管理员的帮助来继续执行任务: {prompt}")
    # 使用 input() 函数来捕获管理员的输入
    admin_input = input("请管理员输入 > ")
    return admin_input.strip()