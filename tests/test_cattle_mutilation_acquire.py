import csv
import hashlib
import json
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import cattle_mutilation_acquire as acquisition
from scripts.cattle_mutilation_acquire import (
    AUDIT_SCHEMA_VERSION,
    CACHE_SCHEMA_VERSION,
    PRIVATE_CACHE_RIGHTS_POLICY,
    CropSourceAcquisitionError,
    HttpResponse,
    SystemTrustStoreError,
    UnsafeNetworkTargetError,
    acquire_crop_sources,
    enumerate_crop_source_targets,
)


FIXED_TIME = datetime(2026, 8, 1, 12, 34, 56, tzinfo=timezone.utc)


def test_enumerates_all_unique_urls_across_collections_and_aggregates_lineage(tmp_path):
    crop_zip = _write_crop_zip(
        tmp_path,
        {
            "source_assertions": [
                {
                    "source_record_url": " https://example.test/a ",
                    "source_name": "Archive A",
                    "formation_id": "cc_2",
                    "assertion_id": "a_2",
                    "rights_scope": "metadata_only",
                },
                {
                    "source_record_url": "https://example.test/a",
                    "source_name": "Archive A",
                    "formation_id": "cc_1",
                    "assertion_id": "a_1",
                    "rights_scope": "metadata_only",
                },
                {"source_record_url": None, "formation_id": "cc_none"},
            ],
            "image_links": [
                {
                    "source_record_url": "https://example.test/a",
                    "source_name": "Image contributor",
                    "formation_id": "cc_1",
                    "assertion_id": "a_img",
                    "rights_status": "contributor_rights_retained",
                }
            ],
            "future_collection": [
                {
                    "nested": {
                        "source_record_url": "https://example.test/b",
                        "source_name": "Future archive",
                        "formation_id": "cc_3",
                    }
                }
            ],
        },
    )

    targets, package_hash = enumerate_crop_source_targets(
        crop_zip, expected_zip_sha256=None
    )

    assert package_hash == _sha256(crop_zip.read_bytes())
    assert [target.url for target in targets] == [
        "https://example.test/a",
        "https://example.test/b",
    ]
    first = targets[0]
    assert first.occurrence_count == 3
    assert first.record_kinds == ("image_links", "source_assertions")
    assert first.source_names == ("Archive A", "Image contributor")
    assert first.formation_ids == ("cc_1", "cc_2")
    assert first.assertion_ids == ("a_1", "a_2", "a_img")
    assert first.rights_scopes == (
        "contributor_rights_retained",
        "metadata_only",
    )


def test_offline_discovery_is_default_and_audit_is_deterministic(tmp_path):
    crop_zip = _write_crop_zip(
        tmp_path,
        {
            "source_assertions": [
                {"source_record_url": "https://z.example.test/story", "formation_id": "cc_z"},
                {"source_record_url": "https://a.example.test/story", "formation_id": "cc_a"},
                {"source_record_url": "https://z.example.test/story", "formation_id": "cc_z"},
            ]
        },
    )
    cache = tmp_path / "private-cache"
    audit_one = tmp_path / "audit-one.csv"
    audit_two = tmp_path / "audit-two.csv"

    def forbidden_fetch(*_args):
        raise AssertionError("offline discovery must not use the network")

    first = acquire_crop_sources(
        crop_zip,
        audit_one,
        cache,
        expected_zip_sha256=None,
        archive_fallback=True,
        fetcher=forbidden_fetch,
    )
    second = acquire_crop_sources(
        crop_zip,
        audit_two,
        cache,
        expected_zip_sha256=None,
        archive_fallback=True,
        fetcher=forbidden_fetch,
    )

    assert audit_one.read_bytes() == audit_two.read_bytes()
    rows = _read_csv(audit_one)
    assert [row["source_record_url"] for row in rows] == [
        "https://a.example.test/story",
        "https://z.example.test/story",
    ]
    assert {row["acquisition_status"] for row in rows} == {"not_attempted_offline"}
    assert {row["coverage_status"] for row in rows} == {"coverage_gap"}
    assert rows[1]["occurrence_count"] == "2"
    assert first["network_enabled"] is False
    assert first["archive_fallback_enabled"] is False
    assert first["http_request_count"] == 0
    assert first["coverage_gap_count"] == 2
    assert second["status_counts"] == {"not_attempted_offline": 2}


