from __future__ import annotations

import os
import sys


def _truthy(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _minimal_mode() -> bool:
    if _truthy(os.environ.get("OCEANS_MINIMAL_PLUGINS")):
        return True
    if getattr(sys, "frozen", False):
        return True
    return False


if _minimal_mode():
    # Minimal export for custom_tools' @register_tool() decorators.
    from ..aient.aient.plugins import register_tool  # noqa: E402

    __all__ = ["register_tool"]
else:
    # Upstream-compatible exports for dev scripts (main.py/main_paper.py).
    from .edit_file import edit_file  # noqa: E402
    from .search_web import search_web  # noqa: E402
    from .completion import task_complete  # noqa: E402
    from .search_arxiv import search_arxiv  # noqa: E402
    from .repomap import get_code_repo_map  # noqa: E402
    from .write_csv import append_row_to_csv  # noqa: E402
    from .graph import (  # noqa: E402
        get_node_details,
        add_knowledge_node,
        delete_knowledge_node,
        rename_knowledge_node,
        move_knowledge_node,
        get_knowledge_graph_tree,
        add_tags_to_knowledge_node,
        remove_tags_from_knowledge_node,
    )
    from .request_input import request_admin_input  # noqa: E402
    from .screenshot import save_screenshot_to_file  # noqa: E402
    from .worker import worker, worker_gen, chatgroup  # noqa: E402
    from .click import find_and_click_element, scroll_screen  # noqa: E402
    from .subtasks import (  # noqa: E402
        create_task,
        resume_task,
        get_all_tasks_status,
        get_task_result,
        create_tasks_from_csv,
    )
    from .deep_search import deepsearch  # noqa: E402
    from .write_file import write_to_file  # noqa: E402
    from .read_file import read_file  # noqa: E402

    from ..aient.aient.plugins import (  # noqa: E402
        get_time,
        read_image,
        register_tool,
        excute_command,
        generate_image,
        list_directory,
        get_url_content,
        run_python_script,
        set_readonly_path,
        get_search_results,
        download_read_arxiv_pdf,
    )

    __all__ = [
        "worker",
        "get_time",
        "edit_file",
        "read_file",
        "chatgroup",
        "worker_gen",
        "read_image",
        "search_web",
        "deepsearch",
        "create_task",
        "resume_task",
        "search_arxiv",
        "write_to_file",
        "scroll_screen",
        "register_tool",
        "task_complete",
        "excute_command",
        "generate_image",
        "list_directory",
        "get_task_result",
        "get_url_content",
        "get_node_details",
        "add_knowledge_node",
        "move_knowledge_node",
        "delete_knowledge_node",
        "rename_knowledge_node",
        "get_knowledge_graph_tree",
        "add_tags_to_knowledge_node",
        "remove_tags_from_knowledge_node",
        "append_row_to_csv",
        "set_readonly_path",
        "get_code_repo_map",
        "run_python_script",
        "get_search_results",
        "request_admin_input",
        "get_all_tasks_status",
        "create_tasks_from_csv",
        "find_and_click_element",
        "download_read_arxiv_pdf",
        "save_screenshot_to_file",
    ]

