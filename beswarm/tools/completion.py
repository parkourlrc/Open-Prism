from ..aient.aient.plugins import register_tool

@register_tool()
def task_complete(message: str) -> str:
    """
    当任务完成时，调用此工具以返回最终结果。

    这个工具接收一个表示任务完成信息的字符串，并将其直接返回。
    它标志着一个任务的成功结束，并将最终的输出传递给用户或调用者。

    Args:
        message (str): 任务完成的信息或最终结果。必填字段。

    Returns:
        str: 传入的任务完成信息。
    """
    return message
