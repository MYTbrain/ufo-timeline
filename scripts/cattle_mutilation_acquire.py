"""Deterministic, rights-aware acquisition of Crop Circle Atlas source pages.

The module is intentionally usable both as a small standalone command and as a
library imported by ``cattle_mutilation_seed.py``.  Discovery is offline by
default.  Network access, including the Internet Archive fallback, must be
enabled explicitly by the caller.

Raw response bodies are written only to a caller-provided private,
content-addressed cache.  The public audit contains provenance and content
hashes, never third-party page content.  A failed or skipped acquisition is a
coverage gap; it is never evidence that a mutilation relationship is absent.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib
import ipaddress
import json
import os
import socket
import ssl
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping, Sequence


PINNED_CROP_ZIP_SHA256 = (
    "7F552F66A197B96C838475B5CAEAB7C78C1AEE5544C81D658A10335687CB2DF6"
)
EXPORT_MEMBER_NAME = "crop_circle_timeline_export_v1.json"
CACHE_SCHEMA_VERSION = "crop-source-private-cache-v1.0.0"
AUDIT_SCHEMA_VERSION = "crop-circle-source-access-audit-v1.0.0"
PRIVATE_CACHE_RIGHTS_POLICY = (
    "private_research_cache_not_for_redistribution_source_rights_retained"
)
DEFAULT_USER_AGENT = (
    "ufo-timeline-cattle-mutilation-research/1.0 "
    "(+https://github.com/MYTbrain/ufo-timeline)"
)
DEFAULT_MAX_CONTENT_BYTES = 10 * 1024 * 1024
SUCCESS_STATUSES = frozenset({"live_success", "archive_success"})
BLOCKED_HTTP_STATUSES = frozenset({401, 403, 407, 429, 451})

AUDIT_FIELDS = (
    "audit_schema_version",
    "source_record_url",
    "occurrence_count",
    "record_kinds",
    "source_names",
    "formation_ids",
    "assertion_ids",
    "input_rights_scopes",
    "cache_rights_policy",
    "acquisition_status",
    "coverage_status",
    "content_sha256",
    "content_bytes",
    "content_type",
    "content_charset",
    "retrieved_at_utc",
    "retrieval_url",
    "live_http_status",
    "archive_cdx_http_status",
    "archive_snapshot_http_status",
    "archive_timestamp",
    "archive_snapshot_url",
    "error_code",
    "source_zip_sha256",
    "cache_metadata_path",
    "cache_object_path",
)


class CropSourceAcquisitionError(RuntimeError):
    """Raised for an invalid package or acquisition configuration."""


class ContentTooLargeError(CropSourceAcquisitionError):
    """Raised before an oversized response can enter the private cache."""


class UnsafeNetworkTargetError(CropSourceAcquisitionError):
    """Raised before connecting to a non-public initial or redirect target."""


class SystemTrustStoreError(CropSourceAcquisitionError):
    """Raised when a verified native-system TLS context cannot be created."""


@dataclass(frozen=True)
class SourceTarget:
    """One unique source URL plus its complete packaged lineage."""

    url: str
    occurrence_count: int
    record_kinds: tuple[str, ...]
    source_names: tuple[str, ...]
    formation_ids: tuple[str, ...]
    assertion_ids: tuple[str, ...]
    rights_scopes: tuple[str, ...]


@dataclass(frozen=True)
class HttpResponse:
    """Small transport-neutral response used by the injectable fetcher."""

    status: int
    body: bytes
    final_url: str
    headers: Mapping[str, str] | None = None


Fetcher = Callable[[str, float, str, int], HttpResponse]
Clock = Callable[[], datetime]
ProgressFn = Callable[[int, int, SourceTarget, str], None]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def enumerate_crop_source_targets(
    crop_zip_path: Path | str,
    *,
    expected_zip_sha256: str | None = PINNED_CROP_ZIP_SHA256,
) -> tuple[list[SourceTarget], str]:
    """Return every unique non-empty ``source_record_url`` in the export.

    The search is recursive rather than limited to today's known collections,
    so a future compatible export cannot silently omit a newly nested source
    record URL.  Exact URL strings are stripped of surrounding whitespace and
    then deduplicated; they are not rewritten or semantically canonicalized.
    """

    crop_zip_path = Path(crop_zip_path)
    if not crop_zip_path.is_file():
        raise CropSourceAcquisitionError(f"Crop export ZIP not found: {crop_zip_path}")

    package_sha256 = sha256_file(crop_zip_path)
    if expected_zip_sha256 and package_sha256.lower() != expected_zip_sha256.lower():
        raise CropSourceAcquisitionError(
            "Crop export ZIP SHA-256 mismatch: "
            f"expected {expected_zip_sha256.upper()}, got {package_sha256.upper()}"
        )

    try:
        with zipfile.ZipFile(crop_zip_path) as archive:
            names = set(archive.namelist())
            if EXPORT_MEMBER_NAME not in names:
                raise CropSourceAcquisitionError(
                    f"Crop export ZIP is missing {EXPORT_MEMBER_NAME}"
                )
            export = json.loads(archive.read(EXPORT_MEMBER_NAME))
    except (zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CropSourceAcquisitionError(
            f"Invalid crop export ZIP or JSON: {type(exc).__name__}"
        ) from exc

    if not isinstance(export, dict):
        raise CropSourceAcquisitionError("Crop export root must be a JSON object")

    aggregates: dict[str, dict[str, Any]] = {}
    for record_kind in sorted(export):
        _collect_source_record_urls(export[record_kind], record_kind, aggregates)

    targets: list[SourceTarget] = []
    for url in sorted(aggregates):
        item = aggregates[url]
        targets.append(
            SourceTarget(
                url=url,
                occurrence_count=item["occurrence_count"],
                record_kinds=tuple(sorted(item["record_kinds"])),
                source_names=tuple(sorted(item["source_names"])),
                formation_ids=tuple(sorted(item["formation_ids"])),
                assertion_ids=tuple(sorted(item["assertion_ids"])),
                rights_scopes=tuple(sorted(item["rights_scopes"])),
            )
        )
    return targets, package_sha256


def acquire_crop_sources(
    crop_zip_path: Path | str,
    audit_csv_path: Path | str,
    private_cache_dir: Path | str,
    *,
    expected_zip_sha256: str | None = PINNED_CROP_ZIP_SHA256,
    network: bool = False,
    archive_fallback: bool = False,
    rate_limit_seconds: float = 0.5,
    timeout_seconds: float = 20.0,
    max_content_bytes: int = DEFAULT_MAX_CONTENT_BYTES,
    user_agent: str = DEFAULT_USER_AGENT,
    retry_failures: bool = False,
    workers: int = 1,
    progress_every: int = 100,
    progress_fn: ProgressFn | None = None,
    fetcher: Fetcher | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Clock | None = None,
) -> dict[str, Any]:
    """Discover or acquire every unique crop source URL and write an audit.

    Successful prior cache entries are verified by hashing their object bytes
    and reused without network access.  Completed failed attempts are also
    reused by default so an interrupted campaign can advance past persistent
    failures.  Set ``retry_failures=True`` to explicitly attempt them again.
    Set ``network=True`` explicitly for live retrieval and set
    ``archive_fallback=True`` as a separate opt-in for Wayback lookup.
    """

    if rate_limit_seconds < 0:
        raise CropSourceAcquisitionError("rate_limit_seconds must be non-negative")
    if timeout_seconds <= 0:
        raise CropSourceAcquisitionError("timeout_seconds must be positive")
    if max_content_bytes <= 0:
        raise CropSourceAcquisitionError("max_content_bytes must be positive")
    if workers <= 0:
        raise CropSourceAcquisitionError("workers must be positive")
    if progress_every <= 0:
        raise CropSourceAcquisitionError("progress_every must be positive")

    targets, package_sha256 = enumerate_crop_source_targets(
        crop_zip_path,
        expected_zip_sha256=expected_zip_sha256,
    )
    if fetcher is None and network:
        tls_context = _build_system_trust_context()

        def fetcher(
            url: str,
            request_timeout: float,
            request_user_agent: str,
            request_max_bytes: int,
        ) -> HttpResponse:
            return _stdlib_fetch(
                url,
                request_timeout,
                request_user_agent,
                request_max_bytes,
                ssl_context=tls_context,
            )
    elif fetcher is None:
        fetcher = _stdlib_fetch

    audit_csv_path = Path(audit_csv_path)
    private_cache_dir = Path(private_cache_dir)
    metadata_dir = private_cache_dir / "metadata"
    objects_dir = private_cache_dir / "objects"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    objects_dir.mkdir(parents=True, exist_ok=True)
    audit_csv_path.parent.mkdir(parents=True, exist_ok=True)

    if now_fn is None:
        now_fn = lambda: datetime.now(timezone.utc)

    request_count = 0
    request_start_lock = threading.Lock()
    cache_object_lock = threading.Lock()

    def request(url: str) -> HttpResponse:
        nonlocal request_count
        # The lock covers only request-start scheduling. Network I/O happens
        # after release, so at most ``workers`` requests may be in flight while
        # every start remains subject to one process-wide rate limiter.
        with request_start_lock:
            if request_count and rate_limit_seconds:
                sleep_fn(rate_limit_seconds)
            request_count += 1
        response = fetcher(url, timeout_seconds, user_agent, max_content_bytes)
        if not isinstance(response, HttpResponse):
            raise TypeError("fetcher must return HttpResponse")
        if len(response.body) > max_content_bytes:
            raise ContentTooLargeError("response_exceeded_max_content_bytes")
        return response

    audit_rows: list[dict[str, str | int]] = []
    cache_reused_count = 0
    failed_attempt_reused_count = 0
    network_attempted_count = 0
    total_targets = len(targets)

    def process_target(
        target: SourceTarget,
    ) -> tuple[SourceTarget, dict[str, Any], bool, bool, bool]:
        cached_metadata, cache_error = _load_verified_success_metadata(
            target.url, private_cache_dir
        )
        prior_metadata = _load_metadata(target.url, private_cache_dir)
        prior_failed_attempt = bool(
            prior_metadata
            and prior_metadata.get("acquisition_status") not in SUCCESS_STATUSES
            and prior_metadata.get("acquisition_status") != "not_attempted_offline"
        )
        if cached_metadata is not None:
            result = dict(cached_metadata)
            cache_reused = True
            failed_reused = False
            network_attempted = False
        elif prior_failed_attempt and not retry_failures:
            result = dict(prior_metadata or {})
            cache_reused = False
            failed_reused = True
            network_attempted = False
        elif not network:
            if prior_metadata and prior_metadata.get("acquisition_status") not in SUCCESS_STATUSES:
                result = dict(prior_metadata)
            else:
                result = _base_result(
                    target.url,
                    status="not_attempted_offline",
                    error_code=cache_error,
                )
            cache_reused = False
            failed_reused = False
            network_attempted = False
        else:
            result = _acquire_one(
                target,
                private_cache_dir=private_cache_dir,
                archive_fallback=archive_fallback,
                request=request,
                now_fn=now_fn,
                cache_object_lock=cache_object_lock,
                cache_error=cache_error,
                source_zip_sha256=package_sha256,
            )
            cache_reused = False
            failed_reused = False
            network_attempted = True

        return target, result, cache_reused, failed_reused, network_attempted

    def consume_results(
        processed_targets: Iterable[
            tuple[SourceTarget, dict[str, Any], bool, bool, bool]
        ],
    ) -> None:
        nonlocal cache_reused_count
        nonlocal failed_attempt_reused_count
        nonlocal network_attempted_count
        for target_index, processed in enumerate(processed_targets, 1):
            target, result, cache_reused, failed_reused, network_attempted = processed
            cache_reused_count += int(cache_reused)
            failed_attempt_reused_count += int(failed_reused)
            network_attempted_count += int(network_attempted)

            audit_rows.append(_audit_row(target, result, package_sha256))
            if progress_fn is not None and (
                target_index % progress_every == 0 or target_index == total_targets
            ):
                progress_fn(
                    target_index,
                    total_targets,
                    target,
                    str(result.get("acquisition_status", "unknown")),
                )

    if workers == 1:
        consume_results(map(process_target, targets))
    else:
        with ThreadPoolExecutor(
            max_workers=workers,
            thread_name_prefix="crop-source-acquire",
        ) as executor:
            # Executor.map runs concurrently but yields in input order. This
            # keeps audit rows and progress deterministic regardless of which
            # host responds first.
            consume_results(executor.map(process_target, targets))

    _write_audit_csv(audit_csv_path, audit_rows)

    status_counts: dict[str, int] = {}
    for row in audit_rows:
        status = str(row["acquisition_status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    coverage_gap_count = sum(
        1 for row in audit_rows if row["coverage_status"] == "coverage_gap"
    )
    return {
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        "source_zip_sha256": package_sha256,
        "unique_source_record_url_count": len(targets),
        "content_acquired_count": len(targets) - coverage_gap_count,
        "coverage_gap_count": coverage_gap_count,
        "cache_reused_count": cache_reused_count,
        "failed_attempt_reused_count": failed_attempt_reused_count,
        "network_attempted_url_count": network_attempted_count,
        "http_request_count": request_count,
        "network_enabled": network,
        "archive_fallback_enabled": archive_fallback and network,
        "retry_failures_enabled": retry_failures and network,
        "workers": workers,
        "status_counts": dict(sorted(status_counts.items())),
        "audit_csv": str(audit_csv_path),
        "private_cache_dir": str(private_cache_dir),
    }


def _collect_source_record_urls(
    value: Any,
    record_kind: str,
    aggregates: dict[str, dict[str, Any]],
) -> None:
    if isinstance(value, dict):
        raw_url = value.get("source_record_url")
        if isinstance(raw_url, str) and raw_url.strip():
            url = raw_url.strip()
            aggregate = aggregates.setdefault(
                url,
                {
                    "occurrence_count": 0,
                    "record_kinds": set(),
                    "source_names": set(),
                    "formation_ids": set(),
                    "assertion_ids": set(),
                    "rights_scopes": set(),
                },
            )
            aggregate["occurrence_count"] += 1
            aggregate["record_kinds"].add(record_kind)
            _add_nonempty(aggregate["source_names"], value.get("source_name"))
            _add_nonempty(aggregate["formation_ids"], value.get("formation_id"))
            _add_nonempty(aggregate["assertion_ids"], value.get("assertion_id"))
            _add_nonempty(aggregate["rights_scopes"], value.get("rights_scope"))
            _add_nonempty(aggregate["rights_scopes"], value.get("rights_status"))
        for child in value.values():
            _collect_source_record_urls(child, record_kind, aggregates)
    elif isinstance(value, list):
        for child in value:
            _collect_source_record_urls(child, record_kind, aggregates)


def _add_nonempty(values: set[str], candidate: Any) -> None:
    if candidate is not None:
        text = str(candidate).strip()
        if text:
            values.add(text)


def _acquire_one(
    target: SourceTarget,
    *,
    private_cache_dir: Path,
    archive_fallback: bool,
    request: Callable[[str], HttpResponse],
    now_fn: Clock,
    cache_object_lock: threading.Lock,
    cache_error: str,
    source_zip_sha256: str,
) -> dict[str, Any]:
    url_problem = _url_problem(target.url)
    if url_problem:
        result = _base_result(
            target.url,
            status="invalid_url",
            error_code=_join_errors(cache_error, url_problem),
            retrieved_at_utc=_utc_text(now_fn()),
        )
        _write_metadata(target, result, private_cache_dir, source_zip_sha256)
        return result

    live_status = ""
    archive_eligible = True
    errors: list[str] = [cache_error] if cache_error else []
    try:
        live_response = request(target.url)
        live_status = str(live_response.status)
        if _successful_nonempty(live_response):
            return _store_success(
                target,
                response=live_response,
                status="live_success",
                private_cache_dir=private_cache_dir,
                now_fn=now_fn,
                cache_object_lock=cache_object_lock,
                source_zip_sha256=source_zip_sha256,
                live_http_status=live_status,
            )
        if 200 <= live_response.status < 300:
            errors.append("live_empty_content")
        else:
            errors.append(f"live_http_{live_response.status}")
        final_status = _classify_http_failure(live_response.status)
        archive_eligible = live_response.status not in BLOCKED_HTTP_STATUSES
    except UnsafeNetworkTargetError as exc:
        errors.append(_stable_exception_code("live", exc))
        final_status = "blocked"
        archive_eligible = False
    except Exception as exc:  # transport implementations expose different exception classes
        errors.append(_stable_exception_code("live", exc))
        final_status = "unavailable"

    archive_details: dict[str, Any] = {
        "archive_cdx_http_status": "",
        "archive_snapshot_http_status": "",
        "archive_timestamp": "",
        "archive_snapshot_url": "",
    }
    if archive_fallback and archive_eligible:
        archive_result = _try_wayback(target.url, request)
        archive_details.update(archive_result["details"])
        if archive_result["response"] is not None:
            return _store_success(
                target,
                response=archive_result["response"],
                status="archive_success",
                private_cache_dir=private_cache_dir,
                now_fn=now_fn,
                cache_object_lock=cache_object_lock,
                source_zip_sha256=source_zip_sha256,
                live_http_status=live_status,
                **archive_details,
            )
        errors.append(archive_result["error_code"])
    elif archive_fallback:
        errors.append("archive_skipped_not_permitted")

    result = _base_result(
        target.url,
        status=final_status,
        error_code=_join_errors(*errors),
        retrieved_at_utc=_utc_text(now_fn()),
        live_http_status=live_status,
        **archive_details,
    )
    _write_metadata(target, result, private_cache_dir, source_zip_sha256)
    return result


def _try_wayback(
    source_url: str,
    request: Callable[[str], HttpResponse],
) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        [
            ("url", source_url),
            ("output", "json"),
            ("filter", "statuscode:200"),
            ("fl", "timestamp,original,statuscode,digest"),
            ("limit", "1"),
            ("sort", "reverse"),
            ("collapse", "digest"),
        ]
    )
    cdx_url = f"https://web.archive.org/cdx/search/cdx?{query}"
    details: dict[str, str] = {
        "archive_cdx_http_status": "",
        "archive_snapshot_http_status": "",
        "archive_timestamp": "",
        "archive_snapshot_url": "",
    }
    try:
        cdx_response = request(cdx_url)
        details["archive_cdx_http_status"] = str(cdx_response.status)
    except Exception as exc:
        return {
            "response": None,
            "details": details,
            "error_code": _stable_exception_code("archive_cdx", exc),
        }
    if not 200 <= cdx_response.status < 300:
        return {
            "response": None,
            "details": details,
            "error_code": f"archive_cdx_http_{cdx_response.status}",
        }

    capture = _parse_cdx_capture(cdx_response.body)
    if capture is None:
        return {
            "response": None,
            "details": details,
            "error_code": "archive_no_snapshot",
        }
    timestamp, original_url = capture
    snapshot_url = f"https://web.archive.org/web/{timestamp}id_/{original_url}"
    details["archive_timestamp"] = timestamp
    details["archive_snapshot_url"] = snapshot_url
    try:
        snapshot_response = request(snapshot_url)
        details["archive_snapshot_http_status"] = str(snapshot_response.status)
    except Exception as exc:
        return {
            "response": None,
            "details": details,
            "error_code": _stable_exception_code("archive_snapshot", exc),
        }
    if not _successful_nonempty(snapshot_response):
        if 200 <= snapshot_response.status < 300:
            error = "archive_snapshot_empty_content"
        else:
            error = f"archive_snapshot_http_{snapshot_response.status}"
        return {"response": None, "details": details, "error_code": error}
    return {"response": snapshot_response, "details": details, "error_code": ""}


def _parse_cdx_capture(body: bytes) -> tuple[str, str] | None:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, list) or len(payload) < 2:
        return None
    header = payload[0]
    row = payload[1]
    if not isinstance(header, list) or not isinstance(row, list):
        return None
    values = {str(key): row[index] for index, key in enumerate(header) if index < len(row)}
    timestamp = str(values.get("timestamp", "")).strip()
    original = str(values.get("original", "")).strip()
    if not timestamp.isdigit() or len(timestamp) != 14 or _url_problem(original):
        return None
    return timestamp, original


def _store_success(
    target: SourceTarget,
    *,
    response: HttpResponse,
    status: str,
    private_cache_dir: Path,
    now_fn: Clock,
    cache_object_lock: threading.Lock,
    source_zip_sha256: str,
    live_http_status: str = "",
    archive_cdx_http_status: str = "",
    archive_snapshot_http_status: str = "",
    archive_timestamp: str = "",
    archive_snapshot_url: str = "",
) -> dict[str, Any]:
    digest = sha256_bytes(response.body)
    content_type, content_charset = _normalized_content_metadata(response.headers)
    object_relative = _object_relative_path(digest)
    object_path = private_cache_dir.joinpath(*PurePosixPath(object_relative).parts)
    object_path.parent.mkdir(parents=True, exist_ok=True)
    # Multiple URLs commonly resolve to identical publisher error or index
    # pages. Guard the existence/hash/replace sequence so Windows never tries
    # to replace an object while another worker is hashing it.
    with cache_object_lock:
        if object_path.exists():
            if sha256_file(object_path) != digest:
                raise CropSourceAcquisitionError(
                    f"Content-addressed cache collision or corruption for {digest}"
                )
        else:
            _atomic_write_bytes(object_path, response.body)

    result = _base_result(
        target.url,
        status=status,
        content_sha256=digest,
        content_bytes=len(response.body),
        content_type=content_type,
        content_charset=content_charset,
        retrieved_at_utc=_utc_text(now_fn()),
        retrieval_url=response.final_url,
        live_http_status=live_http_status,
        archive_cdx_http_status=archive_cdx_http_status,
        archive_snapshot_http_status=archive_snapshot_http_status,
        archive_timestamp=archive_timestamp,
        archive_snapshot_url=archive_snapshot_url,
        cache_object_path=object_relative,
    )
    _write_metadata(target, result, private_cache_dir, source_zip_sha256)
    return result


def _base_result(
    url: str,
    *,
    status: str,
    content_sha256: str = "",
    content_bytes: int | str = "",
    content_type: str = "",
    content_charset: str = "",
    retrieved_at_utc: str = "",
    retrieval_url: str = "",
    live_http_status: str = "",
    archive_cdx_http_status: str = "",
    archive_snapshot_http_status: str = "",
    archive_timestamp: str = "",
    archive_snapshot_url: str = "",
    error_code: str = "",
    cache_object_path: str = "",
) -> dict[str, Any]:
    return {
        "source_record_url": url,
        "acquisition_status": status,
        "coverage_status": "content_acquired" if status in SUCCESS_STATUSES else "coverage_gap",
        "content_sha256": content_sha256,
        "content_bytes": content_bytes,
        "content_type": content_type,
        "content_charset": content_charset,
        "retrieved_at_utc": retrieved_at_utc,
        "retrieval_url": retrieval_url,
        "live_http_status": live_http_status,
        "archive_cdx_http_status": archive_cdx_http_status,
        "archive_snapshot_http_status": archive_snapshot_http_status,
        "archive_timestamp": archive_timestamp,
        "archive_snapshot_url": archive_snapshot_url,
        "error_code": error_code,
        "cache_object_path": cache_object_path,
    }


def _write_metadata(
    target: SourceTarget,
    result: Mapping[str, Any],
    private_cache_dir: Path,
    source_zip_sha256: str,
) -> None:
    archive_provenance = None
    if result.get("archive_snapshot_url") or result.get("archive_cdx_http_status"):
        archive_provenance = {
            "cdx_http_status": result.get("archive_cdx_http_status", ""),
            "snapshot_http_status": result.get("archive_snapshot_http_status", ""),
            "snapshot_timestamp": result.get("archive_timestamp", ""),
            "snapshot_url": result.get("archive_snapshot_url", ""),
        }
    metadata = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "source_record_url": target.url,
        "acquisition_status": result["acquisition_status"],
        "coverage_status": result["coverage_status"],
        "retrieved_at_utc": result.get("retrieved_at_utc", ""),
        "retrieval_url": result.get("retrieval_url", ""),
        "content_sha256": result.get("content_sha256", ""),
        "content_bytes": result.get("content_bytes", ""),
        "content_type": result.get("content_type", ""),
        "content_charset": result.get("content_charset", ""),
        "cache_object_path": result.get("cache_object_path", ""),
        "live_http_status": result.get("live_http_status", ""),
        "archive_cdx_http_status": result.get("archive_cdx_http_status", ""),
        "archive_snapshot_http_status": result.get("archive_snapshot_http_status", ""),
        "archive_timestamp": result.get("archive_timestamp", ""),
        "archive_snapshot_url": result.get("archive_snapshot_url", ""),
        "archive_provenance": archive_provenance,
        "error_code": result.get("error_code", ""),
        "rights": {
            "cache_policy": PRIVATE_CACHE_RIGHTS_POLICY,
            "input_rights_scopes": list(target.rights_scopes),
        },
        "source_context": {
            "record_kinds": list(target.record_kinds),
            "source_names": list(target.source_names),
            "formation_ids": list(target.formation_ids),
            "assertion_ids": list(target.assertion_ids),
            "occurrence_count": target.occurrence_count,
        },
        "source_zip_sha256": source_zip_sha256,
    }
    metadata_path = _metadata_path(target.url, private_cache_dir)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    _atomic_write_bytes(metadata_path, payload)


def _load_metadata(url: str, private_cache_dir: Path) -> dict[str, Any] | None:
    path = _metadata_path(url, private_cache_dir)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("schema_version") != CACHE_SCHEMA_VERSION:
        return None
    if payload.get("source_record_url") != url:
        return None
    return payload


def _load_verified_success_metadata(
    url: str,
    private_cache_dir: Path,
) -> tuple[dict[str, Any] | None, str]:
    metadata_path = _metadata_path(url, private_cache_dir)
    if not metadata_path.exists():
        return None, ""
    metadata = _load_metadata(url, private_cache_dir)
    if metadata is None:
        return None, "cache_metadata_invalid"
    if metadata.get("acquisition_status") not in SUCCESS_STATUSES:
        return None, ""
    digest = str(metadata.get("content_sha256", ""))
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest.lower()):
        return None, "cache_content_hash_invalid"
    expected_relative = _object_relative_path(digest.lower())
    if metadata.get("cache_object_path") != expected_relative:
        return None, "cache_object_path_invalid"
    object_path = private_cache_dir.joinpath(*PurePosixPath(expected_relative).parts)
    if not object_path.is_file():
        return None, "cache_object_missing"
    if sha256_file(object_path) != digest.lower():
        return None, "cache_object_hash_mismatch"
    return metadata, ""


def _audit_row(
    target: SourceTarget,
    result: Mapping[str, Any],
    source_zip_sha256: str,
) -> dict[str, str | int]:
    return {
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        "source_record_url": target.url,
        "occurrence_count": target.occurrence_count,
        "record_kinds": ";".join(target.record_kinds),
        "source_names": ";".join(target.source_names),
        "formation_ids": ";".join(target.formation_ids),
        "assertion_ids": ";".join(target.assertion_ids),
        "input_rights_scopes": ";".join(target.rights_scopes),
        "cache_rights_policy": PRIVATE_CACHE_RIGHTS_POLICY,
        "acquisition_status": str(result.get("acquisition_status", "")),
        "coverage_status": str(result.get("coverage_status", "coverage_gap")),
        "content_sha256": str(result.get("content_sha256", "")),
        "content_bytes": result.get("content_bytes", ""),
        "content_type": str(result.get("content_type", "")),
        "content_charset": str(result.get("content_charset", "")),
        "retrieved_at_utc": str(result.get("retrieved_at_utc", "")),
        "retrieval_url": str(result.get("retrieval_url", "")),
        "live_http_status": str(result.get("live_http_status", "")),
        "archive_cdx_http_status": str(result.get("archive_cdx_http_status", "")),
        "archive_snapshot_http_status": str(
            result.get("archive_snapshot_http_status", "")
        ),
        "archive_timestamp": str(result.get("archive_timestamp", "")),
        "archive_snapshot_url": str(result.get("archive_snapshot_url", "")),
        "error_code": str(result.get("error_code", "")),
        "source_zip_sha256": source_zip_sha256,
        "cache_metadata_path": _metadata_relative_path(target.url),
        "cache_object_path": str(result.get("cache_object_path", "")),
    }


def _write_audit_csv(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for row in sorted(rows, key=lambda item: str(item["source_record_url"])):
            writer.writerow(row)


def _metadata_relative_path(url: str) -> str:
    return f"metadata/{sha256_bytes(url.encode('utf-8'))}.json"


def _metadata_path(url: str, private_cache_dir: Path) -> Path:
    return private_cache_dir.joinpath(*PurePosixPath(_metadata_relative_path(url)).parts)


def _object_relative_path(content_sha256: str) -> str:
    return f"objects/{content_sha256[:2]}/{content_sha256}.bin"


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=f".{path.name}.{os.getpid()}.",
        suffix=".tmp",
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _url_problem(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url)
    except ValueError:
        return "invalid_source_url"
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return "invalid_source_url"
    try:
        parsed.port
    except ValueError:
        return "invalid_source_url"
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "localhost" or hostname.endswith(".local"):
        return "blocked_private_source_url"
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return ""
    if not address.is_global:
        return "blocked_private_source_url"
    return ""


def _assert_public_network_target(
    url: str,
    *,
    resolver: Callable[..., list[tuple[Any, ...]]] | None = None,
) -> None:
    """Fail before connection unless every resolved address is globally routable."""

    url_problem = _url_problem(url)
    if url_problem:
        raise UnsafeNetworkTargetError(url_problem)
    parsed = urllib.parse.urlsplit(url)
    hostname = parsed.hostname
    assert hostname is not None
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    resolver = resolver or socket.getaddrinfo
    addresses = resolver(hostname, port, type=socket.SOCK_STREAM)
    if not addresses:
        raise socket.gaierror(f"No addresses resolved for {hostname}")
    for address_info in addresses:
        socket_address = address_info[4]
        if not socket_address:
            raise UnsafeNetworkTargetError("unusable_resolved_source_address")
        raw_address = str(socket_address[0]).split("%", 1)[0]
        try:
            address = ipaddress.ip_address(raw_address)
        except ValueError as exc:
            raise UnsafeNetworkTargetError("unusable_resolved_source_address") from exc
        if not address.is_global:
            raise UnsafeNetworkTargetError("blocked_private_resolved_source_address")


class _SafeRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Validate every HTTP redirect destination before urllib connects to it."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> urllib.request.Request | None:
        _assert_public_network_target(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _normalized_content_metadata(
    headers: Mapping[str, str] | None,
) -> tuple[str, str]:
    """Return lowercase media type and charset from response headers."""

    raw_content_type = ""
    for key, value in (headers or {}).items():
        if str(key).casefold() == "content-type":
            raw_content_type = str(value).strip()
            break
    if not raw_content_type:
        return "", ""
    parts = [part.strip() for part in raw_content_type.split(";")]
    content_type = parts[0].casefold()
    charset = ""
    for parameter in parts[1:]:
        name, separator, value = parameter.partition("=")
        if separator and name.strip().casefold() == "charset":
            charset = value.strip().strip("\"'").casefold()
            break
    return content_type, charset


def _successful_nonempty(response: HttpResponse) -> bool:
    return 200 <= response.status < 300 and bool(response.body)


def _classify_http_failure(status: int) -> str:
    return "blocked" if status in BLOCKED_HTTP_STATUSES else "unavailable"


def _stable_exception_code(prefix: str, exc: Exception) -> str:
    if isinstance(exc, ContentTooLargeError):
        suffix = "content_too_large"
    elif isinstance(exc, SystemTrustStoreError):
        suffix = str(exc) or "system_truststore_error"
    elif isinstance(exc, UnsafeNetworkTargetError):
        suffix = str(exc) or "unsafe_network_target"
    elif isinstance(exc, TimeoutError):
        suffix = "timeout"
    else:
        suffix = type(exc).__name__.lower()
    return f"{prefix}_{suffix}"


def _join_errors(*errors: str) -> str:
    return ";".join(error for error in errors if error)


def _utc_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _build_system_trust_context() -> ssl.SSLContext:
    """Create a verified TLS client context backed by the native trust store."""

    try:
        truststore = importlib.import_module("truststore")
    except (ImportError, ModuleNotFoundError) as exc:
        raise SystemTrustStoreError("system_truststore_unavailable") from exc
    try:
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except Exception as exc:
        raise SystemTrustStoreError("system_truststore_initialization_failed") from exc
    if context.verify_mode != ssl.CERT_REQUIRED or context.check_hostname is not True:
        raise SystemTrustStoreError("system_truststore_verification_disabled")
    return context


def _stdlib_fetch(
    url: str,
    timeout_seconds: float,
    user_agent: str,
    max_content_bytes: int,
    *,
    ssl_context: ssl.SSLContext | None = None,
) -> HttpResponse:
    _assert_public_network_target(url)
    ssl_context = ssl_context or _build_system_trust_context()
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/json,text/plain;q=0.9,*/*;q=0.5",
        },
        method="GET",
    )
    opener = urllib.request.build_opener(
        _SafeRedirectHandler(),
        urllib.request.HTTPSHandler(context=ssl_context),
    )
    try:
        response = opener.open(request, timeout=timeout_seconds)
    except urllib.error.HTTPError as exc:
        body = exc.read(max_content_bytes + 1)
        if len(body) > max_content_bytes:
            raise ContentTooLargeError("response_exceeded_max_content_bytes") from exc
        return HttpResponse(
            status=int(exc.code),
            body=body,
            final_url=exc.geturl(),
            headers=dict(exc.headers.items()) if exc.headers else {},
        )
    with response:
        body = response.read(max_content_bytes + 1)
        if len(body) > max_content_bytes:
            raise ContentTooLargeError("response_exceeded_max_content_bytes")
        final_url = response.geturl()
        if _url_problem(final_url):
            raise CropSourceAcquisitionError("unsafe_final_response_url")
        return HttpResponse(
            status=int(response.status),
            body=body,
            final_url=final_url,
            headers=dict(response.headers.items()),
        )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Discover or privately acquire Crop Circle Atlas source pages."
    )
    parser.add_argument("--crop-zip", type=Path, required=True)
    parser.add_argument("--audit-csv", type=Path, required=True)
    parser.add_argument("--private-cache-dir", type=Path, required=True)
    parser.add_argument("--expected-zip-sha256", default=PINNED_CROP_ZIP_SHA256)
    parser.add_argument(
        "--network",
        action="store_true",
        help="Explicitly allow live HTTP retrieval. The default is offline discovery only.",
    )
    parser.add_argument(
        "--archive-fallback",
        action="store_true",
        help="With --network, allow Wayback CDX and snapshot fallback.",
    )
    parser.add_argument("--rate-limit-seconds", type=float, default=0.5)
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--max-content-bytes", type=int, default=DEFAULT_MAX_CONTENT_BYTES)
    parser.add_argument(
        "--retry-failures",
        action="store_true",
        help="Explicitly retry completed failed/blocked attempts instead of resuming past them.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Maximum concurrent source targets; request starts remain globally rate-limited.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Report progress to stderr after this many source dispositions.",
    )
    return parser


def _print_progress(
    completed: int,
    total: int,
    target: SourceTarget,
    status: str,
) -> None:
    print(
        f"crop-source acquisition {completed:,}/{total:,}: {status} {target.url}",
        file=sys.stderr,
        flush=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    summary = acquire_crop_sources(
        args.crop_zip,
        args.audit_csv,
        args.private_cache_dir,
        expected_zip_sha256=args.expected_zip_sha256,
        network=args.network,
        archive_fallback=args.archive_fallback,
        rate_limit_seconds=args.rate_limit_seconds,
        timeout_seconds=args.timeout_seconds,
        max_content_bytes=args.max_content_bytes,
        retry_failures=args.retry_failures,
        workers=args.workers,
        progress_every=args.progress_every,
        progress_fn=_print_progress,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