def test_live_success_writes_private_content_addressed_object_and_metadata(tmp_path):
    source_url = "https://source.example.test/case-1"
    crop_zip = _write_crop_zip(
        tmp_path,
        {
            "source_assertions": [
                {
                    "source_record_url": source_url,
                    "source_name": "Test archive",
                    "formation_id": "cc_case_1",
                    "assertion_id": "a_case_1",
                    "rights_scope": "link_and_short_factual_extract_only",
                }
            ]
        },
    )
    body = b"<html><body>Source narrative</body></html>"
    calls = []

    def fetcher(url, timeout_seconds, user_agent, max_content_bytes):
        calls.append((url, timeout_seconds, user_agent, max_content_bytes))
        return HttpResponse(
            200,
            body,
            url,
            {"Content-Type": "Text/HTML; Charset=Windows-1252"},
        )

    audit = tmp_path / "access.csv"
    cache = tmp_path / "private-cache"
    summary = acquire_crop_sources(
        crop_zip,
        audit,
        cache,
        expected_zip_sha256=None,
        network=True,
        fetcher=fetcher,
        now_fn=lambda: FIXED_TIME,
        rate_limit_seconds=0,
    )

    digest = _sha256(body)
    rows = _read_csv(audit)
    assert len(calls) == 1
    assert rows[0]["acquisition_status"] == "live_success"
    assert rows[0]["coverage_status"] == "content_acquired"
    assert rows[0]["content_sha256"] == digest
    assert rows[0]["content_bytes"] == str(len(body))
    assert rows[0]["content_type"] == "text/html"
    assert rows[0]["content_charset"] == "windows-1252"
    assert rows[0]["retrieved_at_utc"] == "2026-08-01T12:34:56Z"
    assert rows[0]["cache_object_path"] == f"objects/{digest[:2]}/{digest}.bin"
    assert (cache / "objects" / digest[:2] / f"{digest}.bin").read_bytes() == body

    metadata_path = cache / Path(rows[0]["cache_metadata_path"])
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["schema_version"] == CACHE_SCHEMA_VERSION
    assert metadata["source_record_url"] == source_url
    assert metadata["content_type"] == "text/html"
    assert metadata["content_charset"] == "windows-1252"
    assert metadata["rights"] == {
        "cache_policy": PRIVATE_CACHE_RIGHTS_POLICY,
        "input_rights_scopes": ["link_and_short_factual_extract_only"],
    }
    assert metadata["archive_provenance"] is None
    assert metadata["source_context"]["formation_ids"] == ["cc_case_1"]
    assert summary["content_acquired_count"] == 1
    assert summary["coverage_gap_count"] == 0


def test_archive_fallback_records_cdx_and_snapshot_provenance(tmp_path):
    source_url = "https://blocked.example.test/case"
    crop_zip = _write_crop_zip(
        tmp_path,
        {"source_assertions": [{"source_record_url": source_url, "formation_id": "cc_a"}]},
    )
    timestamp = "20210102030405"
    archived_body = b"archived factual source page"
    calls = []
    sleeps = []

    def fetcher(url, _timeout, _agent, _max_bytes):
        calls.append(url)
        if url == source_url:
            return HttpResponse(404, b"missing", url)
        if "/cdx/search/cdx?" in url:
            payload = [
                ["timestamp", "original", "statuscode", "digest"],
                [timestamp, source_url, "200", "ARCHIVEDIGEST"],
            ]
            return HttpResponse(200, json.dumps(payload).encode("utf-8"), url)
        expected_snapshot = f"https://web.archive.org/web/{timestamp}id_/{source_url}"
        assert url == expected_snapshot
        return HttpResponse(200, archived_body, url)

    audit = tmp_path / "archive-audit.csv"
    cache = tmp_path / "private-cache"
    acquire_crop_sources(
        crop_zip,
        audit,
        cache,
        expected_zip_sha256=None,
        network=True,
        archive_fallback=True,
        fetcher=fetcher,
        sleep_fn=sleeps.append,
        rate_limit_seconds=0.25,
        now_fn=lambda: FIXED_TIME,
    )

    row = _read_csv(audit)[0]
    assert len(calls) == 3
    assert sleeps == [0.25, 0.25]
    assert row["acquisition_status"] == "archive_success"
    assert row["coverage_status"] == "content_acquired"
    assert row["live_http_status"] == "404"
    assert row["archive_cdx_http_status"] == "200"
    assert row["archive_snapshot_http_status"] == "200"
    assert row["archive_timestamp"] == timestamp
    assert row["archive_snapshot_url"] == calls[-1]
    assert row["content_sha256"] == _sha256(archived_body)

    metadata = json.loads(
        (cache / Path(row["cache_metadata_path"])).read_text(encoding="utf-8")
    )
    assert metadata["archive_provenance"] == {
        "cdx_http_status": "200",
        "snapshot_http_status": "200",
        "snapshot_timestamp": timestamp,
        "snapshot_url": calls[-1],
    }


