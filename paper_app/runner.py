from __future__ import annotations

import json
import asyncio
import os
import re
import shutil
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

from beswarm.tools.worker import worker
from beswarm.tools.repomap import get_code_repo_map
from beswarm.tools.search_arxiv import search_arxiv
from beswarm.tools.read_file import read_file
from beswarm.tools.write_file import write_to_file
from beswarm.tools.edit_file import edit_file
from beswarm.tools.search_web import search_web
from beswarm.tools.subtasks import create_task, get_task_result

from beswarm.aient.aient.plugins.registry import register_tool
from beswarm.aient.aient.plugins.read_image import read_image
from beswarm.aient.aient.plugins.list_directory import list_directory
from beswarm.aient.aient.plugins.excute_command import excute_command
from beswarm.aient.aient.plugins.websearch import get_url_content
from beswarm.aient.aient.plugins.arXiv import download_read_arxiv_pdf

from custom_tools.markdown_to_docx import convert_markdown_to_docx
from custom_tools.xml_to_png import convert_xml_to_png


@dataclass(frozen=True)
class PaperRunResult:
    output_dir: Path
    internal_work_dir: Path


def _prepend_to_path(dir_path: Path) -> None:
    if not dir_path.exists():
        return
    value = str(dir_path.resolve())
    current = os.environ.get("PATH", "")
    parts = [p for p in current.split(os.pathsep) if p]
    if value in parts:
        return
    os.environ["PATH"] = value + (os.pathsep + current if current else "")


def _safe_copytree(src: Path, dst: Path, ignore_names: Iterable[str]) -> None:
    ignore = shutil.ignore_patterns(*list(ignore_names))
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=ignore)


def _redact_secrets(text: str, *, api_key: str, thordata_key: str) -> str:
    redacted = text
    for secret in (api_key, thordata_key):
        if secret:
            redacted = redacted.replace(secret, "******")
    redacted = re.sub(r"\bsk-[A-Za-z0-9]{10,}\b", "sk-******", redacted)
    redacted = re.sub(r"\bBearer\s+sk-[A-Za-z0-9]{10,}\b", "Bearer sk-******", redacted, flags=re.IGNORECASE)
    return redacted


def build_goal(prompt_rel_path: str, topic: str, api_key: str, base_url: str, model: str) -> str:
    topic = (topic or "").strip()
    return (
        f"请根据\"{prompt_rel_path}\"中的内容,针对\"{topic}\"的任务生成一篇顶级论文。\n"
        "!注意!: 所有涉及到使用大语言模型的部分请使用 openai compatible 格式的大模型调用方式来完成。\n"
        "本程序已在运行时设置好如下环境变量，请直接读取使用，不要在对话/文件中输出这些变量的具体值：\n"
        "os.environ['API_KEY']\n"
        "os.environ['BASE_URL']\n"
        "os.environ['MODEL']\n"
        "\n"
        "为了便于用户在输出目录实时查看进度，请至少按以下阶段持续写入文件：\n"
        "1) research_plan.md（研究计划/大纲）\n"
        "2) related_work.md（相关工作与引用列表）\n"
        "3) paper_draft.md（论文草稿，逐步完善）\n"
        "4) paper_final.md 与 paper_final.docx（最终论文）\n"
    )


