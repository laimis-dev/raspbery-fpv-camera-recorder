import signal
from threading import Event
import unittest

from recorder.signals import handle_shutdown_signals


class SignalTests(unittest.TestCase):
    def test_signal_handlers_are_restored_after_failure(self):
        original_signal_handlers = {
            signal_number: signal.getsignal(signal_number)
            for signal_number in (signal.SIGINT, signal.SIGTERM)
        }
        stop_requested_event = Event()
        with self.assertRaisesRegex(RuntimeError, "failed"):
            with handle_shutdown_signals(stop_requested_event):
                signal.raise_signal(signal.SIGTERM)
                self.assertTrue(stop_requested_event.is_set())
                raise RuntimeError("failed")
        self.assertEqual(
            {signal_number: signal.getsignal(signal_number) for signal_number in original_signal_handlers},
            original_signal_handlers,
        )