@pytest.mark.parametrize("blocked_status", [401, 403, 407, 429, 451])
def test_blocked_status_never_uses_archive_fallback(tmp_path, blocked_status):
    source_url = "https://restricted.example.test/case"
    crop_zip = _write_crop_zip(
        tmp_path,
        {"source_assertions": [{"source_record_url": source_url}]},
    )
    calls = []

    def fetcher(url, _timeout, _agent, _max_bytes):
        calls.append(url)
        assert url == source_url
        return HttpResponse(blocked_status, b"restricted", url)

    audit = tmp_path / "blocked-audit.csv"
    summary = acquire_crop_sources(
        crop_zip,
        audit,
        tmp_path / "private-cache",
        expected_zip_sha256=None,
        network=True,
        archive_fallback=True,
        fetcher=fetcher,
        rate_limit_seconds=0,
        now_fn=lambda: FIXED_TIME,
    )

    row = _read_csv(audit)[0]
    assert calls == [source_url]
    assert row["acquisition_status"] == "blocked"
    assert row["coverage_status"] == "coverage_gap"
    assert row["archive_cdx_http_status"] == ""
    assert row["error_code"] == (
        f"live_http_{blocked_status};archive_skipped_not_permitted"
    )
    assert summary["http_request_count"] == 1


def test_inaccessible_source_is_a_coverage_gap_not_negative_evidence(tmp_path):
    source_url = "https://missing.example.test/case"
    crop_zip = _write_crop_zip(
        tmp_path,
        {"source_assertions": [{"source_record_url": source_url}]},
    )

    def fetcher(url, _timeout, _agent, _max_bytes):
        if url == source_url:
            raise TimeoutError("unstable platform-specific details are not persisted")
        assert "/cdx/search/cdx?" in url
        return HttpResponse(200, b'[["timestamp","original","statuscode","digest"]]', url)

    audit = tmp_path / "missing-audit.csv"
    cache = tmp_path / "private-cache"
    summary = acquire_crop_sources(
        crop_zip,
        audit,
        cache,
        expected_zip_sha256=None,
        network=True,
        archive_fallback=True,
        fetcher=fetcher,
        rate_limit_seconds=0,
        now_fn=lambda: FIXED_TIME,
    )

    row = _read_csv(audit)[0]
    assert row["acquisition_status"] == "unavailable"
    assert row["coverage_status"] == "coverage_gap"
    assert row["content_sha256"] == ""
    assert row["error_code"] == "live_timeout;archive_no_snapshot"
    assert summary["content_acquired_count"] == 0
    assert summary["coverage_gap_count"] == 1
    metadata = json.loads(
        (cache / Path(row["cache_metadata_path"])).read_text(encoding="utf-8")
    )
    assert metadata["coverage_status"] == "coverage_gap"
    assert metadata["content_sha256"] == ""


