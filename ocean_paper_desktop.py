from __future__ import annotations

import queue
import threading
import traceback
import time
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import ttk

from paper_app.config import AppConfig, DEFAULT_BASE_URL
from paper_app.cleanup import cleanup_child_processes
from paper_app.paths import (
    get_app_config_path,
    get_internal_work_root,
    get_output_root,
    get_resource_root,
)
from paper_app.runner import run_paper_job


PROMPT_MAP = {
    "英文CS论文": "prompts/paper/英文CS论文_paper_generation_prompt.md",
    "中文CS论文": "prompts/paper/中文CS论文_paper_generation_prompt.md",
    "非CS论文": "prompts/paper/非CS论文_paper_generation_prompt.md",
}


class PaperApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("OceanS Paper Generator")
        self.geometry("980x680")
        self.minsize(900, 620)
        self.configure(bg="#F3F4F6")

        self._status_queue: "queue.Queue[tuple[str, str]]" = queue.Queue()
        self._input_queue: "queue.Queue[tuple[str, queue.Queue[str]]]" = queue.Queue()
        self._closing = False

        self.resource_root = get_resource_root()
        self.config_path = get_app_config_path()
        self.internal_work_root = get_internal_work_root()
        self.output_root = get_output_root()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.current_run_output_dir: Path | None = None

        self.config_data = AppConfig.load(self.config_path)

        self._build_styles()
        self._build_ui()
        self.after(150, self._poll_queues)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self) -> None:
        if self._closing:
            return
        self._closing = True
        try:
            self._append_log("[退出] 正在清理子进程…")
        except Exception:
            pass
        try:
            cleanup_child_processes()
        except Exception:
            pass
        self.destroy()

    def _build_styles(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TFrame", background="#F3F4F6")
        style.configure("Card.TFrame", background="#FFFFFF")
        style.configure("Title.TLabel", background="#F3F4F6", foreground="#111827", font=("Segoe UI", 18, "bold"))
        style.configure("Subtitle.TLabel", background="#FFFFFF", foreground="#111827", font=("Segoe UI", 12, "bold"))
        style.configure("Body.TLabel", background="#FFFFFF", foreground="#374151", font=("Segoe UI", 10))
        style.configure("Muted.TLabel", background="#FFFFFF", foreground="#6B7280", font=("Segoe UI", 9))
        style.configure("TLabel", background="#FFFFFF", foreground="#111827", font=("Segoe UI", 10))

        style.configure("TEntry", padding=6)
        style.configure("Accent.TButton", padding=8)
        style.map(
            "Accent.TButton",
            foreground=[("disabled", "#9CA3AF"), ("!disabled", "#FFFFFF")],
            background=[("disabled", "#E5E7EB"), ("!disabled", "#2563EB")],
        )

        # Make all ttk.Checkbutton show a "√" checkmark (instead of the theme-specific indicator).
        # Implemented via a custom indicator element for the base "TCheckbutton" style.
        try:
            from PIL import Image, ImageDraw, ImageTk  # type: ignore

            def _mk_indicator(*, selected: bool, disabled: bool) -> "ImageTk.PhotoImage":
                size = 18
                img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                d = ImageDraw.Draw(img)

                border = "#D1D5DB" if not disabled else "#E5E7EB"
                fill = "#FFFFFF" if not disabled else "#F9FAFB"
                if selected:
                    fill = "#2563EB" if not disabled else "#93C5FD"
                    border = fill

                d.rounded_rectangle((1, 1, size - 2, size - 2), radius=4, outline=border, fill=fill, width=2)

                if selected:
                    # Draw a simple checkmark "√"
                    check = "#FFFFFF" if not disabled else "#EFF6FF"
                    d.line((4, 10, 8, 14), fill=check, width=3)
                    d.line((8, 14, 14, 5), fill=check, width=3)

                return ImageTk.PhotoImage(img)

            # Keep references to avoid Tk image GC.
            self._oceans_cb_off = _mk_indicator(selected=False, disabled=False)
            self._oceans_cb_on = _mk_indicator(selected=True, disabled=False)
            self._oceans_cb_off_dis = _mk_indicator(selected=False, disabled=True)
            self._oceans_cb_on_dis = _mk_indicator(selected=True, disabled=True)

            style.element_create(
                "Oceans.Checkbutton.indicator",
                "image",
                self._oceans_cb_off,
                ("disabled", self._oceans_cb_off_dis),
                ("selected", self._oceans_cb_on),
                ("selected", "disabled", self._oceans_cb_on_dis),
            )

            style.layout(
                "TCheckbutton",
                [
                    (
                        "Checkbutton.padding",
                        {
                            "sticky": "nswe",
                            "children": [
                                ("Oceans.Checkbutton.indicator", {"side": "left", "sticky": ""}),
                                (
                                    "Checkbutton.focus",
                                    {
                                        "side": "left",
                                        "sticky": "w",
                                        "children": [("Checkbutton.label", {"sticky": "nswe"})],
                                    },
                                ),
                            ],
                        },
                    )
                ],
            )
        except Exception:
            pass

    def _build_ui(self) -> None:
        container = ttk.Frame(self, padding=18, style="TFrame")
        container.pack(fill="both", expand=True)

        header = ttk.Label(container, text="OceanS Paper Generator", style="Title.TLabel")
        header.pack(anchor="w", pady=(0, 12))

        notebook = ttk.Notebook(container)
        notebook.pack(fill="both", expand=True)

        self.tab_generate = ttk.Frame(notebook, style="TFrame")
        self.tab_settings = ttk.Frame(notebook, style="TFrame")
        notebook.add(self.tab_generate, text="生成论文")
        notebook.add(self.tab_settings, text="设置")

        self._build_generate_tab(self.tab_generate)
        self._build_settings_tab(self.tab_settings)

    def _build_generate_tab(self, parent: ttk.Frame) -> None:
        card = ttk.Frame(parent, padding=18, style="Card.TFrame")
        card.pack(fill="both", expand=True, padx=4, pady=4)

        ttk.Label(card, text="生成", style="Subtitle.TLabel").pack(anchor="w")
        ttk.Label(
            card,
            text="输入主题并选择论文类型，生成结果将输出到固定文件夹。",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 14))

        ttk.Label(card, text="主题 / 方向", style="Body.TLabel").pack(anchor="w")
        self.topic_text = tk.Text(
            card,
            height=4,
            wrap="word",
            relief="solid",
            bd=1,
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
        )
        self.topic_text.pack(fill="x", pady=(6, 14))

        type_row = ttk.Frame(card, style="Card.TFrame")
        type_row.pack(fill="x")
        ttk.Label(type_row, text="论文类型", style="Body.TLabel").pack(anchor="w")

        self.paper_type = tk.StringVar(value="英文CS论文")
        radio_row = ttk.Frame(type_row, style="Card.TFrame")
        radio_row.pack(anchor="w", pady=(6, 14))
        self.paper_type_radios: list[ttk.Radiobutton] = []
        for label in PROMPT_MAP.keys():
            rb = ttk.Radiobutton(radio_row, text=label, value=label, variable=self.paper_type)
            rb.pack(side="left", padx=(0, 14))
            self.paper_type_radios.append(rb)

        action_row = ttk.Frame(card, style="Card.TFrame")
        action_row.pack(fill="x", pady=(4, 10))

        self.btn_start = ttk.Button(action_row, text="开始生成", style="Accent.TButton", command=self._on_start)
        self.btn_start.pack(side="left")

        self.progress = ttk.Progressbar(action_row, mode="indeterminate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(12, 0))

        out_card = ttk.Frame(card, padding=12, style="Card.TFrame")
        out_card.pack(fill="x", pady=(6, 10))
        ttk.Label(out_card, text="输出目录", style="Body.TLabel").pack(anchor="w")
        ttk.Label(out_card, text=str(self.output_root), style="Muted.TLabel").pack(anchor="w", pady=(4, 6))
        ttk.Label(
            out_card,
            text="提示：生成结束后，请到该目录下的本次任务文件夹查看全部结果文件；最终论文通常为 paper_final.docx。",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(0, 10))

        out_actions = ttk.Frame(out_card, style="Card.TFrame")
        out_actions.pack(fill="x")
        ttk.Button(out_actions, text="打开输出目录", command=self._open_output_dir).pack(side="left")
        self.btn_open_run_dir = ttk.Button(out_actions, text="打开本次结果", command=self._open_current_run_dir)
        self.btn_open_run_dir.pack(side="left", padx=(10, 0))
        self.btn_open_run_dir.configure(state="disabled")

        self.status_label = ttk.Label(card, text="状态：就绪", style="Muted.TLabel")
        self.status_label.pack(anchor="w", pady=(8, 6))

        ttk.Label(card, text="运行日志", style="Body.TLabel").pack(anchor="w")
        self.log_text = tk.Text(
            card,
            height=12,
            wrap="word",
            relief="solid",
            bd=1,
            state="disabled",
            bg="#FFFFFF",
            fg="#111827",
            insertbackground="#111827",
        )
        self.log_text.pack(fill="both", expand=True, pady=(6, 0))

    def _build_settings_tab(self, parent: ttk.Frame) -> None:
        card = ttk.Frame(parent, padding=18, style="Card.TFrame")
        card.pack(fill="both", expand=True, padx=4, pady=4)

        header = ttk.Frame(card, style="Card.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text="API 设置", style="Subtitle.TLabel").pack(side="left", anchor="w")

        def _open_get_api() -> None:
            import webbrowser

            webbrowser.open("https://0-0.pro/")

        ttk.Button(header, text="获取API", command=_open_get_api).pack(side="left", padx=(10, 0))
        ttk.Label(
            card,
            text="保存后会在运行时写入环境变量：API_KEY / BASE_URL / MODEL / 网页抓取Key（ThorData）。",
            style="Muted.TLabel",
        ).pack(anchor="w", pady=(2, 14))

        form = ttk.Frame(card, style="Card.TFrame")
        form.pack(fill="x")

        self.var_api_key = tk.StringVar(value=self.config_data.api_key)
        self.var_base_url = tk.StringVar(value=(self.config_data.base_url or DEFAULT_BASE_URL))
        self.var_model = tk.StringVar(value=self.config_data.model)
        self.var_thor = tk.StringVar(value=self.config_data.thordata_key)
        self.var_search_mode = tk.BooleanVar(value=bool(self.config_data.search_mode))

        self._add_labeled_entry(form, "API_KEY", self.var_api_key, secret=True)
        self._add_labeled_entry(form, "BASE_URL", self.var_base_url, secret=False)
        self._add_labeled_entry(form, "MODEL", self.var_model, secret=False)
        self._add_labeled_entry(form, "网页抓取 Key（ThorData）", self.var_thor, secret=True, helper="环境变量名：THORDATA_KEY（用于 search_web 联网搜索/网页抓取）")

        search_row = ttk.Frame(form, style="Card.TFrame")
        search_row.pack(fill="x", pady=(0, 10))
        ttk.Label(search_row, text="搜索模式", style="Body.TLabel").pack(anchor="w")
        ttk.Checkbutton(
            search_row,
            text="启用 OpenAI-Compatible 搜索接口（无需网页抓取Key）",
            variable=self.var_search_mode,
        ).pack(anchor="w", pady=(6, 0))
        ttk.Label(
            search_row,
            text="说明：启用后，当未填写“网页抓取 Key（ThorData）”时，search_web 会改用 BASE_URL 同域的 /v1/search?q=...；Authorization 使用上方填写的 API_KEY。",
            style="Muted.TLabel",
            wraplength=780,
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        btn_row = ttk.Frame(card, style="Card.TFrame")
        btn_row.pack(fill="x", pady=(10, 0))
        ttk.Button(btn_row, text="保存设置", style="Accent.TButton", command=self._on_save_settings).pack(side="left")

        self.settings_hint = ttk.Label(card, text="", style="Muted.TLabel")
        self.settings_hint.pack(anchor="w", pady=(10, 0))

        summary = ttk.Frame(card, padding=12, style="Card.TFrame")
        summary.pack(fill="x", pady=(14, 0))
        ttk.Label(summary, text="当前配置（脱敏）", style="Body.TLabel").pack(anchor="w")
        self.config_summary = tk.Text(summary, height=5, wrap="word", relief="solid", bd=1)
        self.config_summary.pack(fill="x", pady=(6, 0))
        self._refresh_config_summary()

    def _add_labeled_entry(
        self,
        parent: ttk.Frame,
        label: str,
        var: tk.StringVar,
        *,
        secret: bool,
        helper: str = "",
    ) -> None:
        row = ttk.Frame(parent, style="Card.TFrame")
        row.pack(fill="x", pady=(0, 10))
        ttk.Label(row, text=label, style="Body.TLabel").pack(anchor="w")
        entry = ttk.Entry(row, textvariable=var, show="•" if secret else "")
        entry.pack(fill="x", pady=(6, 0))
        if helper:
            ttk.Label(row, text=helper, style="Muted.TLabel").pack(anchor="w", pady=(4, 0))

    def _refresh_config_summary(self) -> None:
        self.config_summary.configure(state="normal")
        self.config_summary.delete("1.0", "end")
        self.config_summary.insert("1.0", self.config_data.masked_summary())
        self.config_summary.configure(state="disabled")

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _on_save_settings(self) -> None:
        self.config_data = AppConfig(
            api_key=self.var_api_key.get().strip(),
            base_url=self.var_base_url.get().strip(),
            model=self.var_model.get().strip(),
            thordata_key=self.var_thor.get().strip(),
            search_mode=bool(self.var_search_mode.get()),
        )
        self.config_data.save(self.config_path)
        self.settings_hint.configure(text=f"已保存到：{self.config_path}")
        self._refresh_config_summary()

    def _open_output_dir(self) -> None:
        try:
            import os
            os.startfile(str(self.output_root))  # noqa: S606
        except Exception as e:
            self._append_log(f"[打开目录失败] {e}")

    def _open_current_run_dir(self) -> None:
        if not self.current_run_output_dir:
            return
        try:
            import os
            os.startfile(str(self.current_run_output_dir))  # noqa: S606
        except Exception as e:
            self._append_log(f"[打开目录失败] {e}")

    def _ask_user_input(self, prompt: str) -> str:
        dialog = tk.Toplevel(self)
        dialog.title("需要输入")
        dialog.configure(bg="#FFFFFF")
        dialog.geometry("520x220")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        lbl = tk.Label(dialog, text=prompt, bg="#FFFFFF", fg="#111827", justify="left", wraplength=480, font=("Segoe UI", 10))
        lbl.pack(anchor="w", padx=16, pady=(14, 10))

        entry = ttk.Entry(dialog)
        entry.pack(fill="x", padx=16)
        entry.focus_set()

        result: dict[str, str] = {"value": ""}

        def on_ok() -> None:
            result["value"] = entry.get().strip()
            dialog.destroy()

        def on_cancel() -> None:
            result["value"] = ""
            dialog.destroy()

        btn_row = tk.Frame(dialog, bg="#FFFFFF")
        btn_row.pack(fill="x", padx=16, pady=14)
        ttk.Button(btn_row, text="取消", command=on_cancel).pack(side="right", padx=(8, 0))
        ttk.Button(btn_row, text="确定", style="Accent.TButton", command=on_ok).pack(side="right")

        self.wait_window(dialog)
        return result["value"]

    def _poll_queues(self) -> None:
        # Handle input requests from worker thread.
        try:
            while True:
                prompt, resp_q = self._input_queue.get_nowait()
                answer = self._ask_user_input(prompt)
                resp_q.put(answer)
        except queue.Empty:
            pass

        # Handle status updates/logs.
        try:
            while True:
                kind, payload = self._status_queue.get_nowait()
                if kind == "status":
                    self.status_label.configure(text=f"状态：{payload}")
                elif kind == "log":
                    self._append_log(payload)
                elif kind == "result_dir":
                    p = Path(payload)
                    if p.exists():
                        self.current_run_output_dir = p
                        self.btn_open_run_dir.configure(state="normal")
                elif kind == "done":
                    self.progress.stop()
                    self.btn_start.configure(state="normal")
                    self.topic_text.configure(state="normal")
                    for rb in self.paper_type_radios:
                        rb.configure(state="normal")
                    self.status_label.configure(text=f"状态：完成")
                    self._append_log(payload)
                elif kind == "error":
                    self.progress.stop()
                    self.btn_start.configure(state="normal")
                    self.topic_text.configure(state="normal")
                    for rb in self.paper_type_radios:
                        rb.configure(state="normal")
                    self.status_label.configure(text=f"状态：失败")
                    self._append_log(payload)
        except queue.Empty:
            pass

        self.after(150, self._poll_queues)

    def _on_start(self) -> None:
        topic = self.topic_text.get("1.0", "end").strip()
        paper_type = self.paper_type.get()
        prompt_rel = PROMPT_MAP.get(paper_type, PROMPT_MAP["英文CS论文"])

        if not topic:
            self._append_log("[提示] 请输入主题/方向。")
            return

        if not (self.config_data.api_key and self.config_data.base_url and self.config_data.model):
            self._append_log("[提示] 请先在“设置”中配置 API_KEY / BASE_URL / MODEL。")
            return

        run_id = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        internal_dir = self.internal_work_root / run_id
        output_dir = self.output_root / run_id

        self.btn_start.configure(state="disabled")
        self.current_run_output_dir = output_dir
        self.btn_open_run_dir.configure(state="normal")
        self.topic_text.configure(state="disabled")
        for rb in self.paper_type_radios:
            rb.configure(state="disabled")
        self.progress.start(10)
        self._status_queue.put(("status", "准备中..."))
        self._append_log(f"[开始] 类型={paper_type} 主题={topic}")
        self._append_log(f"[提示] 运行中会持续同步文件到：{output_dir}")

        def request_input(prompt: str) -> str:
            resp_q: "queue.Queue[str]" = queue.Queue(maxsize=1)
            self._input_queue.put((prompt, resp_q))
            return resp_q.get()

        def worker_thread() -> None:
            try:
                self._status_queue.put(("status", "运行中..."))

                def on_log(message: str) -> None:
                    self._status_queue.put(("log", message))

                result = run_paper_job(
                    resource_root=self.resource_root,
                    internal_work_dir=internal_dir,
                    output_dir=output_dir,
                    prompt_rel_path=prompt_rel,
                    topic=topic,
                    api_key=self.config_data.api_key,
                    base_url=self.config_data.base_url,
                    model=self.config_data.model,
                    thordata_key=self.config_data.thordata_key,
                    search_mode=bool(self.config_data.search_mode),
                    request_input=request_input,
                    on_log=on_log,
                )
                self._status_queue.put(("result_dir", str(result.output_dir)))
                self._status_queue.put(("done", f"[完成] 输出目录：{result.output_dir}\\n最终论文通常为：paper_final.docx"))
            except Exception as e:
                tb = traceback.format_exc()
                self._status_queue.put(("result_dir", str(output_dir)))
                self._status_queue.put(("error", f"[失败] {e}\\n{tb}"))

        threading.Thread(target=worker_thread, daemon=True).start()


if __name__ == "__main__":
    PaperApp().mainloop()
