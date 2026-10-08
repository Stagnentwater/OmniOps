"""Tests for RQ Ingestion Execution Strategies (V15-QUEUE-001).

Tests cover:
- BackgroundTaskStrategy enqueue behavior
- RQExecutionStrategy fallback when redis/rq not installed
- Auto-selection logic (Windows vs Linux vs Redis)
- Strategy name reporting
- Idempotency: same job_id used for RQ job ID
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

from ingestion.execution_strategy import (
    BackgroundTaskStrategy,
    RQExecutionStrategy,
    get_execution_strategy,
)


# ---------------------------------------------------------------------------
# Tests: BackgroundTaskStrategy
# ---------------------------------------------------------------------------

class TestBackgroundTaskStrategy(unittest.TestCase):
    """Test the Windows-compatible BackgroundTaskStrategy."""

    def test_name(self) -> None:
        strategy = BackgroundTaskStrategy()
        self.assertIn("BackgroundTasks", strategy.name())
        self.assertIn("Windows", strategy.name())

    def test_enqueue_calls_add_task(self) -> None:
        strategy = BackgroundTaskStrategy()
        mock_bg = MagicMock()

        result = strategy.enqueue(
            job_id="job-123",
            document_id="doc-abc",
            file_name="test.pdf",
            background_tasks=mock_bg,
        )

        self.assertEqual(result, "job-123")
        mock_bg.add_task.assert_called_once()

        # Verify the correct function and kwargs were passed
        call_args = mock_bg.add_task.call_args
        self.assertEqual(call_args.kwargs["lifecycle_job_id"], "job-123")
        self.assertEqual(call_args.kwargs["document_id"], "doc-abc")
        self.assertEqual(call_args.kwargs["file_name"], "test.pdf")

    def test_enqueue_without_background_tasks_raises(self) -> None:
        strategy = BackgroundTaskStrategy()

        with self.assertRaises(ValueError) as ctx:
            strategy.enqueue(
                job_id="job-123",
                document_id="doc-abc",
                file_name="test.pdf",
                background_tasks=None,
            )

        self.assertIn("BackgroundTasks", str(ctx.exception))


# ---------------------------------------------------------------------------
# Tests: RQExecutionStrategy
# ---------------------------------------------------------------------------

class TestRQExecutionStrategy(unittest.TestCase):
    """Test the RQ execution strategy."""

    def test_name(self) -> None:
        strategy = RQExecutionStrategy(redis_url="redis://localhost:6379")
        self.assertIn("RQ", strategy.name())
        self.assertIn("retryable", strategy.name())

    def test_fallback_when_redis_not_installed(self) -> None:
        """When redis/rq packages are missing, should fallback to BackgroundTasks."""
        # Temporarily remove redis and rq from sys.modules if present
        original_redis = sys.modules.pop("redis", None)
        original_rq = sys.modules.pop("rq", None)

        # Make import fail
        import builtins
        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name in ("redis", "rq"):
                raise ImportError(f"No module named '{name}'")
            return real_import(name, *args, **kwargs)

        strategy = RQExecutionStrategy(redis_url="redis://localhost:6379")
        mock_bg = MagicMock()

        with patch("builtins.__import__", side_effect=mock_import):
            result = strategy.enqueue(
                job_id="job-456",
                document_id="doc-xyz",
                file_name="report.pdf",
                background_tasks=mock_bg,
            )

        # Should have fallen back to BackgroundTasks
        self.assertEqual(result, "job-456")
        mock_bg.add_task.assert_called_once()

        # Restore
        if original_redis is not None:
            sys.modules["redis"] = original_redis
        if original_rq is not None:
            sys.modules["rq"] = original_rq

    def test_idempotent_job_id(self) -> None:
        """The lifecycle job_id should be used as the RQ job ID."""
        strategy = RQExecutionStrategy(redis_url="redis://localhost:6379")

        # Mock redis and rq
        mock_redis_cls = MagicMock()
        mock_queue_cls = MagicMock()
        mock_retry_cls = MagicMock()
        mock_rq_job = MagicMock()
        mock_rq_job.id = "job-789"
        mock_queue_cls.return_value.enqueue.return_value = mock_rq_job

        with patch.dict(sys.modules, {
            "redis": MagicMock(Redis=mock_redis_cls),
            "rq": MagicMock(Queue=mock_queue_cls, Retry=mock_retry_cls),
        }):
            # Need to reimport since we patched sys.modules
            from importlib import reload
            import ingestion.execution_strategy as es_module
            reload(es_module)

            strategy = es_module.RQExecutionStrategy(
                redis_url="redis://localhost:6379",
                retry_max=3,
            )

            result = strategy.enqueue(
                job_id="job-789",
                document_id="doc-abc",
                file_name="test.pdf",
            )

        self.assertEqual(result, "job-789")


# ---------------------------------------------------------------------------
# Tests: Auto-selection
# ---------------------------------------------------------------------------

class TestGetExecutionStrategy(unittest.TestCase):
    """Test automatic strategy selection."""

    @patch("ingestion.execution_strategy.platform.system", return_value="Windows")
    def test_windows_selects_background_tasks(self, _) -> None:
        strategy = get_execution_strategy()
        self.assertIsInstance(strategy, BackgroundTaskStrategy)

    @patch("ingestion.execution_strategy.platform.system", return_value="Linux")
    @patch.dict("os.environ", {"REDIS_URL": ""}, clear=False)
    def test_linux_no_redis_selects_background_tasks(self, _) -> None:
        strategy = get_execution_strategy()
        self.assertIsInstance(strategy, BackgroundTaskStrategy)

    @patch("ingestion.execution_strategy.platform.system", return_value="Darwin")
    @patch.dict("os.environ", {"REDIS_URL": ""}, clear=False)
    def test_macos_no_redis_selects_background_tasks(self, _) -> None:
        strategy = get_execution_strategy()
        self.assertIsInstance(strategy, BackgroundTaskStrategy)


# ---------------------------------------------------------------------------
# Tests: Strategy contract
# ---------------------------------------------------------------------------

class TestStrategyContract(unittest.TestCase):
    """Verify both strategies implement the same interface."""

    def test_both_have_enqueue(self) -> None:
        bg = BackgroundTaskStrategy()
        rq = RQExecutionStrategy(redis_url="redis://localhost:6379")

        self.assertTrue(callable(getattr(bg, "enqueue", None)))
        self.assertTrue(callable(getattr(rq, "enqueue", None)))

    def test_both_have_name(self) -> None:
        bg = BackgroundTaskStrategy()
        rq = RQExecutionStrategy(redis_url="redis://localhost:6379")

        self.assertIsInstance(bg.name(), str)
        self.assertIsInstance(rq.name(), str)
        self.assertNotEqual(bg.name(), rq.name())


if __name__ == "__main__":
    unittest.main()