def test_verified_cache_resumes_without_network_and_preserves_audit_bytes(tmp_path):
    source_url = "https://resume.example.test/case"
    crop_zip = _write_crop_zip(
        tmp_path,
        {"source_assertions": [{"source_record_url": source_url}]},
    )
    cache = tmp_path / "private-cache"
    first_audit = tmp_path / "first.csv"
    second_audit = tmp_path / "second.csv"

    def first_fetcher(url, _timeout, _agent, _max_bytes):
        return HttpResponse(200, b"stable content", url)

    acquire_crop_sources(
        crop_zip,
        first_audit,
        cache,
        expected_zip_sha256=None,
        network=True,
        fetcher=first_fetcher,
        rate_limit_seconds=0,
        now_fn=lambda: FIXED_TIME,
    )

    def forbidden_fetcher(*_args):
        raise AssertionError("a verified content-addressed cache entry must be reused")

    summary = acquire_crop_sources(
        crop_zip,
        second_audit,
        cache,
        expected_zip_sha256=None,
        network=True,
        archive_fallback=True,
        fetcher=forbidden_fetcher,
        rate_limit_seconds=0,
        now_fn=lambda: pytest.fail("the clock is not needed when cache metadata is reused"),
    )

    assert first_audit.read_bytes() == second_audit.read_bytes()
    assert summary["cache_reused_count"] == 1
    assert summary["network_attempted_url_count"] == 0
    assert summary["http_request_count"] == 0
    assert summary["status_counts"] == {"live_success": 1}


def test_completed_failure_resumes_without_retry_until_explicitly_requested(tmp_path):
    source_url = "https://resume-failure.example.test/case"
    crop_zip = _write_crop_zip(
        tmp_path,
        {"source_assertions": [{"source_record_url": source_url}]},
    )
    cache = tmp_path / "private-cache"
    first_audit = tmp_path / "first.csv"
    resumed_audit = tmp_path / "resumed.csv"
    retry_audit = tmp_path / "retry.csv"

    def failed_fetcher(*_args):
        raise TimeoutError("first campaign attempt")

    acquire_crop_sources(
        crop_zip,
        first_audit,
        cache,
        expected_zip_sha256=None,
        network=True,
        fetcher=failed_fetcher,
        rate_limit_seconds=0,
        now_fn=lambda: FIXED_TIME,
    )

    def forbidden_fetcher(*_args):
        raise AssertionError("completed failures must be reused during ordinary resume")

    resumed = acquire_crop_sources(
        crop_zip,
        resumed_audit,
        cache,
        expected_zip_sha256=None,
        network=True,
        fetcher=forbidden_fetcher,
        rate_limit_seconds=0,
        now_fn=lambda: pytest.fail("reusing a failure must not replace its timestamp"),
    )

    retry_calls = []

    def successful_retry(url, _timeout, _agent, _max_bytes):
        retry_calls.append(url)
        return HttpResponse(200, b"available now", url)

    retried = acquire_crop_sources(
        crop_zip,
        retry_audit,
        cache,
        expected_zip_sha256=None,
        network=True,
        retry_failures=True,
        fetcher=successful_retry,
        rate_limit_seconds=0,
        now_fn=lambda: FIXED_TIME,
    )

    assert first_audit.read_bytes() == resumed_audit.read_bytes()
    assert resumed["failed_attempt_reused_count"] == 1
    assert resumed["network_attempted_url_count"] == 0
    assert resumed["retry_failures_enabled"] is False
    assert retry_calls == [source_url]
    assert retried["failed_attempt_reused_count"] == 0
    assert retried["network_attempted_url_count"] == 1
    assert retried["retry_failures_enabled"] is True
    assert _read_csv(retry_audit)[0]["acquisition_status"] == "live_success"


def test_progress_callback_reports_periodic_and_final_dispositions(tmp_path):
    urls = [f"https://example.test/{index}" for index in range(3)]
    crop_zip = _write_crop_zip(
        tmp_path,
        {"source_assertions": [{"source_record_url": url} for url in urls]},
    )
    progress = []

    acquire_crop_sources(
        crop_zip,
        tmp_path / "audit.csv",
        tmp_path / "private-cache",
        expected_zip_sha256=None,
        progress_every=2,
        progress_fn=lambda completed, total, target, status: progress.append(
            (completed, total, target.url, status)
        ),
    )

    assert progress == [
        (2, 3, urls[1], "not_attempted_offline"),
        (3, 3, urls[2], "not_attempted_offline"),
    ]


