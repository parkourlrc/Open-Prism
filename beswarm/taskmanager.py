import os
import json
import uuid
import asyncio
from enum import Enum
from pathlib import Path

from .aient.aient.plugins import registry

class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"
    NOT_FOUND = "NOT_FOUND"


class TaskManager:
    """
    一个带并发控制的异步任务管理器。
    它管理任务的生命周期，并通过一个固定大小的工作者池来控制并发执行的任务数量。
    """
    def __init__(self, concurrency_limit=None):
        self.raw_concurrency_limit = concurrency_limit
        self.concurrency_limit = concurrency_limit or int(os.getenv("BESWARM_CONCURRENCY_LIMIT", "3"))

        if self.concurrency_limit <= 0:
            raise ValueError("并发限制必须大于0")

        self.tasks_cache = {}          # 存储所有任务的状态和元数据, key: task_id
        self.task_events = {}          # 为每个任务存储一个asyncio.Event，用于等待特定任务完成

        self._pending_queue = asyncio.Queue() # 内部待办任务队列
        self._results_queue = asyncio.Queue() # 内部已完成任务结果队列
        self._workers = []                    # 持有工作者任务的引用
        self._is_running = False              # 标记工作者池是否在运行
        self.root_path = None
        self.cache_dir = None
        self.task_cache_file = None

    async def set_root_path(self, root_path):
        """设置工作根目录并加载持久化的任务状态。"""
        if self.root_path is not None:
            return
        self.root_path = Path(root_path)
        self.cache_dir = self.root_path / ".beswarm"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.task_cache_file = self.cache_dir / "tasks.json"

        self._load_tasks_from_cache()
        self.set_task_cache("root_path", str(self.root_path))

        if not self.raw_concurrency_limit:
            self.concurrency_limit = int(os.getenv("BESWARM_CONCURRENCY_LIMIT", "3"))

        # 启动工作者池
        self.start()
        # 恢复中断的任务
        await self.resume_interrupted_tasks()

    def start(self):
        """启动并发工作者池。"""
        if self._is_running:
            return

        self._is_running = True
        for i in range(self.concurrency_limit):
            worker = asyncio.create_task(self._worker_loop(f"Worker-{i+1}"))
            self._workers.append(worker)
        print(f"已启动 {self.concurrency_limit} 个并发工作者。")

    async def stop(self):
        """优雅地停止所有工作者。"""
        if not self._is_running:
            return

        print("\n正在停止 TaskManager...")
        await self._pending_queue.join()

        for worker in self._workers:
            worker.cancel()

        await asyncio.gather(*self._workers, return_exceptions=True)

        self._is_running = False
        print("所有工作者已停止。")

    async def _worker_loop(self, worker_name: str):
        """每个工作者的主循环，从队列中拉取并执行任务。"""
        while self._is_running:
            try:
                task_id, coro = await self._pending_queue.get()

                print(f"[{worker_name}] 领到了任务 <{task_id[:8]}>，开始执行...")
                self._update_task_status(task_id, TaskStatus.RUNNING)

                try:
                    result = await coro
                    self._handle_task_completion(task_id, TaskStatus.DONE, result)
                except Exception as e:
                    self._handle_task_completion(task_id, TaskStatus.ERROR, e)
                finally:
                    self._pending_queue.task_done()

            except asyncio.CancelledError:
                # print(f"[{worker_name}] 被取消，正在退出...")
                break
            except Exception as e:
                print(f"[{worker_name}] 循环中遇到严重错误: {e}")

    def _handle_task_completion(self, task_id, status, result):
        """统一处理任务完成的内部函数。"""
        if status == TaskStatus.DONE:
            print(f"✅ 任务 <{task_id[:8]}> 执行成功。")
        else: # ERROR
            print(f"❌ 任务 <{task_id[:8]}> 执行失败: {result}")

        self._update_task_status(task_id, status, result=str(result))
        self._results_queue.put_nowait((task_id, status, result))
        if task_id in self.task_events:
            self.task_events[task_id].set()

    def set_task_cache(self, *keys_and_value):
        """设置可嵌套的任务缓存。"""
        if len(keys_and_value) < 2: return
        keys, value = keys_and_value[:-1], keys_and_value[-1]
        d = self.tasks_cache
        for key in keys[:-1]:
            d = d.setdefault(key, {})
        d[keys[-1]] = value
        self._save_tasks_to_cache()

    def _save_tasks_to_cache(self):
        """将任务缓存持久化到文件。"""
        if not self.task_cache_file: return
        try:
            with self.task_cache_file.open('w', encoding='utf-8') as f:
                json.dump(self.tasks_cache, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"警告：无法将任务状态持久化到文件: {e}")

    def _load_tasks_from_cache(self):
        """从文件加载任务缓存。"""
        if not self.task_cache_file or not self.task_cache_file.exists():
            self.tasks_cache = {}
            return
        try:
            content = self.task_cache_file.read_text(encoding='utf-8')
            if content:
                self.tasks_cache = json.loads(content)
            else:
                self.tasks_cache = {}
        except (FileNotFoundError, json.JSONDecodeError):
            self.tasks_cache = {}
            print("警告：任务缓存文件不存在或格式错误，将使用空缓存。")

    async def get_next_result(self):
        """异步获取下一个完成的任务结果。"""
        return await self._results_queue.get()

    def create_tasks_batch(self, task_coro_func, tasks_params_list):
        """
        批量创建任务，但不是立即执行，而是将它们放入待处理队列。
        """
        if not self._is_running:
            raise RuntimeError("TaskManager尚未启动。请先调用 start() 方法。")

        task_ids = []
        for params in tasks_params_list:
            task_id = str(uuid.uuid4())
            self.task_events[task_id] = asyncio.Event()
            coro = task_coro_func(**params)

            # 初始化任务状态为 PENDING
            self._update_task_status(task_id, TaskStatus.PENDING, args=params)

            # 将任务定义放入队列
            self._pending_queue.put_nowait((task_id, coro))
            task_ids.append(task_id)

        print(f"已将 {len(task_ids)} 个新任务加入待处理队列。队列当前大小: {self._pending_queue.qsize()}")
        return task_ids

    def create_tasks(self, task_coro_func, tasks_params_list):
        """批量将任务放入待处理队列。"""
        if not self._is_running:
            raise RuntimeError("TaskManager尚未启动。请先在 set_root_path 后确保其已启动。")

        task_ids = []
        for params in tasks_params_list:
            task_id = str(uuid.uuid4())
            self.task_events[task_id] = asyncio.Event()
            coro = task_coro_func(**params)

            self._update_task_status(task_id, TaskStatus.PENDING, args=params)
            self._pending_queue.put_nowait((task_id, coro))
            task_ids.append(task_id)

        print(f"已将 {len(task_ids)} 个新任务加入待处理队列。队列当前大小: {self._pending_queue.qsize()}")
        return task_ids

    async def resume_interrupted_tasks(self):
        """在启动时，恢复所有处于 PENDING 或 RUNNING 状态的旧任务。"""
        interrupted_tasks = [
            (tid, info) for tid, info in self.tasks_cache.items()
            if tid != "root_path" and info.get("status") in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]
        ]

        if not interrupted_tasks:
            return

        print(f"检测到 {len(interrupted_tasks)} 个中断的任务，正在恢复...")
        worker_fun = registry.tools["worker"]

        for task_id, task_info in interrupted_tasks:
            self.task_events[task_id] = asyncio.Event()
            args = task_info.get("args")
            if not args:
                print(f"警告：任务 <{task_id[:8]}> 缺少参数，无法恢复。")
                self._update_task_status(task_id, TaskStatus.ERROR, result="缺少参数，无法恢复")
                continue

            coro = worker_fun(**args)
            self._update_task_status(task_id, TaskStatus.PENDING)
            await self._pending_queue.put((task_id, coro))

        print(f"{len(interrupted_tasks)} 个中断的任务已重新加入队列。")

    def resume_task(self, task_id, goal):
        """恢复一个指定的任务，实质上是创建一个新任务并替换旧的记录，但ID保持不变。"""
        if task_id not in self.tasks_cache:
            return f"任务 {task_id} 不存在"

        old_task_info = self.tasks_cache.get(task_id, {})
        tasks_params = old_task_info.get("args", {})
        if not tasks_params:
             return f"<tool_error>任务 {task_id} 缺少参数信息，无法恢复。</tool_error>"

        tasks_params["goal"] = goal
        tasks_params["cache_messages"] = True # 恢复时强制使用缓存

        worker_fun = registry.tools["worker"]
        coro = worker_fun(**tasks_params)

        self.task_events[task_id] = asyncio.Event()
        self._update_task_status(task_id, TaskStatus.PENDING, args=tasks_params)
        self._pending_queue.put_nowait((task_id, coro))

        print(f"任务 <{task_id[:8]}> 已被重新加入队列等待恢复执行。")
        return f"任务 {task_id} 已恢复"

    def _update_task_status(self, task_id, status: TaskStatus, args=None, result=None):
        """统一更新任务状态缓存并持久化。"""
        if task_id not in self.tasks_cache:
            self.tasks_cache[task_id] = {}

        current_task = self.tasks_cache[task_id]
        current_task['status'] = status.value
        if args is not None:
            current_task['args'] = args
        if result is not None:
            current_task['result'] = result

        self._save_tasks_to_cache()

    def get_task_status(self, task_id):
        """查询特定任务的状态。"""
        task_info = self.tasks_cache.get(task_id)
        if not task_info:
            return TaskStatus.NOT_FOUND
        return TaskStatus(task_info.get("status", "NOT_FOUND"))

    def get_task_result(self, task_id):
        """获取已完成任务的结果。"""
        task_info = self.tasks_cache.get(task_id)
        if not task_info or task_info.get("status") not in [TaskStatus.DONE.value, TaskStatus.ERROR.value]:
            return None
        return task_info.get("result")

