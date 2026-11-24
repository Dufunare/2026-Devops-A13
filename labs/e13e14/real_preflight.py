"""Check B's frozen real08 input without executing Docker or modifying the repo."""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(HERE), str(ROOT / "labs/e11e12"), str(ROOT / "labs/e8e10")]
from contract import digest, profile_sha256
from lab import resolve_profile
from pipeline import shape_ok


def course_data(value, root):
    if not isinstance(value, str) or not value.startswith("/course/data/"):
        raise ValueError("REAL_INPUT_PATH_INVALID")
    safe_root = (root / "data").resolve()
    path = (root / value[len("/course/"):]).resolve()
    if not path.is_relative_to(safe_root):
        raise ValueError("REAL_INPUT_PATH_ESCAPE")
    return path


def git(repo, *args):
    p = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise ValueError("REAL_GIT_OBJECT_MISSING: " + " ".join(args))
    return p.stdout.strip()


def verify(request_path, root=ROOT, *, expected_request_sha=None,
           expected_candidate_sha=None):
    from handoff import strict_json
    raw = Path(request_path).read_bytes()
    request = strict_json(raw)
    if request.get("mode") != "e12":
        raise ValueError("REAL_MODE_INVALID: expected e12")
    for name in ("base", "target"):
        revision = request.get(name)
        if not isinstance(revision, str) or re.fullmatch(r"[0-9a-f]{40}", revision) is None:
            raise ValueError("REAL_COMMIT_INVALID: " + name)
    profile = resolve_profile(request.get("profile"))
    repo = course_data(request["repo"], root)
    candidate = course_data(request["candidate"], root)
    if not repo.is_dir() or not candidate.is_file():
        raise ValueError("REAL_INPUT_MISSING")
    if git(repo, "rev-parse", "HEAD") != request["target"]:
        raise ValueError("REAL_C1_HEAD_MISMATCH")
    for name in ("base", "target"):
        git(repo, "cat-file", "-e", request[name] + "^{commit}")
    shape, sources, expected = shape_ok(repo, profile)
    if not shape:
        raise ValueError("REAL_PROFILE_SHAPE_MISMATCH: " + repr((sorted(sources), sorted(expected))))
    request_sha, candidate_sha = digest(raw), digest(candidate.read_bytes())
    if expected_request_sha and request_sha != expected_request_sha:
        raise ValueError("REAL_REQUEST_HASH_MISMATCH")
    if expected_candidate_sha and candidate_sha != expected_candidate_sha:
        raise ValueError("REAL_CANDIDATE_HASH_MISMATCH")
    return {"status": "INPUT_VERIFIED_EXECUTION_NOT_STARTED",
            "base_commit": request["base"], "target_commit": request["target"],
            "request_sha256": request_sha, "candidate_sha256": candidate_sha,
            "profile_sha256": profile_sha256(profile), "profile": profile,
            "execution_requested": profile["exec_image"],
            "draft_image_id": None, "downstream_container_attested": False,
            "note": "Executor/socket-isolation pending; no Docker or E14 job executed"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--request", type=Path, required=True)
    p.add_argument("--request-sha256")
    p.add_argument("--candidate-sha256")
    a = p.parse_args()
    result = verify(a.request, expected_request_sha=a.request_sha256,
                    expected_candidate_sha=a.candidate_sha256)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