def run_paper_job(
    *,
    resource_root: Path,
    internal_work_dir: Path,
    output_dir: Path,
    prompt_rel_path: str,
    topic: str,
    api_key: str,
    base_url: str,
    model: str,
    thordata_key: str,
    search_mode: bool,
    request_input: Callable[[str], str],
    on_log: Callable[[str], None] | None = None,
) -> PaperRunResult:
    # Ensure predictable encoding for any console prints during dev runs.
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

    # Expose bundled resource root to tools/filters.
    os.environ["OCEANS_RESOURCE_ROOT"] = str(resource_root)

    # Set user LLM config for beswarm.
    os.environ["API_KEY"] = api_key
    os.environ["BASE_URL"] = base_url
    os.environ["MODEL"] = model
    os.environ["THORDATA_KEY"] = thordata_key
    os.environ["OCEANS_SEARCH_MODE"] = "1" if search_mode else ""

    # Tool chain expects these for docx styling and mermaid-cli resolution.
    default_reference = resource_root / "default_reference.docx"
    if default_reference.exists():
        os.environ["DEFAULT_REFERENCE_DOC"] = str(default_reference)

    # Add bundled toolchains into PATH for any subprocesses that rely on PATH lookups.
    pandoc_exe = (
        resource_root
        / "custom_tools"
        / "markdown_to_docx"
        / "md2doc_tools"
        / "pandoc"
        / "pandoc-3.6.4-windows-x86_64"
        / "pandoc-3.6.4"
        / "pandoc.exe"
    )
    if pandoc_exe.exists():
        _prepend_to_path(pandoc_exe.parent)

    graphviz_bin = (
        resource_root
        / "custom_tools"
        / "xml_to_png"
        / "xml2png_tools"
        / "graphviz"
        / "windows_10_cmake_Release_Graphviz-12.2.1-win64"
        / "Graphviz-12.2.1-win64"
        / "bin"
    )
    _prepend_to_path(graphviz_bin)

    mmdc_cli = (
        resource_root
        / "custom_tools"
        / "mermaid_to_png"
        / "mermaid2png_tools"
        / "mmdc"
        / "node_modules"
        / "@mermaid-js"
        / "mermaid-cli"
        / "src"
        / "cli.js"
    )
    if mmdc_cli.exists():
        os.environ["MMDC_CLI_SCRIPT"] = str(mmdc_cli)

    bundled_node = resource_root / "runtime" / "node" / "node.exe"
    if bundled_node.exists():
        os.environ["OCEANS_NODE_PATH"] = str(bundled_node)
        node_dir = str(bundled_node.parent)
        os.environ["PATH"] = node_dir + os.pathsep + os.environ.get("PATH", "")

    # Mermaid CLI uses Puppeteer; on many machines Chromium is not bundled with node_modules.
    # Prefer system browsers to avoid downloads during first run.
    if not os.environ.get("PUPPETEER_EXECUTABLE_PATH"):
        candidates = [
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
            / "Microsoft"
            / "Edge"
            / "Application"
            / "msedge.exe",
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
            / "Microsoft"
            / "Edge"
            / "Application"
            / "msedge.exe",
            Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
            / "Google"
            / "Chrome"
            / "Application"
            / "chrome.exe",
            Path(os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)"))
            / "Google"
            / "Chrome"
            / "Application"
            / "chrome.exe",
        ]
        for exe in candidates:
            if exe.exists():
                os.environ["PUPPETEER_EXECUTABLE_PATH"] = str(exe)
                break

    internal_work_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    logs_dir = output_dir / "_logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    run_log_path = logs_dir / "run.log"
    conversation_export_path = logs_dir / "conversation.json"
    agent_log_export_path = logs_dir / "agent.log"
    heartbeat_path = logs_dir / "heartbeat.txt"

    def emit_log(message: str) -> None:
        text = (message or "").rstrip()
        if not text:
            return
        safe = _redact_secrets(text, api_key=api_key, thordata_key=thordata_key)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {safe}\n"
        try:
            with run_log_path.open("a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass
        if on_log:
            try:
                on_log(safe)
            except Exception:
                pass

    readme_path = output_dir / "README.txt"
    if not readme_path.exists():
        readme_path.write_text(
            "OceanS Paper Generator 输出说明\n"
            f"- 本次任务输出目录：{output_dir}\n"
            "- 运行过程中会持续同步可见产物到该目录。\n"
            "- 运行日志：_logs/run.log\n"
            "- 最终论文通常为：paper_final.docx\n",
            encoding="utf-8",
        )

    # Copy required prompts into work_dir so beswarm's relative file tools work.
    prompts_src = resource_root / "prompts"
    prompts_dst = internal_work_dir / "prompts"
    if prompts_src.exists():
        _safe_copytree(prompts_src, prompts_dst, ignore_names=(".git",))

    goal = build_goal(prompt_rel_path, topic, api_key, base_url, model)
    emit_log(f"[开始] 任务已创建，输出目录：{output_dir}")

    @register_tool(name="request_admin_input")
    def request_admin_input(prompt: str) -> str:
        return request_input(prompt)

    tools = [
        read_file,
        read_image,
        list_directory,
        write_to_file,
        excute_command,
        search_arxiv,
        download_read_arxiv_pdf,
        get_code_repo_map,
        edit_file,
        search_web,
        get_url_content,
        create_task,
        get_task_result,
        request_admin_input,
        convert_markdown_to_docx,
        convert_xml_to_png,
    ]

    worker_error: BaseException | None = None
    stop_event = threading.Event()

    def sync_loop() -> None:
        last_agent_pos = 0
        last_conv_mtime = 0.0
        ignore_roots = {".beswarm", "__pycache__", "prompts"}

        while not stop_event.is_set():
            try:
                heartbeat_path.write_text(time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
            except Exception:
                pass

            agent_log_candidates = [
                internal_work_dir / ".beswarm" / "cache" / "agent.log",
                internal_work_dir / ".beswarm" / "agent.log",
            ]
            agent_log_src = next((p for p in agent_log_candidates if p.exists()), None)
            if agent_log_src:
                try:
                    try:
                        size = agent_log_src.stat().st_size
                        if size < last_agent_pos:
                            last_agent_pos = 0
                    except Exception:
                        pass
                    with agent_log_src.open("rb") as f:
                        try:
                            f.seek(last_agent_pos)
                        except Exception:
                            last_agent_pos = 0
                            f.seek(0)
                        chunk_bytes = f.read()
                        last_agent_pos = f.tell()
                    if chunk_bytes:
                        chunk = chunk_bytes.decode("utf-8", errors="ignore")
                        safe_chunk = _redact_secrets(chunk, api_key=api_key, thordata_key=thordata_key)
                        try:
                            with agent_log_export_path.open("a", encoding="utf-8") as f:
                                f.write(safe_chunk)
                        except Exception:
                            pass
                        for raw_line in safe_chunk.splitlines():
                            emit_log(raw_line)
                except Exception:
                    pass

            conv_candidates = [
                internal_work_dir / ".beswarm" / "cache" / "work_agent_conversation_history.json",
                internal_work_dir / ".beswarm" / "work_agent_conversation_history.json",
            ]
            conv_src = next((p for p in conv_candidates if p.exists()), None)
            if conv_src:
                try:
                    mtime = conv_src.stat().st_mtime
                    if mtime > last_conv_mtime:
                        last_conv_mtime = mtime
                        raw = conv_src.read_text(encoding="utf-8", errors="ignore")
                        safe = _redact_secrets(raw, api_key=api_key, thordata_key=thordata_key)
                        try:
                            obj = json.loads(safe)
                            conversation_export_path.write_text(
                                json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8"
                            )
                        except Exception:
                            conversation_export_path.write_text(safe, encoding="utf-8")
                except Exception:
                    pass

            try:
                if internal_work_dir.exists():
                    for p in internal_work_dir.rglob("*"):
                        try:
                            rel = p.relative_to(internal_work_dir)
                        except Exception:
                            continue
                        if not rel.parts:
                            continue
                        if rel.parts[0] in ignore_roots:
                            continue
                        dst = output_dir / rel
                        if p.is_dir():
                            dst.mkdir(parents=True, exist_ok=True)
                        else:
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            if dst.exists():
                                try:
                                    src_stat = p.stat()
                                    dst_stat = dst.stat()
                                    if src_stat.st_size == dst_stat.st_size and src_stat.st_mtime <= dst_stat.st_mtime:
                                        continue
                                except Exception:
                                    pass
                            shutil.copy2(p, dst)
            except Exception:
                pass

            stop_event.wait(1.0)

    sync_thread = threading.Thread(target=sync_loop, daemon=True)
    sync_thread.start()
    try:
        asyncio.run(worker(goal, tools, str(internal_work_dir), cache_messages=True))
    except BaseException as e:
        worker_error = e
    finally:
        stop_event.set()
        sync_thread.join(timeout=3.0)

    # Export results to fixed output folder, excluding any internal .beswarm folders.
    exported = output_dir

    if internal_work_dir.exists():
        _safe_copytree(internal_work_dir, exported, ignore_names=(".beswarm", "__pycache__", "prompts"))

    # Cleanup internal work directory so users only see the exported output folder.
    shutil.rmtree(internal_work_dir, ignore_errors=True)

    if worker_error is not None:
        raise RuntimeError(f"{worker_error} (已导出当前结果到: {exported})") from worker_error

    return PaperRunResult(output_dir=exported, internal_work_dir=internal_work_dir)
