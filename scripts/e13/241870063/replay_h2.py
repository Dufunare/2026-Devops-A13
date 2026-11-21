"""Run from the A13 repository root after restoring the H2 input and request."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

case = Path("data/e13-upstream-student/H2-inih")
request = case / "request-e12.json"
spec = json.loads(request.read_text())
c0 = "aafc740a2cac05a74541abede93b7d59ed23b87f"
c1 = "3aadb81763c79651e4dfa99b725ba921ee2b8a39"
assert (spec["base"], spec["target"], spec["mode"]) == (c0, c1, "e12")
assert spec["repo"] == "/course/" + str(case / "repo")
assert spec["candidate"] == "/course/" + str(case / "candidate.Dockerfile")
assert spec["expected_output"] == "1"
def git(*args):
    return subprocess.check_output(["git", "-C", str(case / "repo"), *args], text=True).strip()
assert git("rev-parse", "HEAD") == c1 and git("rev-parse", "HEAD^") == c0
assert not git("status", "--porcelain")
Path("work").mkdir(exist_ok=True)
run = Path(tempfile.mkdtemp(prefix="h2-replay-", dir="work"))
out = run / "result"
(run / "source-commit.txt").write_bytes(subprocess.check_output(["git", "rev-parse", "HEAD"]))
print("Output:", run.resolve(), flush=True)
with (run / "console.log").open("wb") as log:
    rc = subprocess.run([sys.executable, "run_e11e12.py", "run", "--request",
                         str(request), "--out", str(out)], stdout=log, stderr=subprocess.STDOUT).returncode
(run / "exit-code.txt").write_text(f"{rc}\n")
if rc:
    sys.exit(rc)
def read(name):
    return json.loads((out / name).read_bytes())
result = read("result.json")
assert result["status"] == "SUCCEEDED"
assert [s["name"] for s in result["stages"]] == ["draft", "full-check", "incremental-check", "repair", "recheck"]
ref = read("repair.json")["data"]["input_report"]
assert ref["uri"] == f"artifact://{result['job_id']}/incremental-check.json"
assert hashlib.sha256((out / "incremental-check.json").read_bytes()).hexdigest() == ref["sha256"]
validation = read("validation/validation.json")
assert validation["accepted"] and all(validation["checks"].values())
assert sorted((f["type"], f["target"], f["dependency"]) for f in read("recheck.json")["data"]["findings"]) == [("REDUNDANT", "main.o", "unused.h")]
print("H2 verified", result["job_id"], result["downstream_executed_in"])
