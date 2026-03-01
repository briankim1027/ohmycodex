import unittest
from datetime import datetime, timezone

from threads_obsidian.markdown import build_date_folder_name, build_filename, generate_title
from threads_obsidian.models import Post


class TestMarkdownLogic(unittest.TestCase):
    def test_generate_title_truncates_first_line_to_80(self):
        line = "a" * 120
        title = generate_title(f"{line}\nsecond line")
        self.assertEqual(title, "a" * 80)

    def test_generate_title_untitled_for_empty_body(self):
        self.assertEqual(generate_title("\n   \n"), "Untitled")

    def test_filename_and_date_folder_use_kst_created_at_date(self):
        created_at = datetime(2026, 3, 1, 15, 30, tzinfo=timezone.utc)  # 2026-03-02 00:30 KST
        post = Post(
            author_id="author01",
            post_id="post77",
            created_at=created_at,
            text="hello",
            post_url="https://example.com",
        )

        self.assertEqual(build_date_folder_name(created_at), "2026-03-02")
        self.assertEqual(build_filename(post), "2026-03-02_author01_post77.md")


if __name__ == "__main__":
    unittest.main()
