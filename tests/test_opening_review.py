"""Offline regression tests for the EGX opening-price review guard."""
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import run_daily


class OpeningReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.signals = Path(self.tmp.name)
        self.now = datetime(2026, 10, 28, 11, 0, tzinfo=timezone.utc)
        self.cfg = {"market": {"timezone": "Africa/Cairo"}}
        self.report_path = self.signals / "latest.json"
        self.report = {
            "generated_at": self.now.isoformat(),
            "data_date": "2026-10-28",
            "picks": [{
                "signal": "BUY", "code": "TEST", "name": "Test",
                "entry_low": 9, "entry_high": 11, "stop": 8, "t1": 13,
            }],
        }
        self.report_path.write_text(json.dumps(self.report), encoding="utf-8")
        self.state = {}
        self.state_patch = patch.multiple(
            run_daily.C,
            SIGNALS=self.signals,
            load_state=lambda: dict(self.state),
            save_state=self.save_state,
        )
        self.state_patch.start()
        self.addCleanup(self.state_patch.stop)
        self.env_patch = patch.dict(os.environ, {
            "TELEGRAM_BOT_TOKEN": "test-token", "TELEGRAM_CHAT_ID": "test-chat"
        })
        self.env_patch.start()
        self.addCleanup(self.env_patch.stop)

    def save_state(self, state):
        self.state.clear()
        self.state.update(state)

    @patch("run_daily.fetch_live_quotes")
    @patch("run_daily.send_message")
    def test_stale_report_is_rejected_without_quote_or_send(self, send, quotes):
        self.report["generated_at"] = "2026-10-27T08:00:00+00:00"
        self.report_path.write_text(json.dumps(self.report), encoding="utf-8")
        result = run_daily.opening_review(self.cfg, self.now)
        self.assertEqual(result["status"], "not_sent")
        quotes.assert_not_called()
        send.assert_not_called()

    @patch("run_daily.fetch_live_quotes")
    @patch("run_daily.send_message")
    def test_attempt_guard_prevents_duplicate_send(self, send, quotes):
        self.state["opening_review_attempt_date"] = self.now.date().isoformat()
        result = run_daily.opening_review(self.cfg, self.now)
        self.assertEqual(result["status"], "skipped")
        quotes.assert_not_called()
        send.assert_not_called()

    @patch("run_daily.fetch_live_quotes", return_value={
        "ok": True, "retrieved_at": "2026-10-28T11:00:00+00:00",
        "quotes": [{"code": "TEST", "price": 10, "change_percent": 0, "as_of": "source-time"}],
    })
    @patch("run_daily.send_message")
    def test_attempt_is_persisted_before_telegram_send(self, send, quotes):
        def inspect_reserved_state(*args, **kwargs):
            self.assertEqual(self.state.get("opening_review_attempt_date"), self.now.date().isoformat())
            return 1
        send.side_effect = inspect_reserved_state
        result = run_daily.opening_review(self.cfg, self.now)
        self.assertEqual(result["status"], "sent")
        self.assertEqual(self.state.get("last_opening_review_date"), self.now.date().isoformat())
        send.assert_called_once()


if __name__ == "__main__":
    unittest.main()
