import asyncio
from typing import Dict, List, Any

class EventBus:
    def __init__(self):
        # Maps topic string to list of (event_loop, asyncio.Queue)
        self._subscribers: Dict[str, List[tuple[asyncio.AbstractEventLoop, asyncio.Queue]]] = {}

    def subscribe(self, topic: str) -> asyncio.Queue:
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue()
        self._subscribers[topic].append((loop, queue))
        return queue

    def unsubscribe(self, topic: str, queue: asyncio.Queue):
        if topic in self._subscribers:
            self._subscribers[topic] = [sq for sq in self._subscribers[topic] if sq[1] != queue]

    def publish(self, topic: str, event: Any):
        if topic in self._subscribers:
            for loop, queue in self._subscribers[topic]:
                # Safe to call from any thread
                loop.call_soon_threadsafe(queue.put_nowait, event)

bus = EventBus()
