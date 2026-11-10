"""Local end-to-end checks; no cloud connection and no outbound network."""
import io
import os
import sys
import zipfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src" / "functions" / "src"))

import config  # noqa: E402
import events  # noqa: E402
import fetcher  # noqa: E402
import index  # noqa: E402
import observability  # noqa: E402
import storage  # noqa: E402

FIXED = datetime(2026, 11, 9, 6, 59, 0, tzinfo=timezone.utc)


class FakeClient:
    def __init__(self):
        self.calls = []

    def put_object(self, bucket, key, body, content_type=None):
        self.calls.append((bucket, key, body, content_type))
        return type("Resp", (), {"status": 200})()


class LocalChecks(unittest.TestCase):
    def test_config_defaults(self):
        cfg = config.load_config({})
        self.assertEqual(cfg.target_url, "https://www.example.com")
        self.assertEqual(cfg.result_prefix, "snapshots")

    def test_config_env_override_and_blanks(self):
        cfg = config.load_config({"TARGET_URL": "https://example.org/a", "LOG_LEVEL": "  "})
        self.assertEqual(cfg.target_url, "https://example.org/a")
        self.assertEqual(cfg.log_level, "INFO")

    def test_event_kind_timer(self):
        self.assertEqual(events.event_kind({"trigger_type": "TIMER"}), "TIMER")
        self.assertEqual(events.event_kind({"schedule_time": "2026-11-09T06:59:00Z"}), "TIMER")

    def test_event_kind_manual_and_apig(self):
        self.assertEqual(events.event_kind({}), "MANUAL")
        self.assertEqual(events.event_kind({"httpMethod": "POST"}), "APIG")

    def test_target_override_from_event(self):
        self.assertEqual(events.target_override({"target_url": "https://a.example"}), "https://a.example")

    def test_target_override_from_json_body(self):
        self.assertEqual(events.target_override({"body": '{"url":"https://b.example"}'}), "https://b.example")

    def test_target_override_invalid_body(self):
        self.assertIsNone(events.target_override({"body": "not-json"}))

    def test_trace_id_from_headers(self):
        self.assertEqual(events.trace_id({"headers": {"X-Trace-Id": "abc-123"}}), "abc-123")

    def test_trace_id_default(self):
        self.assertEqual(events.trace_id({}), "local-invocation")

    def test_fetch_uses_injected_opener(self):
        seen = {}

        def opener(url, timeout):
            seen["url"] = url
            return "<html>ok</html>", 200

        body, status = fetcher.fetch("https://ignored", opener=opener)
        self.assertEqual(body, "<html>ok</html>")
        self.assertEqual(status, 200)
        self.assertEqual(seen["url"], "https://ignored")

    def test_fetch_stdlib_fallback_is_present(self):
        self.assertTrue(callable(fetcher._via_stdlib))

    def test_result_key_shape(self):
        key = storage.result_key("snapshots", "https://www.example.com", now=FIXED)
        self.assertTrue(key.startswith("snapshots/2026/11/09/065900-"))
        self.assertTrue(key.endswith(".html"))

    def test_result_key_is_url_sensitive(self):
        a = storage.result_key("snapshots", "https://a.example", now=FIXED)
        b = storage.result_key("snapshots", "https://b.example", now=FIXED)
        self.assertNotEqual(a, b)

    def test_result_key_custom_prefix(self):
        key = storage.result_key(" custom/path ", "https://a.example", now=FIXED)
        self.assertTrue(key.startswith("custom/path/"))

    def test_put_snapshot_uses_put_content_when_available(self):
        class ContentClient:
            def __init__(self):
                self.args = None

            def putContent(self, bucket, key, content=None, contentType=None):
                self.args = (bucket, key, content, contentType)
                return type("Resp", (), {"status": 200})()

        client = ContentClient()
        status = storage.put_snapshot(client, "bucket", "key", "<p>x</p>")
        self.assertEqual(status, 200)
        self.assertEqual(client.args[1], "key")

    def test_logger_emits_json_line(self):
        buffer = []
        log = observability.create_logger("svc", trace="t-1", sink=buffer.append)
        log("INFO", "hello", key="k")
        self.assertIn('"message": "hello"', buffer[0])
        self.assertIn('"trace_id": "t-1"', buffer[0])

    def test_logger_respects_level(self):
        buffer = []
        log = observability.create_logger("svc", level="ERROR", sink=buffer.append)
        log("INFO", "hidden")
        self.assertEqual(buffer, [])

    def test_handler_name_matches_iac_contract(self):
        self.assertEqual(index.HANDLER_NAME, "index.handler")

    def _deps(self, client=None, body="<html>hello</html>", status=200):
        client = client or FakeClient()
        logs = []
        return {
            "config": config.load_config({"OBS_BUCKET": "test-bucket", "TARGET_URL": "https://www.example.com"}),
            "client_factory": lambda region, endpoint: client,
            "fetch": lambda url, timeout: (body, status),
            "clock": FIXED,
            "log_sink": logs.append,
        }, client, logs

    def test_handler_happy_path(self):
        deps, client, logs = self._deps()
        result = index.create_handler(deps)({"trigger_type": "TIMER"}, None)
        self.assertEqual(result["statusCode"], 200)
        body = result["body"]
        self.assertTrue(body["ok"])
        self.assertEqual(body["trigger"], "TIMER")
        self.assertEqual(body["http_status"], 200)
        self.assertEqual(body["bucket"], "test-bucket")
        self.assertTrue(body["key"].startswith("snapshots/2026/11/09/065900-"))
        self.assertEqual(len(client.calls), 1)
        self.assertEqual(client.calls[0][2], "<html>hello</html>")
        self.assertEqual(len(logs), 2)

    def test_handler_manual_invocation(self):
        deps, client, _ = self._deps()
        result = index.create_handler(deps)({}, None)
        self.assertEqual(result["body"]["trigger"], "MANUAL")

    def test_handler_target_override(self):
        deps, client, _ = self._deps()
        result = index.create_handler(deps)({"target_url": "https://override.example"}, None)
        self.assertEqual(result["body"]["target"], "https://override.example")

    def test_handler_fetch_failure_is_structured(self):
        deps, client, logs = self._deps()

        def failing(url, timeout):
            raise OSError("unreachable")

        deps["fetch"] = failing
        result = index.create_handler(deps)({"trigger_type": "TIMER"}, None)
        self.assertEqual(result["statusCode"], 502)
        self.assertFalse(result["body"]["ok"])
        self.assertEqual(result["body"]["error"], "fetch_failed")
        self.assertEqual(len(client.calls), 0)
        self.assertTrue(any("fetch failed" in line for line in logs))

    def test_handler_sha256_is_stable(self):
        deps, _, _ = self._deps()
        body = index.create_handler(deps)({}, None)["body"]
        self.assertEqual(len(body["sha256"]), 64)
        self.assertEqual(body["bytes"], len("<html>hello</html>"))

    def test_module_handler_is_callable(self):
        self.assertTrue(callable(index.handler))

    def test_deployment_archive_contains_sources(self):
        archive = ROOT / "build" / "function.zip"
        if not archive.exists():
            self.skipTest("deployment archive not built yet")
        with zipfile.ZipFile(archive) as zf:
            names = set(zf.namelist())
        for expected in ("index.py", "config.py", "events.py", "fetcher.py",
                         "storage.py", "observability.py", "requirements.txt"):
            self.assertIn(expected, names)

    def test_deployment_archive_is_single_package(self):
        archive = ROOT / "build" / "function.zip"
        if not archive.exists():
            self.skipTest("deployment archive not built yet")
        with zipfile.ZipFile(archive) as zf:
            names = zf.namelist()
        self.assertTrue(any(n.startswith("requests/") for n in names) or
                        any(n == "requests.py" for n in names),
                        "third-party library should be bundled into the same archive")


def main():
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(LocalChecks)
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=1).run(suite)
    for line in stream.getvalue().splitlines():
        if line.strip():
            print("  " + line)
    passed = result.testsRun - len(result.failures) - len(result.errors)
    print("=== Summary: %d passed, %d failed ===" % (
        passed, len(result.failures) + len(result.errors)))
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
