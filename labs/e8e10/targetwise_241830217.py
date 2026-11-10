"""Student 241830217: target-local dependency-cache invalidation for E8-E10.

This is an optional teaching-profile extension, not the paper's syscall-based
EChecker. The original lab.scan() and its conservative semantics are unchanged.

Only the two explicit GCC/Make object targets from lab.fixture are supported.
Each target carries a fingerprint of its own recipe and all *previously read*
local source/header preprocessor lines. A change to those inputs refreshes that
target via GCC -MM; a change elsewhere does not. Declarations are ALWAYS parsed
again, even if the actual dependency graph is reused. Unknown/invalid historical
fingerprints force a refresh rather than claiming a cache hit.
"""

import time
from pathlib import Path
from typing import Any, Dict, Optional

from lab import declarations, run

TARGET_SOURCES = (("main.o", "main.c"), ("helper.o", "helper.c"))
ALLOWED_FLAGS = ("-O0", "-O1", "-O0 -DMODE=1")
SCHEMA = "e8e10-targetwise-241830217-v1"


def _recipe(makefile: str, target: str):
    """Read only this object's recipe, not unrelated target recipes."""
    lines = makefile.splitlines()
    for index, line in enumerate(lines):
        if line.startswith(target + ":"):
            recipe = []
            for following in lines[index + 1 :]:
                if not following.startswith("\t"):
                    break
                recipe.append(following)
            if not recipe:
                raise ValueError("UNSUPPORTED_RECIPE " + target)
            return recipe
    raise ValueError("UNSUPPORTED_RULE " + target)


def _source_fingerprint(root: Path, dep: str):
    """Detect relevant lexical changes, including comment-boundary edits.

    This uses the same narrow local C/Make semantics as the course profile,
    not a general C preprocessor or syscall tracker. Missing and unsafe paths
    fail closed rather than reusing an old dependency set.
    """
    path = Path(dep)
    if (path.is_absolute() or ".." in path.parts or path.suffix not in (".c", ".h")
            or not path.parts or path.parts[0].startswith(".")):
        raise ValueError("UNSUPPORTED_DEPENDENCY " + dep)
    full = root / path
    if full.is_symlink() or not full.is_file():
        raise ValueError("COMMAND_FAILED missing/unsafe dependency " + dep)
    relevant = []
    for line in full.read_text().splitlines():
        # A change to a block-comment delimiter can activate/deactivate a
        # previously present #include line without changing that line itself.
        if line.lstrip().startswith("#") or "/*" in line or "*/" in line:
            relevant.append(line)
    return relevant


def _signature(root: Path, target: str, source: str, dependencies,
               makefile: str, flags: str, compiler: str):
    paths = sorted(set(dependencies) | {source})
    return {
        "files": {dep: _source_fingerprint(root, dep) for dep in paths},
        "recipe": _recipe(makefile, target),
        "flags": flags,
        "compiler": compiler,
    }


def _findings(actual, declared):
    rows = []
    for target, _ in TARGET_SOURCES:
        for kind, deps in (
            ("MISSING", set(actual[target]) - set(declared[target])),
            ("REDUNDANT", set(declared[target]) - set(actual[target])),
        ):
            rows.extend({"type": kind, "target": target, "dependency": dep}
                        for dep in sorted(deps))
    return rows


def _as_edges(rows):
    return {(row["type"], row["target"], row["dependency"])
            for row in rows}


def scan_targetwise(project: Path, old: Optional[Dict[str, Any]] = None):
    """Incrementally scan two object targets with independently checked caches.

    Explicitly compares the old target fingerprint with current files. Does not
    reuse an unrelated base-course report (its schema differs). A full scan via
    lab.scan(project) is the independent oracle used in the student tests.
    """
    start = time.perf_counter()
    project = Path(project)
    declared, flags = declarations(project)
    if flags not in ALLOWED_FLAGS:
        raise ValueError("UNSUPPORTED_FLAGS")
    makefile = (project / "Makefile").read_text()
    compiler = run(["gcc", "--version"], project).splitlines()[0]
    compatible = isinstance(old, dict) and old.get("schema_version") == SCHEMA
    actual, keys, reused, refreshed = {}, {}, [], []
    for target, source in TARGET_SOURCES:
        previous = old.get("actual", {}).get(target) if compatible else None
        saved_key = old.get("target_keys", {}).get(target) if compatible else None
        if (isinstance(previous, list) and
                isinstance(saved_key, dict) and
                _signature(project, target, source, previous, makefile, flags, compiler) == saved_key):
            actual[target] = list(previous)
            reused.append(target)
        else:
            observed = run(["gcc", *flags.split(), "-MM", "-MT", target, source], project)
            actual[target] = sorted(set(observed.replace("\\\n", " ").split(":", 1)[1].split()))
            refreshed.append(target)
        keys[target] = _signature(project, target, source, actual[target], makefile, flags, compiler)
    findings = _findings(actual, declared)
    current = _as_edges(findings)
    previous_edges = _as_edges(old.get("findings", [])) if compatible else set()
    return {
        "schema_version": SCHEMA,
        "profile": "GCC_LOCAL_HEADERS_EXPLICIT_MAKE_TARGETWISE",
        "commit": run(["git", "rev-parse", "HEAD"], project).strip(),
        "target_keys": keys,
        "actual": actual,
        "declared": declared,
        "findings": findings,
        "added": [list(edge) for edge in sorted(current - previous_edges)],
        "resolved": [list(edge) for edge in sorted(previous_edges - current)],
        "reused": reused,
        "refreshed": refreshed,
        "elapsed_s": time.perf_counter() - start,
    }