async def main():
    manager = TaskManager()

    # --- 任务提交阶段 ---
    print("--- 任务提交 ---")

    tasks_to_run = [
        {"goal": ""},
        {"goal": 1},
        {"goal": 5},
        {"goal": 2},
        {"goal": 4},
    ]
    task_ids = manager.create_tasks(registry.tools["worker"], tasks_to_run)
    print(f"\n主程序: {len(task_ids)} 个任务已提交，现在开始等待结果...\n")

    # --- 结果处理阶段 ---
    # 使用 get_next_result() 逐个获取已完成任务的结果
    print("--- 结果处理 ---")
    for i in range(len(task_ids)):
        print(f"等待第 {i + 1} 个任务完成...")
        # 此处会异步等待，直到队列中有可用的结果
        task_id, status, result = await manager.get_next_result()

        # 从管理器中获取任务名称（如果需要）
        task_name = manager.tasks[task_id].get_name()

        print(f"-> 收到结果: 任务 {task_name}, index: {manager.get_task_index(task_id)}")
        print(f"  - 状态: {status.value}")

        if status == TaskStatus.DONE:
            print(f"  - 结果: '{result}'")
        elif status == TaskStatus.ERROR:
            print(f"  - 错误: {result}")
        elif status == TaskStatus.CANCELLED:
            print("  - 结果: 任务被取消")
        print("-" * 20)

    print("\n--- 所有任务的结果都已处理完毕 ---")


# 运行主协程
if __name__ == "__main__":
    asyncio.run(main())
    print("\n主程序: 所有任务都已完成并处理。")