"""E14 service-boundary evidence contract. No DRAFT-image execution here."""
import hashlib
import json
import re

IMAGE_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def profile_sha256(profile):
    raw = json.dumps(profile, sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    return digest(raw)


def require_image_id(value):
    if not isinstance(value, str) or IMAGE_RE.fullmatch(value) is None:
        raise ValueError("DRAFT_IMAGE_ID_INVALID: expected complete sha256 image ID")
    return value


def successful_draft_image(response):
    """Select the one successful build ID, not a tag or a historical reference."""
    if not isinstance(response, dict) or response.get("status") != "SUCCEEDED":
        raise ValueError("DRAFT_IMAGE_MISSING: service did not succeed")
    report = response.get("result")
    if not isinstance(report, dict) or report.get("status") != "SUCCEEDED":
        raise ValueError("DRAFT_IMAGE_MISSING: report did not succeed")
    attempts = report.get("attempts")
    if not isinstance(attempts, list):
        raise ValueError("DRAFT_IMAGE_MISSING: attempts absent")
    successes = [a for a in attempts if isinstance(a, dict)
                 and a.get("build_exit_code") == 0]
    if len(successes) != 1:
        raise ValueError("DRAFT_IMAGE_MISSING: expected exactly one successful build")
    image = require_image_id(successes[0].get("image_id"))
    if response.get("draft_image_id") is not None and response["draft_image_id"] != image:
        raise ValueError("DRAFT_IMAGE_ID_MISMATCH: service response differs from build")
    return image


def verify_request_identity(request, profile):
    expected = request.get("profile_sha256")
    if expected is not None and expected != profile_sha256(profile):
        raise ValueError("PROFILE_HASH_MISMATCH: service profile differs from request")
    image = request.get("draft_image_id")
    if image is not None:
        require_image_id(image)
    return image


def checked_incremental(raw, sha256, job, trace, commit,
                        expected_profile_sha=None, expected_image_id=None):
    """Verify original bytes, strict JSON, and job/source/image binding pre-patch."""
    if not isinstance(sha256, str) or SHA_RE.fullmatch(sha256) is None:
        raise ValueError("REPORT_SHA_INVALID")
    if digest(raw) != sha256:
        raise ValueError("REPORT_HASH_MISMATCH: transferred bytes changed")
    from handoff import strict_json
    report = strict_json(raw)
    for key, expected in (("schema_version", "e11e12-1"),
                          ("kind", "incremental-check"), ("status", "SUCCEEDED"),
                          ("job_id", job), ("trace_id", trace), ("commit", commit)):
        if report.get(key) != expected:
            raise ValueError("REPORT_IDENTITY_MISMATCH: " + key)
    payload = report.get("data")
    if not isinstance(payload, dict) or payload.get("commit") != commit:
        raise ValueError("REPORT_DATA_COMMIT_MISMATCH")
    findings = payload.get("findings")
    if not isinstance(findings, list) or not all(
        isinstance(item, dict) and item.get("type") in ("MISSING", "REDUNDANT")
        and isinstance(item.get("target"), str) and bool(item["target"])
        and isinstance(item.get("dependency"), str) and bool(item["dependency"])
        for item in findings
    ):
        raise ValueError("REPORT_FINDINGS_INVALID")
    if expected_profile_sha is not None and report.get("profile_sha256") != expected_profile_sha:
        raise ValueError("PROFILE_HASH_MISMATCH: incremental report")
    if expected_image_id is not None:
        require_image_id(expected_image_id)
        if report.get("draft_image_id") != expected_image_id:
            raise ValueError("DRAFT_IMAGE_ID_MISMATCH: incremental report")
    return report


def findings_by_scope(findings, profile):
    """Retain every actual-build finding and separately project B's target set."""
    if not isinstance(findings, list):
        raise ValueError("FINDINGS_INVALID")
    targets = {target for target, _source in profile["units"]}
    selected = [item for item in findings if item["target"] in targets]
    return {"full_findings": findings,
            "profile_findings": selected,
            "profile_targets": sorted(targets),
            "remaining_missing_full": sum(x["type"] == "MISSING" for x in findings),
            "remaining_missing_profile": sum(x["type"] == "MISSING" for x in selected)}
