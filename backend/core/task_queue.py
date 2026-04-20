"""
Simple in-process background task queue using asyncio.Queue.
Offloads heavy/slow tasks from the main incident pipeline.
"""
import asyncio
import logging
from typing import Any, Callable, Coroutine
from core.tracing import set_trace_id, new_trace_id

logger = logging.getLogger(__name__)

class TaskQueue:
    def __init__(self, name: str = "default", workers: int = 2):
        self.name = name
        self.queue = asyncio.Queue()
        self.workers = workers
        self._worker_tasks = []
        self._running = False

    async def start(self):
        """Start worker loop."""
        if self._running:
            return
        self._running = True
        self._worker_tasks = [
            asyncio.create_task(self._worker_loop(i)) 
            for i in range(self.workers)
        ]
        logger.info(f"TaskQueue {self.name} started with {self.workers} workers")

    async def stop(self):
        """Stop worker loop gracefully."""
        self._running = False
        for task in self._worker_tasks:
            task.cancel()
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        logger.info(f"TaskQueue {self.name} stopped")

    async def enqueue(self, func: Callable, *args, **kwargs):
        """Add a task to the queue. Captures current trace_id if available."""
        # Check if we should pass trace_id
        from core.tracing import get_trace_id
        tid = get_trace_id() or new_trace_id()
        
        await self.queue.put((func, args, kwargs, tid))

    async def _worker_loop(self, worker_id: int):
        while self._running:
            try:
                func, args, kwargs, tid = await self.queue.get()
                set_trace_id(tid)
                
                logger.debug(f"Worker {worker_id} starting task {func.__name__} (trace_id={tid})")
                try:
                    await func(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Task {func.__name__} failed: {e}", exc_info=True)
                finally:
                    self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Worker {worker_id} encountered unexpected error: {e}")
                await asyncio.sleep(0.1)
