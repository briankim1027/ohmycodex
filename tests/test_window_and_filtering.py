import unittest
from datetime import datetime, timezone

from threads_obsidian.collector import filter_posts_by_window
from threads_obsidian.models import CollectWindow, Post
from threads_obsidian.state_store import CollectorState, resolve_collect_window


class TestWindowAndFiltering(unittest.TestCase):
    def test_resolve_collect_window_first_run_uses_kst_start_of_day(self):
        now = datetime(2026, 3, 1, 3, 45, tzinfo=timezone.utc)  # 12:45 KST
        state = CollectorState(last_success_at=None)

        window = resolve_collect_window(now_utc=now, state=state)

        self.assertEqual(window.start, datetime(2026, 2, 28, 15, 0, tzinfo=timezone.utc))
        self.assertEqual(window.end, now)

    def test_filter_posts_by_window_inclusive_bounds(self):
        window = CollectWindow(
            start=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
            end=datetime(2026, 3, 1, 1, 0, tzinfo=timezone.utc),
        )
        in_start = Post("a", "1", datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc), "", "")
        in_middle = Post("a", "2", datetime(2026, 3, 1, 0, 30, tzinfo=timezone.utc), "", "")
        in_end = Post("a", "3", datetime(2026, 3, 1, 1, 0, tzinfo=timezone.utc), "", "")
        out = Post("a", "4", datetime(2026, 3, 1, 1, 1, tzinfo=timezone.utc), "", "")

        filtered = filter_posts_by_window([in_start, in_middle, in_end, out], window)
        self.assertEqual([p.post_id for p in filtered], ["1", "2", "3"])


if __name__ == "__main__":
    unittest.main()