def test_parallel_workers_preserve_deterministic_order_and_shared_cache_object(
    tmp_path,
):
    urls = [
        "https://z.example.test/story",
        "https://a.example.test/story",
        "https://m.example.test/story",
    ]
    crop_zip = _write_crop_zip(
        tmp_path,
        {"source_assertions": [{"source_record_url": url} for url in urls]},
    )
    shared_body = b"same content returned by concurrent sources"

    def run_once(name):
        barrier = threading.Barrier(3)

        def fetcher(url, _timeout, _agent, _max_bytes):
            barrier.wait(timeout=5)
            return HttpResponse(
                200,
                shared_body,
                url,
                {"Content-Type": "text/plain; charset=UTF-8"},
            )

        audit = tmp_path / f"{name}.csv"
        cache = tmp_path / f"{name}-cache"
        summary = acquire_crop_sources(
            crop_zip,
            audit,
            cache,
            expected_zip_sha256=None,
            network=True,
            workers=3,
            fetcher=fetcher,
            rate_limit_seconds=0,
            now_fn=lambda: FIXED_TIME,
        )
        return audit, cache, summary

    first_audit, first_cache, first_summary = run_once("first")
    second_audit, second_cache, second_summary = run_once("second")

    assert first_audit.read_bytes() == second_audit.read_bytes()
    assert [row["source_record_url"] for row in _read_csv(first_audit)] == sorted(urls)
    assert first_summary["workers"] == second_summary["workers"] == 3
    assert first_summary["http_request_count"] == 3
    assert second_summary["http_request_count"] == 3
    digest = _sha256(shared_body)
    for cache in (first_cache, second_cache):
        assert (cache / "objects" / digest[:2] / f"{digest}.bin").read_bytes() == shared_body
        assert len(list((cache / "objects").rglob("*.bin"))) == 1
        assert list(cache.rglob("*.tmp")) == []


def test_parallel_workers_share_one_global_request_start_limiter(tmp_path):
    urls = [f"https://rate.example.test/{index}" for index in range(4)]
    crop_zip = _write_crop_zip(
        tmp_path,
        {"source_assertions": [{"source_record_url": url} for url in urls]},
    )
    sleeps = []

    summary = acquire_crop_sources(
        crop_zip,
        tmp_path / "rate.csv",
        tmp_path / "rate-cache",
        expected_zip_sha256=None,
        network=True,
        workers=4,
        fetcher=lambda url, _timeout, _agent, _max_bytes: HttpResponse(
            200, url.encode("utf-8"), url
        ),
        sleep_fn=sleeps.append,
        rate_limit_seconds=0.125,
        now_fn=lambda: FIXED_TIME,
    )

    assert sleeps == [0.125, 0.125, 0.125]
    assert summary["http_request_count"] == 4
    assert summary["workers"] == 4


@pytest.mark.parametrize("workers", [0, -1])
def test_workers_must_be_positive_before_any_output_is_created(tmp_path, workers):
    crop_zip = _write_crop_zip(tmp_path, {"source_assertions": []})
    audit = tmp_path / "invalid-workers.csv"
    cache = tmp_path / "invalid-workers-cache"

    with pytest.raises(CropSourceAcquisitionError, match="workers must be positive"):
        acquire_crop_sources(
            crop_zip,
            audit,
            cache,
            expected_zip_sha256=None,
            workers=workers,
        )

    assert not audit.exists()
    assert not cache.exists()


def test_invalid_or_private_url_is_never_requested(tmp_path):
    crop_zip = _write_crop_zip(
        tmp_path,
        {
            "source_assertions": [
                {"source_record_url": "file:///private/story.html"},
                {"source_record_url": "http://127.0.0.1/internal"},
            ]
        },
    )

    def forbidden_fetcher(*_args):
        raise AssertionError("invalid and private URLs must be rejected before retrieval")

    audit = tmp_path / "invalid.csv"
    summary = acquire_crop_sources(
        crop_zip,
        audit,
        tmp_path / "private-cache",
        expected_zip_sha256=None,
        network=True,
        fetcher=forbidden_fetcher,
        rate_limit_seconds=0,
        now_fn=lambda: FIXED_TIME,
    )

    rows = _read_csv(audit)
    assert {row["acquisition_status"] for row in rows} == {"invalid_url"}
    assert {row["coverage_status"] for row in rows} == {"coverage_gap"}
    assert {row["error_code"] for row in rows} == {
        "invalid_source_url",
        "blocked_private_source_url",
    }
    assert summary["http_request_count"] == 0


