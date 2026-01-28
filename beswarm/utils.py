import re
import sys
import logging
from pathlib import Path
import queue
import atexit
from logging.handlers import QueueHandler, QueueListener

def extract_xml_content(text, xml_tag):
    result = ''
    pattern = rf'^<{xml_tag}>([\D\d\s]+?)<\/{xml_tag}>$'
    match = re.search(pattern, text, re.MULTILINE)
    if match:
        result = match.group(1)
    if not result:
        return ''
    return result.strip()

def replace_xml_content(original_string: str, tag_name: str, replacement_content: str) -> str:
    """
    将指定XML标签内的内容替换为新内容。

    此函数使用正则表达式查找所有匹配的XML标签对（例如 `<tag>...</tag>`），
    并将其中的内容替换为 `replacement_content`。

    Args:
        original_string (str): 包含XML标记的原始字符串。
        tag_name (str): 要定位的XML标签的名称（不带尖括号）。
        replacement_content (str): 用于替换标签内部内容的新字符串。

    Returns:
        str: 返回内容已被替换的新字符串。如果未找到匹配的标签，则返回原始字符串。
    """
    pattern = f"<{tag_name}>.*?<\\/{tag_name}>"
    replacement = f"<{tag_name}>{replacement_content}</{tag_name}>"

    new_string = re.sub(pattern, replacement, original_string, flags=re.DOTALL)

    return new_string

import io
import base64
from .aient.aient.core.utils import get_image_message, get_text_message

async def get_current_screen_image_message(prompt):
    print("instruction agent 正在截取当前屏幕...")
    try:
        import pyautogui
        # 使用 pyautogui 截取屏幕，返回 PIL Image 对象
        screenshot = pyautogui.screenshot()
        # img_width, img_height = screenshot.size # 获取截图尺寸
        img_width, img_height = pyautogui.size()
        print(f"截图成功，尺寸: {img_width}x{img_height}")

        # 将 PIL Image 对象转换为 Base64 编码的 PNG 字符串
        buffered = io.BytesIO()
        screenshot.save(buffered, format="PNG")
        base64_encoded_image = base64.b64encode(buffered.getvalue()).decode("utf-8")
        IMAGE_MIME_TYPE = "image/png" # 截图格式为 PNG

    except ImportError:
        # Pillow 也是 pyautogui 的依赖，但以防万一单独处理
        print("\n❌ 请安装所需库: pip install Pillow pyautogui")
        return False
    except Exception as e:
        print(f"\n❌ 截取屏幕或处理图像时出错: {e}")
        return False

    engine_type = "gpt"
    message_list = []
    text_message = await get_text_message(prompt, engine_type)
    image_message = await get_image_message(f"data:{IMAGE_MIME_TYPE};base64," + base64_encoded_image, engine_type)
    message_list.append(text_message)
    message_list.append(image_message)
    return message_list

import asyncio
from .bemcp.bemcp import MCPClient, convert_tool_format

