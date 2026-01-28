from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from beswarm.tools import register_tool


def _get_resource_root() -> Path:
    env_root = os.environ.get("OCEANS_RESOURCE_ROOT")
    if env_root:
        return Path(env_root).resolve()
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


@register_tool()
def convert_xml_to_png(xml_file_path: str, output_png_path: str, engine: str = "dot") -> str:
    """
    将指定的 XML（包含 DOT 内容）转换为 PNG 图像，使用项目内嵌的 Graphviz。

    :param xml_file_path: 输入 XML/DOT 文件路径
    :param output_png_path: 输出 PNG 文件路径
    :param engine: Graphviz 布局引擎（如 dot/neato/fdp），Windows 下会自动补全 .exe
    :return: 成功/错误信息
    """

    input_path = Path(xml_file_path)
    if not input_path.exists():
        return f"错误: 输入 XML/DOT 文件未找到 - {xml_file_path}"

    engine_name = engine
    if os.name == "nt" and not engine_name.lower().endswith(".exe"):
        engine_name = f"{engine_name}.exe"

    resource_root = _get_resource_root()
    dot_exec_path = (
        resource_root
        / "custom_tools"
        / "xml_to_png"
        / "xml2png_tools"
        / "graphviz"
        / "windows_10_cmake_Release_Graphviz-12.2.1-win64"
        / "Graphviz-12.2.1-win64"
        / "bin"
        / engine_name
    )

    if not dot_exec_path.exists():
        fallback = dot_exec_path.with_suffix("")  # try without .exe if caller provided it that way
        if fallback.exists():
            dot_exec_path = fallback
        else:
            return (
                f"错误: Graphviz 引擎 '{engine}' 未在预期路径找到: {dot_exec_path}. "
                f"请确保依赖已正确放置在 custom_tools/xml_to_png/xml2png_tools/graphviz 下。"
            )

    output_path = Path(output_png_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        str(dot_exec_path),
        "-Tpng",
        "-o",
        str(output_path),
        str(input_path),
    ]

    try:
        process = subprocess.run(command, capture_output=True, text=True, check=False, encoding="utf-8")
        if process.returncode == 0 and output_path.exists():
            return f"成功: {xml_file_path} -> {output_png_path} (引擎 {engine})"

        if output_path.exists():
            return (
                f"成功 (Graphviz 返回码 {process.returncode} 但文件已生成): "
                f"{xml_file_path} -> {output_png_path}. stderr: {process.stderr.strip()}"
            )

        return (
            f"错误: Graphviz 执行失败 (返回码 {process.returncode}) - "
            f"stderr: {process.stderr.strip()} stdout: {process.stdout.strip()}"
        )
    except FileNotFoundError:
        return f"错误: Graphviz 可执行文件未找到 - {dot_exec_path}"
    except Exception as e:
        return f"错误: XML 转 PNG 发生意外错误 - {e}"

