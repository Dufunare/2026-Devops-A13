# E14 member C — real-project profile plumbing (pre-integration)

This preparatory change is based on the **PR #24 combined preflight tree**
\`268a0ccb9a07a4aedd7bde6879cd7e912b70c358\`. That tree is **not**
a merged integration baseline, an independent Review, or a release candidate.

## Implemented without freezing B's unfinished interface

- Accept the optional E11/E12 \`request.profile\` object. Absence keeps the
  teaching fixture's exact default target/source selection and build target.
- Resolve and validate it using B's existing \`lab.resolve_profile\` and
  \`pipeline.shape_ok\`, not a second implementation.
- Preserve one resolved \`profile\` in \`result.json\` and forward it to all
  four services. BuildChecker uses the selected Make clean/build targets.
  EChecker projects actual edges and findings using \`profile.units\`.
  MDFixer passes the profile to B's \`validate\`.
- If \`profile.exec_image=draft\`, reject it before scheduling work; the
  current four-service plumbing does **not** implement DRAFT-image
  downstream execution. Never silently run in the orchestrator instead.
- Keep the conservative **all-build-targets MISSING=0** final recheck
  until B/A confirm whether the formal gate should be profile-scoped.

## Still requires B's interface / group integration

- Frozen real project C0/C1, original request SHA256, candidate Dockerfile
  SHA256, full \`profile\`, declared detector scope and success criteria.
- Immutable successful DRAFT image ID and agreed downstream execution
  and isolation mechanism (including no inherited Docker socket).
- Real-project four-service integration, independent Review of source PRs,
  final merged-source SHA, official bilateral inputs and formal acceptance.

This branch must **not** be merged into main or PR #24 as a substitute for
normal PR #19/#20/#22/#23 review and merge ordering.

## Non-Docker contract verification

\`\`\`bash
python3 -m py_compile labs/e13e14/orchestrate.py labs/e13e14/service.py \
    labs/e13e14/tests/test_e14_profile.py
python3 -m unittest discover -s labs/e13e14/tests -p 'test_*.py' -v
\`\`\`

The existing \`e14_gate.py\` continues to validate the fixed teaching
fixture separately; it is not a real-project E14 acceptance test.
