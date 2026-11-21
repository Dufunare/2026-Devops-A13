"""Run inside the course container with the repository at /course and an empty writable /evidence."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import lab

out = Path("/evidence")
if any(out.iterdir()):
    sys.exit("Use an empty /evidence directory")
repo = out / "project"
subprocess.run(["git", "clone", "-q", "--no-local",
                "/course/data/e13-upstream-student/H2-inih/repo", str(repo)], check=True)
def snapshot():
    def git(*args):
        return subprocess.check_output(["git", "-C", str(repo), *args], text=True).strip()
    return {"commit": git("rev-parse", "HEAD"), "status": git("status", "--porcelain"),
            "makefile_sha256": hashlib.sha256((repo / "Makefile").read_bytes()).hexdigest()}

before = snapshot()
assert before["commit"] == "3aadb81763c79651e4dfa99b725ba921ee2b8a39" and not before["status"]
good = Path(sys.argv[1]).read_text()
line = "+main.o: main.c config.h unused.h extra.h"
assert good.count(line) == 1
bad = out / "wrong-dependency.patch"
bad.write_text(good.replace(line, "+main.o: main.c config.h unused.h ini.h"))
v = lab.validate(repo, bad, out / "validation")
after = snapshot()
(out / "c5-result.json").write_text(json.dumps({"before": before, "after": after, "validation": v}, indent=2) + "\n")
assert v["accepted"] is False and v["rollback"] and v["source_unchanged"] and before == after
assert v["checks"] == dict(patch_applies=True, build=True, test=True, header_change=True, no_missing=False)
findings = json.loads((out / "validation/recheck.json").read_bytes())["findings"]
assert [(f["target"], f["dependency"]) for f in findings if f["type"] == "MISSING"] == [("main.o","extra.h")]
print("C5_H2_PREFLIGHT=PASS")
