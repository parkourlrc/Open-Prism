# patent_generation_project/custom_tools/mermaid_to_png.py
import os
import subprocess
import tempfile
import shutil # Needed for shutil.which
import sys
from pathlib import Path
from dotenv import load_dotenv
# 确保从正确的位置导入 register_tool
from beswarm.tools import register_tool

# --- Determine Project Root and Load .env ---
MMDC_CLI_SCRIPT_ABS = None
NODE_EXEC_PATH = None
PROJECT_ROOT = None

def _get_resource_root() -> Path:
    env_root = os.environ.get("OCEANS_RESOURCE_ROOT")
    if env_root:
        return Path(env_root).resolve()
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = _get_resource_root()
DOTENV_PATH = PROJECT_ROOT / ".env"
if DOTENV_PATH.is_file():
    load_dotenv(dotenv_path=DOTENV_PATH)
else:
    load_dotenv()

# --- Configuration from .env and System ---
MMDC_CLI_SCRIPT_REL = os.getenv('MMDC_CLI_SCRIPT')
NODE_EXEC_PATH = shutil.which('node') # Find node in system PATH

if not NODE_EXEC_PATH:
    node_from_env = os.environ.get("OCEANS_NODE_PATH", "").strip()
    if node_from_env and Path(node_from_env).exists():
        NODE_EXEC_PATH = node_from_env
    else:
        bundled_node = PROJECT_ROOT / "runtime" / "node" / "node.exe"
        if bundled_node.exists():
            NODE_EXEC_PATH = str(bundled_node)

if MMDC_CLI_SCRIPT_REL:
    p = Path(MMDC_CLI_SCRIPT_REL)
    MMDC_CLI_SCRIPT_ABS = p if p.is_absolute() else (PROJECT_ROOT / p).resolve()


def check_dependencies_for_mermaid_to_png():
    """Checks if Node.js and the configured MMDC script are available."""
    if not NODE_EXEC_PATH:
        # This message should ideally be logged or returned in a structured way
        print("Error: 'node' command not found in system PATH. Please install Node.js globally.")
        return False
    if not MMDC_CLI_SCRIPT_ABS or not MMDC_CLI_SCRIPT_ABS.is_file():
        print(f"Error: MMDC_CLI_SCRIPT path not found or invalid. Checked: {MMDC_CLI_SCRIPT_ABS}")
        print(f"  MMDC_CLI_SCRIPT from .env (relative to project root): {MMDC_CLI_SCRIPT_REL}")
        print("  Ensure MMDC_CLI_SCRIPT in .env points to the correct mermaid-cli script.")
        return False
    return True

@register_tool()
def convert_mermaid_to_png(mermaid_code_or_file_path: str,
                           output_png_path: str,
                           is_file: bool = False,
                           puppeteer_config_path: str = None) -> str:
    """
    将 Mermaid 代码或包含 Mermaid 代码的文件转换为 PNG 图像，
    使用通过 .env 配置的本地 mermaid-cli 脚本和系统 Node.js。
    允许指定可选的 Puppeteer 配置文件。

    :param mermaid_code_or_file_path: Mermaid 代码字符串或包含 Mermaid 代码的 .mmd/.mermaid 文件路径。
    :param output_png_path: 输出的 PNG 文件路径。
    :param is_file: 如果 True，则 mermaid_code_or_file_path 是文件路径；否则是 Mermaid 代码字符串。
    :param puppeteer_config_path: 可选的 Puppeteer JSON 配置文件路径。
                                   如果提供，其路径应由调用者构建。
                                   对于捆绑的配置, 建议相对于项目根目录构建路径,
                                   例如 'custom_tools/mermaid2png_tools/my_puppeteer_config.json'.
    :return: 成功信息或错误信息。
    """
    if not check_dependencies_for_mermaid_to_png():
        return "错误: Mermaid 转 PNG 的依赖项检查失败 (Node.js 或 MMDC 脚本未找到/配置错误)。详情请查看控制台日志。"

    input_path_to_use = None
    temp_file_created = False

    output_dir = os.path.dirname(output_png_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    try:
        if is_file:
            if not os.path.exists(mermaid_code_or_file_path):
                return f"错误: Mermaid 输入文件未找到 - {mermaid_code_or_file_path}"
            input_path_to_use = mermaid_code_or_file_path
        else:
            with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".mmd", encoding='utf-8') as tmp_file:
                tmp_file.write(mermaid_code_or_file_path)
                input_path_to_use = tmp_file.name
            temp_file_created = True

        command = [
            NODE_EXEC_PATH,
            str(MMDC_CLI_SCRIPT_ABS),
            "-i", input_path_to_use,
            "-o", output_png_path,
            "-e", "png", # Explicitly set png, though often default for .png output
            # "-w", "800", # Optional: set width, can be parameterized if needed
        ]

        if puppeteer_config_path:
            # Ensure puppeteer_config_path is absolute or correctly relative
            # If relative, it's often expected to be relative to CWD or project root.
            # For consistency, if a bundled config is used, ensure an absolute path
            # or a path relative to PROJECT_ROOT is resolved before passing.
            abs_puppeteer_config_path = puppeteer_config_path
            if PROJECT_ROOT and not os.path.isabs(puppeteer_config_path):
                 # Attempt to resolve relative to project root if not absolute
                 potential_path = PROJECT_ROOT / puppeteer_config_path
                 if potential_path.exists():
                     abs_puppeteer_config_path = str(potential_path)
                 # else, we assume it's relative to CWD or an already correct path

            if not os.path.exists(abs_puppeteer_config_path):
                # Log original path for clarity if resolution failed or was not attempted
                return f"错误: Puppeteer 配置文件未找到 - {puppeteer_config_path} (尝试解析为: {abs_puppeteer_config_path})"
            command.extend(["-p", abs_puppeteer_config_path])
        
        # Using subprocess.Popen for more control over streams if needed,
        # but subprocess.run is simpler for this case.
        process = subprocess.run(command, capture_output=True, text=True, check=False, encoding='utf-8')

        if process.returncode == 0 and os.path.exists(output_png_path):
            return f"成功: Mermaid {'文件 ' + input_path_to_use if is_file else '代码'} -> {output_png_path}"
        else:
            # Check if file was created despite non-zero exit code (e.g. mmdc warnings to stderr)
            if os.path.exists(output_png_path):
                 return f"成功 (mmdc 返回码 {process.returncode} 但文件已创建): Mermaid {'文件 ' + input_path_to_use if is_file else '代码'} -> {output_png_path}. 标准错误: {process.stderr.strip()}"
            
            error_message = f"MMDC 执行失败 (返回码 {process.returncode})."
            if process.stdout:
                error_message += f" 标准输出: {process.stdout.strip()}"
            if process.stderr:
                error_message += f" 标准错误: {process.stderr.strip()}"
            return f"错误: {error_message}"

    except FileNotFoundError: # This would be for NODE_EXEC_PATH if shutil.which failed and was None
        return f"错误: Node.js 执行文件 ('{NODE_EXEC_PATH}') 未找到。请确保 Node.js 已安装并添加到系统 PATH。"
    except Exception as e:
        return f"错误: Mermaid 转 PNG 发生意外错误 - {type(e).__name__}: {e}"
    finally:
        if temp_file_created and input_path_to_use and os.path.exists(input_path_to_use):
            os.remove(input_path_to_use)
