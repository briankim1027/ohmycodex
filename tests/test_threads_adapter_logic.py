import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from threads_obsidian.threads_client import HttpThreadsAdapter, HttpThreadsAdapterConfig, ThreadsAPIError
from threads_obsidian.time_utils import parse_iso_datetime


def _build_adapter() -> HttpThreadsAdapter:
    return HttpThreadsAdapter(
        HttpThreadsAdapterConfig(
            access_token="token",
            base_url="https://graph.threads.net",
            profile_lookup_endpoint="/v1.0/profile_lookup",
            user_threads_endpoint_template="/v1.0/{threads_user_id}/threads",
            posts_fields="id,text,timestamp,permalink,username",
            posts_limit=25,
        )
    )


class TestThreadsAdapterLogic(unittest.TestCase):
    def test_build_urls_for_official_endpoints(self):
        adapter = _build_adapter()
        self.assertEqual(
            adapter.build_profile_lookup_url(),
            "https://graph.threads.net/v1.0/profile_lookup",
        )
        self.assertEqual(
            adapter.build_user_threads_url("12345"),
            "https://graph.threads.net/v1.0/12345/threads",
        )

    def test_build_threads_query_params_supports_fields_since_until_limit(self):
        since = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
        until = datetime(2026, 3, 1, 1, 0, tzinfo=timezone.utc)
        params = HttpThreadsAdapter.build_threads_query_params(
            fields="id,text,timestamp",
            limit=10,
            since=since,
            until=until,
        )
        self.assertEqual(params["fields"], "id,text,timestamp")
        self.assertEqual(params["limit"], "10")
        self.assertEqual(params["since"], since.isoformat())
        self.assertEqual(params["until"], until.isoformat())

    def test_resolve_user_id_skips_lookup_for_numeric_input(self):
        adapter = _build_adapter()
        with patch.object(adapter, "_request_with_retry") as mock_request:
            resolved = adapter.resolve_threads_user_id("123456789")
        self.assertEqual(resolved, "123456789")
        mock_request.assert_not_called()

    def test_extract_user_id_from_profile_lookup_payload_shapes(self):
        self.assertEqual(
            HttpThreadsAdapter.extract_user_id_from_profile_lookup({"id": "111"}, username="u"),
            "111",
        )
        self.assertEqual(
            HttpThreadsAdapter.extract_user_id_from_profile_lookup({"data": {"id": "222"}}, username="u"),
            "222",
        )
        self.assertEqual(
            HttpThreadsAdapter.extract_user_id_from_profile_lookup({"data": [{"threads_user_id": "333"}]}, username="u"),
            "333",
        )

    def test_extract_user_id_from_profile_lookup_permission_gated_error(self):
        with self.assertRaises(ThreadsAPIError):
            HttpThreadsAdapter.extract_user_id_from_profile_lookup({"data": []}, username="private_user")

    def test_parse_iso_datetime_accepts_threads_offset_without_colon(self):
        dt = parse_iso_datetime("2026-03-01T12:34:56+0000")
        self.assertEqual(dt, datetime(2026, 3, 1, 12, 34, 56, tzinfo=timezone.utc))


if __name__ == "__main__":
    unittest.main()
