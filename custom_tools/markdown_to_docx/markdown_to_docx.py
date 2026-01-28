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
    # repo root (custom_tools/markdown_to_docx/markdown_to_docx.py -> <root>/custom_tools/... -> <root>)
    return Path(__file__).resolve().parents[2]


@register_tool()
def convert_markdown_to_docx(
    markdown_file_path: str,
    output_docx_path: str,
    use_mermaid_filter: bool = True,
) -> tuple[str, str]:
    """
    将指定的 Markdown 文件转换为 DOCX 文件，使用项目内嵌的 Pandoc。
    允许通过参数控制是否使用 Mermaid 过滤器。

    :param markdown_file_path: 输入 Markdown 文件路径
    :param output_docx_path: 输出 DOCX 文件路径
    :param use_mermaid_filter: 是否使用 Mermaid 过滤器（默认 True）
    :return: (status_message, pandoc_stderr)
    """

    pandoc_stderr_output = ""

    input_path = Path(markdown_file_path)
    if not input_path.exists():
        return f"错误: 输入 Markdown 文件未找到 - {markdown_file_path}", pandoc_stderr_output

    resource_root = _get_resource_root()
    md2doc_tools_dir = resource_root / "custom_tools" / "markdown_to_docx" / "md2doc_tools"
    pandoc_exec_path = (
        md2doc_tools_dir
        / "pandoc"
        / "pandoc-3.6.4-windows-x86_64"
        / "pandoc-3.6.4"
        / "pandoc.exe"
    )

    if not pandoc_exec_path.exists():
        return (
            f"错误: Pandoc 可执行文件未在预期路径找到 - {pandoc_exec_path}. "
            f"请确保依赖已正确放置在 custom_tools/markdown_to_docx/md2doc_tools/ 目录下。",
            pandoc_stderr_output,
        )

    output_path = Path(output_docx_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    markdown_dir = input_path.resolve().parent

    command: list[str] = [
        str(pandoc_exec_path),
        str(input_path),
        "-o",
        str(output_path),
        "--standalone",
        "--resource-path",
        str(markdown_dir),
    ]

    reference_doc_env = os.getenv("DEFAULT_REFERENCE_DOC", "").strip()
    reference_doc_path: Path | None = None
    if reference_doc_env:
        p = Path(reference_doc_env)
        reference_doc_path = p if p.is_absolute() else (resource_root / p).resolve()
    else:
        p = resource_root / "default_reference.docx"
        if p.exists():
            reference_doc_path = p

    if reference_doc_path and reference_doc_path.exists():
        command.extend(["--reference-doc", str(reference_doc_path)])

    if use_mermaid_filter:
        filter_dir = md2doc_tools_dir / "filters"
        mermaid_filter_exe = filter_dir / "pandoc_mermaid_filter.exe"
        mermaid_filter_py = filter_dir / "pandoc_mermaid_filter.py"
        mermaid_filter_path = mermaid_filter_exe if mermaid_filter_exe.exists() else mermaid_filter_py

        if not mermaid_filter_path.exists():
            return (
                f"错误: Mermaid 过滤器文件未在预期路径找到 - {mermaid_filter_path}. 请确保依赖已正确放置。",
                pandoc_stderr_output,
            )

        if mermaid_filter_path.suffix.lower() == ".lua":
            command.extend(["--lua-filter", str(mermaid_filter_path)])
        else:
            # .py or .exe both go through --filter
            command.extend(["--filter", str(mermaid_filter_path)])

    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            encoding="utf-8",
            cwd=str(markdown_dir),
        )

        if process.stderr:
            pandoc_stderr_output = process.stderr.strip()

        if process.returncode == 0:
            if output_path.exists():
                return f"成功: {markdown_file_path} -> {output_docx_path}", pandoc_stderr_output
            return (
                f"错误: Pandoc 执行成功但输出文件 '{output_docx_path}' 未创建。标准输出: {process.stdout.strip()}",
                pandoc_stderr_output,
            )

        return (
            f"错误: Pandoc 执行失败 (返回码{process.returncode}) - 标准输出: {process.stdout.strip()}",
            pandoc_stderr_output,
        )

    except FileNotFoundError:
        return f"错误: Pandoc 可执行文件 '{pandoc_exec_path}' 执行时发生 FileNotFoundError。", pandoc_stderr_output
    except Exception as e:
        return f"错误: Markdown 转 DOCX 发生意外错误 - {e}", pandoc_stderr_output

