"""
使用 Reaktiv 模拟消息队列 (发布/订阅)

本模块提供了一个 MessageBroker 类，它利用 Reaktiv 的核心原语（Signal, Computed, Effect）
来构建一个功能类似消息队列的、内存中的发布/订阅系统。
"""
import asyncio
from typing import Callable, Any, List, Union, Tuple

from reaktiv import Signal, Effect, Computed, untracked, to_async_iter

class Subscription:
    """封装一个或多个 Effect，提供统一的暂停、恢复和取消订阅的接口。"""

    def __init__(
        self,
        broker: "MessageBroker",
        callback: Callable[[Any], None],
        effects_with_topics: List[Tuple[Effect, str]],
    ):
        self._broker = broker
        self._callback = callback
        self._effects_with_topics = effects_with_topics
        self._effects = [e for e, t in effects_with_topics]
        self.is_paused = Signal(False)

    def pause(self):
        """暂停订阅，将不再处理新消息。"""
        self.is_paused.set(True)
        if self._broker.debug:
            print(f"Subscription paused.")

    def resume(self):
        """恢复订阅，将继续处理新消息。"""
        self.is_paused.set(False)
        if self._broker.debug:
            print(f"Subscription resumed.")

    def dispose(self):
        """永久取消订阅并清理资源。"""
        for effect, topic in self._effects_with_topics:
            effect.dispose()
            # 从代理的注册表中移除
            if (
                topic in self._broker._effects_registry
                and self._callback in self._broker._effects_registry[topic]
            ):
                del self._broker._effects_registry[topic][self._callback]
                if not self._broker._effects_registry[topic]:
                    del self._broker._effects_registry[topic]
        if self._broker.debug:
            print(f"Subscription disposed.")


