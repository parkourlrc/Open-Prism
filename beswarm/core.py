import contextvars
from .broker import MessageBroker
from .bemcp.bemcp import MCPManager
from .taskmanager import TaskManager
from .knowledge_graph import KnowledgeGraphManager

"""
全局共享实例
"""

broker = MessageBroker()
mcp_manager = MCPManager()
kgm = KnowledgeGraphManager(broker=broker)
current_task_manager = contextvars.ContextVar('current_task_manager')
current_work_dir = contextvars.ContextVar('current_work_dir', default=None)

# 动态系统提示扩展：允许用户注册可实时刷新的提示片段（字符串或可调用）
_system_prompt_providers = contextvars.ContextVar('system_prompt_providers', default=[])

def register_system_prompt_provider(provider):
    """
    注册一个系统提示扩展。
    - provider 可以是:
      * str: 固定文本
      * callable: 无参函数，返回字符串（每次渲染都会调用，达到实时刷新）
    """
    providers = list(_system_prompt_providers.get())
    providers.append(provider)
    _system_prompt_providers.set(providers)

def clear_system_prompt_providers():
    """清空已注册的系统提示扩展（仅影响当前任务上下文）。"""
    _system_prompt_providers.set([])

def render_system_prompt_extensions():
    """
    把所有扩展拼接成单一字符串。
    - 对于可调用项，会在每次渲染时调用。
    """
    parts = []
    for p in _system_prompt_providers.get():
        try:
            val = p() if callable(p) else p
            parts.append("" if val is None else f"<{p.__name__}>" + str(val) + f"</{p.__name__}>")
        except Exception as e:
            parts.append(f"[system_prompt_provider_error: {e}]")
    # 用两个换行分隔，避免影响主提示结构
    return "\n\n".join([s for s in parts if s])

def get_task_manager():
    """Creates a new, isolated TaskManager instance."""
    return TaskManager()
