import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from core.circuit_breaker import CircuitBreaker, State
from core.task_queue import TaskQueue

class ResilienceIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_circuit_breaker_transitions(self):
        """Verify CB opens after failures and closes after success."""
        cb = CircuitBreaker(name="test-cb", failure_threshold=2, recovery_sec=0.1)
        
        # 1. Successful calls
        async def success_fn(): return "ok"
        self.assertEqual(await cb.call(success_fn()), "ok")
        self.assertEqual(cb.state, State.CLOSED)
        
        # 2. Failure calls
        async def fail_fn(): raise ValueError("fail")
        
        with self.assertRaises(ValueError):
            await cb.call(fail_fn())
        with self.assertRaises(ValueError):
            await cb.call(fail_fn())
            
        # Should now be OPEN
        self.assertEqual(cb.state, State.OPEN)
        
        # 3. Call while OPEN should fail fast
        with self.assertRaises(RuntimeError) as cm:
            await cb.call(success_fn())
        self.assertIn("Circuit breaker OPEN for test-cb", str(cm.exception))
        
        # 4. Wait for recovery
        await asyncio.sleep(0.15)
        self.assertEqual(cb.state, State.HALF_OPEN)
        
        # 5. Success in HALF_OPEN should CLOSE it
        self.assertEqual(await cb.call(success_fn()), "ok")
        self.assertEqual(cb.state, State.CLOSED)

    async def test_task_queue_execution(self):
        """Verify TaskQueue executes enqueued functions."""
        queue = TaskQueue(name="test-queue", workers=1)
        await queue.start()
        
        future = asyncio.get_running_loop().create_future()
        
        async def mock_task(val):
            future.set_result(val)
        
        # TaskQueue expects a function + args
        await queue.enqueue(mock_task, "done")
        
        result = await asyncio.wait_for(future, timeout=1.0)
        self.assertEqual(result, "done")
        
        await queue.stop()

if __name__ == "__main__":
    unittest.main()
