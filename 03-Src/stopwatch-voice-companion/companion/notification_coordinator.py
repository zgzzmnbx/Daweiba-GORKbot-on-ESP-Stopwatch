"""One process-level lane for automatic desktop, Watch and sound output."""
import asyncio
import heapq
import itertools
import time


class NotificationCoordinator:
    def __init__(self, control):
        self.control = control
        self.queue = []
        self.sequence = itertools.count()
        self.condition = asyncio.Condition()
        self.active = False
        self.presentation = None

    async def dispatch(self, *, source, priority, valid, action, ttl=90):
        token = (-priority, next(self.sequence), source, time.monotonic() + ttl)
        queued = True
        try:
            async with self.condition:
                heapq.heappush(self.queue, token)
                self.condition.notify_all()
                while True:
                    if not valid() or time.monotonic() >= token[3]:
                        return False
                    current = self.blocking_current()
                    presentation_blocks = current and current['priority'] >= priority
                    if not self.active and self.queue[0] == token and self.control.auto_available() and not presentation_blocks:
                        heapq.heappop(self.queue)
                        queued = False
                        self.active = True
                        break
                    try:
                        await asyncio.wait_for(self.condition.wait(), 0.2)
                    except asyncio.TimeoutError:
                        pass
            if not valid() or not self.control.auto_available():
                return False
            await action()
            return True
        finally:
            async with self.condition:
                if queued and token in self.queue:
                    self.queue.remove(token)
                    heapq.heapify(self.queue)
                elif not queued:
                    self.active = False
                self.condition.notify_all()

    def show(self, source, expression, bubble, revision, seconds=12, priority=2,
             block_seconds=None, dismiss_on_click=False):
        now = time.monotonic()
        self.presentation = {'source': source, 'expression': expression, 'bubble': bubble,
                             'revision': revision, 'priority': priority,
                             'until': now + seconds,
                             'blocks_until': now + (seconds if block_seconds is None else block_seconds),
                             'dismiss_on_click': dismiss_on_click}

    def clear(self, source=None):
        if not source or (self.presentation and self.presentation['source'] == source):
            self.presentation = None

    def current(self):
        value = self.presentation
        return value if value and value['until'] > time.monotonic() else None

    def blocking_current(self):
        value = self.current()
        return value if value and value['blocks_until'] > time.monotonic() else None