class MessageBroker:
    """一个简单的消息代理，使用 Reaktiv Signal 和 Computed 模拟消息队列和派生主题。"""

    def __init__(self, debug: bool = False):
        # 现在 _topics 可以存储 Signal (原始主题) 或 Computed (派生主题)。
        self._topics: dict[str, Union[Signal[List[Any]], Computed[List[Any]]]] = {}
        # 新增: 注册表来跟踪 (主题, 回调) -> Effect 的映射
        self._effects_registry: dict[str, dict[Callable, Effect]] = {}
        self.debug = debug
        self._channel_counters: dict[str, int] = {}
        # print("消息代理已启动。")

    def request_channel(self, prefix: str = "channel") -> str:
        """
        申请一个新的、唯一的频道名称。

        此方法为每个前缀维护一个独立的计数器。
        返回一个基于前缀和该前缀当前计数值的唯一字符串，例如 'channel0', 'worker_0', 'channel1'。
        它不直接创建主题或任何关联的 Signal；这将在首次发布或订阅到返回的主题名称时发生。

        Args:
            prefix: 频道名称的前缀。默认为 'channel'。

        Returns:
            一个基于前缀的唯一主题/频道名称字符串。
        """
        if prefix not in self._channel_counters:
            self._channel_counters[prefix] = 0

        channel_name = f"{prefix}{self._channel_counters[prefix]}"
        self._channel_counters[prefix] += 1
        return channel_name

    def publish(self, message: Any, topic: Union[str, List[str]] = "default"):
        """
        向一个或多个主题发布一条新消息。
        """
        topics_to_publish = [topic] if isinstance(topic, str) else topic

        for t in topics_to_publish:
            # 只能向原始主题发布
            topic_signal = self._topics.get(t)
            if not isinstance(topic_signal, Signal):
                print(f"警告：主题 '{t}' 不存在或不是一个可发布的原始主题。正在创建...")
                topic_signal = Signal([])
                self._topics[t] = topic_signal

            # 通过 update 方法追加新消息来触发更新。
            # 必须创建一个新列表才能让 Reaktiv 检测到变化。
            topic_signal.update(lambda messages: messages + [message])
            if self.debug:
                print(f"新消息发布到 '{t}': \"{message}\"")

    def subscribe(self, callback: Callable[[Any], None], topic: Union[str, List[str]] = "default") -> Subscription:
        """
        订阅一个或多个主题。每当有新消息发布时，回调函数将被调用。
        此方法是幂等的：重复订阅同一个回调到同一个主题不会产生副作用。

        Args:
            callback: 处理消息的回调函数。
            topic: 要订阅的主题，可以是单个字符串或字符串列表。

        Returns:
            一个 Subscription 实例，用于管理订阅的生命周期（暂停、恢复、取消）。
        """
        topics_to_subscribe = [topic] if isinstance(topic, str) else topic
        created_effects_with_topics = []

        # 创建一个 Subscription 实例来管理所有相关的 effects
        # 它需要提前创建，以便 effect_factory 可以访问它的 is_paused 信号
        subscription = Subscription(self, callback, created_effects_with_topics)

        for t in topics_to_subscribe:
            # 检查此回调是否已订阅该主题
            if t in self._effects_registry and callback in self._effects_registry.get(t, {}):
                print(f"警告：订阅者 '{callback.__name__}' 已经订阅了 '{t}' 主题。跳过。")
                continue

            if t not in self._topics:
                # 如果订阅一个不存在的主题，也为它创建一个 Signal
                self._topics[t] = Signal([])

            # 使用一个工厂函数来为每个主题创建独立的闭包，
            # 确保每个订阅都有自己的 'last_processed_index'。
            def effect_factory(current_topic: str):
                last_processed_index = 0

                def process_new_messages():
                    nonlocal last_processed_index
                    all_messages = self._topics[current_topic]()

                    # 如果暂停了，只更新索引以跳过消息，不进行处理
                    if untracked(subscription.is_paused):
                        last_processed_index = len(all_messages)
                        return

                    new_messages = all_messages[last_processed_index:]

                    if new_messages:
                        if self.debug:
                            print(f"    -> 订阅者 '{callback.__name__}' 在 '{current_topic}' 主题上收到 {len(new_messages)} 条新消息。{new_messages}")
                        for msg in new_messages:
                            try:
                                if asyncio.iscoroutinefunction(callback):
                                    asyncio.create_task(callback(msg))
                                else:
                                    callback(msg)
                            except Exception as e:
                                print(f"    !! 在订阅者 '{callback.__name__}' 中发生错误: {e}")

                    last_processed_index = len(all_messages)
                return process_new_messages

            if self.debug:
                print(f"订阅者 '{callback.__name__}' 已订阅 '{t}' 主题。")
            effect = Effect(effect_factory(t))

            # 注册新的 effect
            if t not in self._effects_registry:
                self._effects_registry[t] = {}
            self._effects_registry[t][callback] = effect

            created_effects_with_topics.append((effect, t))

        return subscription

    def create_derived_topic(self, new_topic_name: str, source_topic: str, transform_fn: Callable[[List[Any]], List[Any]]):
        """
        创建一个派生主题。

        这个新主题的内容是一个 Computed 信号，它会根据源主题的内容和转换函数自动更新。

        Args:
            new_topic_name: 派生主题的名称。
            source_topic: 源主题的名称。
            transform_fn: 一个函数，接收源主题的消息列表并返回新的消息列表。
        """
        if new_topic_name in self._topics:
            print(f"警告：主题 '{new_topic_name}' 已存在。")
            return

        source_signal = self._topics.get(source_topic)
        if not isinstance(source_signal, (Signal, Computed)):
            print(f"错误：源主题 '{source_topic}' 不存在。")
            return

        # 创建一个 Computed 信号作为派生主题
        derived_signal = Computed(
            lambda: transform_fn(source_signal())
        )

        self._topics[new_topic_name] = derived_signal
        if self.debug:
            print(f"已从 '{source_topic}' 创建派生主题 '{new_topic_name}'。")

    async def iter_topic(self, topic: str):
        """
        返回一个异步迭代器，用于通过 async for 循环消费主题消息。

        Args:
            topic: 要订阅的主题名称。

        Yields:
            主题中的新消息。
        """
        if topic not in self._topics:
            # 如果主题不存在，创建一个，以防万一
            self._topics[topic] = Signal([])

        topic_signal = self._topics[topic]
        last_yielded_index = 0

        # to_async_iter 会在每次 topic_signal 更新时产生一个新的消息列表
        async for all_messages in to_async_iter(topic_signal):
            new_messages = all_messages[last_yielded_index:]
            for msg in new_messages:
                # 过滤掉内部的 'init' 消息
                if msg != "init":
                    yield msg

            last_yielded_index = len(all_messages)