async def register_mcp_tools(mcp_client: MCPClient, registry: "Registry"):
    """
    Fetches tools from an MCP client, dynamically creates corresponding
    Python functions with correct signatures, and registers them using the
    provided registry instance.
    """
    try:
        mcp_tools = await mcp_client.list_tools()
        print(f"Found {len(mcp_tools)} tools on the MCP server.")
    except Exception as e:
        print(f"Error fetching tools from MCP server: {e}")
        return

    # Create a dummy file for inspect.getsource to work with exec
    # This helps make the created functions inspectable
    source_storage = {}

    for tool in mcp_tools:
        openai_spec = convert_tool_format(tool)
        func_spec = openai_spec.get('function', {})

        tool_name = func_spec.get('name')
        if not tool_name or not tool_name.isidentifier():
            print(f"Skipping tool with invalid name: {tool_name}")
            continue

        description = func_spec.get('description', 'No description available.')
        params_spec = func_spec.get('parameters', {})
        properties = params_spec.get('properties', {})
        required = set(params_spec.get('required', []))

        param_defs = []
        for name, spec in properties.items():
            if name in required:
                param_defs.append(name)
            else:
                # Add default value for optional parameters
                default = spec.get('default', 'None')
                param_defs.append(f"{name}={default}")

        params_str = ", ".join(param_defs)
        arg_names = list(properties.keys())
        # Create a dictionary of arguments to pass to call_tool
        args_dict_str = "{" + ", ".join(f"'{k}': {k}" for k in arg_names) + "}"

        # Dynamically generate the Python source code for the function
        func_source = f"""
async def {tool_name}({params_str}):
    \"\"\"{description}\"\"\"
    tool_args = {args_dict_str}

    # This function is a dynamically generated wrapper for an MCP tool.
    print(f"-> Calling MCP tool '{tool_name}' with args: {{tool_args}}")
    result = await mcp_client.call_tool('{tool_name}', tool_args)

    # Extract text content if available, otherwise return the raw result
    if hasattr(result, 'content') and isinstance(result.content, list) and result.content:
        if hasattr(result.content[0], 'text'):
            return result.content[0].text
    return result
"""
        # Store the source code so inspect.getsource can find it
        source_storage[tool_name] = func_source

        # Use a dictionary for the execution scope
        exec_scope = {'mcp_client': mcp_client, 'asyncio': asyncio}

        try:
            # Execute the source code to create the function object
            exec(func_source, exec_scope)
            generated_func = exec_scope[tool_name]

            # Monkey-patch getsourcelines to work with our storage
            # This makes our generated function fully compatible with the registry
            import inspect
            import linecache
            linecache.cache[f"<mcp_adapter/{tool_name}>"] = (
                len(func_source),
                None,
                [line + '\n' for line in func_source.splitlines()],
                f"<mcp_adapter/{tool_name}>",
            )
            generated_func.__code__ = generated_func.__code__.replace(co_filename=f"<mcp_adapter/{tool_name}>")

            # Register the newly created function
            registry.register(type="tool", name=tool_name)(generated_func)
            print(f"Successfully registered MCP tool: '{tool_name}'")

        except Exception as e:
            import traceback
            print(f"Failed to create or register function for tool '{tool_name}': {e}")
            traceback.print_exc()

# For asynchronous logging
_listeners = []
_atexit_registered = False

def _stop_all_listeners():
    for listener in _listeners:
        listener.stop()

def setup_logger(logger_name: str, log_file: Path):
    """
    用异步方式设置一个 logger，使其同时输出到文件和终端，避免IO阻塞。

    Args:
        logger_name (str): Logger 的唯一名称。
        log_file (Path): 日志文件的完整路径。

    Returns:
        logging.Logger: 配置好的 logger 实例。
    """
    global _atexit_registered

    # 1. 获取 Logger 实例
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO) # 设置 logger 的最低处理级别为 INFO
    logger.propagate = False

    # 如果已经配置了异步 handler，直接返回
    if any(isinstance(h, QueueHandler) for h in logger.handlers):
        return logger

    # 如果有其他 handler，说明被其他方式配置过，也直接返回
    if logger.hasHandlers():
        return logger

    # 2. 创建用于 Listener 的 Handler（文件和终端）
    # 确保日志文件所在的目录存在
    log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    stream_handler = logging.StreamHandler(sys.stdout)

    # 3. 创建一个通用的 Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')

    # 4. 为两个 Handler 设置 Formatter
    file_handler.setFormatter(formatter)
    stream_handler.setFormatter(formatter)

    # 5. 设置 Queue、QueueHandler 和 QueueListener
    log_queue = queue.Queue(-1)
    # listener 在后台线程中从 queue 读取日志，并分发给 file_handler 和 stream_handler
    listener = QueueListener(log_queue, file_handler, stream_handler, respect_handler_level=True)

    # queue_handler 是一个非阻塞的 handler，它把日志消息放到 queue 中
    queue_handler = QueueHandler(log_queue)

    # 6. 将 QueueHandler 添加到 Logger
    logger.addHandler(queue_handler)

    # 7. 启动 listener 并注册 atexit 钩子以确保程序退出时停止
    _listeners.append(listener)
    listener.start()

    if not _atexit_registered:
        atexit.register(_stop_all_listeners)
        _atexit_registered = True

    return logger

if __name__ == "__main__":
    print(extract_xml_content("<instructions>\n123</instructions>", "instructions"))

# python -m beswarm.utils