def test_stdlib_fetch_rejects_private_dns_before_opening_connection(monkeypatch):
    def private_resolution(*_args, **_kwargs):
        return [
            (
                acquisition.socket.AF_INET,
                acquisition.socket.SOCK_STREAM,
                6,
                "",
                ("10.1.2.3", 443),
            )
        ]

    monkeypatch.setattr(acquisition.socket, "getaddrinfo", private_resolution)
    monkeypatch.setattr(
        acquisition.urllib.request,
        "build_opener",
        lambda *_args: pytest.fail("unsafe DNS target reached the HTTP opener"),
    )

    with pytest.raises(
        UnsafeNetworkTargetError,
        match="blocked_private_resolved_source_address",
    ):
        acquisition._stdlib_fetch(
            "https://public-name.example.test/story",
            1.0,
            "test-agent",
            1024,
        )


def test_system_trust_context_requires_available_verified_truststore(monkeypatch):
    def unavailable(_name):
        raise ModuleNotFoundError("truststore")

    monkeypatch.setattr(acquisition.importlib, "import_module", unavailable)
    with pytest.raises(SystemTrustStoreError, match="^system_truststore_unavailable$"):
        acquisition._build_system_trust_context()

    insecure_context = type(
        "InsecureContext",
        (),
        {"verify_mode": acquisition.ssl.CERT_NONE, "check_hostname": False},
    )()
    fake_module = type(
        "FakeTruststore",
        (),
        {"SSLContext": staticmethod(lambda _protocol: insecure_context)},
    )()
    monkeypatch.setattr(
        acquisition.importlib,
        "import_module",
        lambda name: fake_module if name == "truststore" else pytest.fail(name),
    )
    with pytest.raises(
        SystemTrustStoreError,
        match="^system_truststore_verification_disabled$",
    ):
        acquisition._build_system_trust_context()


def test_stdlib_fetch_passes_explicit_verified_context_to_https_handler(monkeypatch):
    context = acquisition.ssl.create_default_context()
    captured = {}

    class FakeResponse:
        status = 200
        headers = {"Content-Type": "text/plain"}

        def read(self, _limit):
            return b"verified response"

        def geturl(self):
            return "https://public.example.test/story"

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    class FakeOpener:
        def open(self, _request, *, timeout):
            captured["timeout"] = timeout
            return FakeResponse()

    def fake_build_opener(*handlers):
        captured["handlers"] = handlers
        return FakeOpener()

    monkeypatch.setattr(acquisition, "_assert_public_network_target", lambda _url: None)
    monkeypatch.setattr(acquisition, "_build_system_trust_context", lambda: context)
    monkeypatch.setattr(acquisition.urllib.request, "build_opener", fake_build_opener)

    response = acquisition._stdlib_fetch(
        "https://public.example.test/story",
        3.0,
        "test-agent",
        1024,
    )

    https_handlers = [
        handler
        for handler in captured["handlers"]
        if isinstance(handler, acquisition.urllib.request.HTTPSHandler)
    ]
    assert len(https_handlers) == 1
    assert https_handlers[0]._context is context
    assert context.verify_mode == acquisition.ssl.CERT_REQUIRED
    assert context.check_hostname is True
    assert captured["timeout"] == 3.0
    assert response.body == b"verified response"


def test_redirect_handler_rejects_private_hop_before_connection():
    handler = acquisition._SafeRedirectHandler()
    request = acquisition.urllib.request.Request("https://public.example.test/story")

    with pytest.raises(UnsafeNetworkTargetError, match="blocked_private_source_url"):
        handler.redirect_request(
            request,
            None,
            302,
            "Found",
            {},
            "http://127.0.0.1/internal",
        )


def test_package_hash_mismatch_fails_closed(tmp_path):
    crop_zip = _write_crop_zip(tmp_path, {"source_assertions": []})

    with pytest.raises(CropSourceAcquisitionError, match="SHA-256 mismatch"):
        enumerate_crop_source_targets(crop_zip, expected_zip_sha256="0" * 64)


def _write_crop_zip(tmp_path: Path, export_overrides: dict) -> Path:
    export = {
        "schema_version": "crop-circle-timeline-export-v1.0.0",
        "events": [],
        "morphology_occurrences": [],
        "source_assertions": [],
        "image_links": [],
    }
    export.update(export_overrides)
    path = tmp_path / "crop-export.zip"
    payload = json.dumps(export, ensure_ascii=False, sort_keys=True).encode("utf-8")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("crop_circle_timeline_export_v1.json", payload)
    return path


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()
