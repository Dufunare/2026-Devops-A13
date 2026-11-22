# E14 member C — real-project profile plumbing (pre-integration)

This preparatory change is based on the **PR #24 combined preflight tree**
`268a0ccb9a07a4aedd7bde6879cd7e912b70c358`. That tree is **not**
a merged integration baseline, an independent Review, or a release candidate.

## Implemented without freezing B's unfinished interface

- Accept the optional E11/E12 `request.profile` object. Absence keeps the
  teaching fixture's exact default target/source selection and build target.
- Resolve and validate it using B's existing `lab.resolve_profile` and
  `pipeline.shape_ok`, not a second implementation.
- Preserve one resolved `profile` in `result.json` and forward it to all
  four services. BuildChecker uses the selected Make clean/build targets.
  EChecker projects actual edges and findings using `profile.units`.
  MDFixer passes the profile to B's `validate`.
- If `profile.exec_image=draft`, reject it before scheduling work; the
  current four-service plumbing does **not** implement DRAFT-image
  downstream execution. Never silently run in the orchestrator instead.
- Keep the conservative **all-build-targets MISSING=0** final recheck
  until B/A confirm whether the formal gate should be profile-scoped.

## Still requires B's interface / group integration

- Frozen real project C0/C1, original request SHA256, candidate Dockerfile
  SHA256, full `profile`, declared detector scope and success criteria.
- Immutable successful DRAFT image ID and agreed downstream execution
  and isolation mechanism (including no inherited Docker socket).
- Real-project four-service integration, independent Review of source PRs,
  final merged-source SHA, official bilateral inputs and formal acceptance.

This branch must **not** be merged into main or PR #24 as a substitute for
normal PR #19/#20/#22/#23 review and merge ordering.

## Non-Docker contract verification

```bash
python3 -m py_compile labs/e13e14/orchestrate.py labs/e13e14/service.py \
    labs/e13e14/tests/test_e14_profile.py
python3 -m unittest discover -s labs/e13e14/tests -p 'test_*.py' -v
```

The existing `e14_gate.py` continues to validate the fixed teaching
fixture separately; it is not a real-project E14 acceptance test.

## Isolated ECS fixture regression (parallel to the original service)

Optional host port variables `E14_PORT_BUILDCHECKER`, `E14_PORT_ECHECKER`,
`E14_PORT_DRAFT`, `E14_PORT_MDFIXER` apply consistently to Compose,
`orchestrate.py` and `e14_gate.py`. All default to original 18081-18084;
changing their values does not alter the API's in-container port 8080.

On ECS, keep the original Compose project `e14-241830217-c` running.
For a dedicated worktree and unmodified evidence, choose a new project name
(e.g., `e14-profile-241830217`) and unused local ports 18181-18184.
Do **not** use the original project's containers to validate this branch.
Copy the ignored teaching fixtures from the original workspace into the new
worktree before running any integration gate; do not symlink absolute host
paths into the containers. In the new worktree, the fixture's /course paths
resolve within the new mounted project.

The sample-specific gate still expects its pinned success/timeout/recovery
outputs (162 artifacts per successful run), and remains a regression test,
not formal real-project acceptance.


## B real08 contract preparation

This branch now records canonical profile/request/candidate SHA256 and requires one successful DRAFT build with a complete image ID. That **reported** ID is passed to all downstream HTTP services, but does not attest execution in the image. The orchestrator checks report original bytes, SHA256, job/trace, commit, profile SHA and DRAFT ID before passing the incremental-check to MDFixer; the receiver repeats checks before applying a patch. The EChecker emits both complete BuildChecker findings and the B profile-target projection. Final MISSING=0 applies to all actual BuildChecker targets.

For B's frozen input (staged under this worktree's ignored data/), run the no-Docker preflight:

```bash
python3 labs/e13e14/real_preflight.py \\
  --request data/real-e12-inimage.json \\
  --request-sha256 4b8267018b7189b9cb0b214397de0779388f0860d9aec529787603f53393a5a5 \\
  --candidate-sha256 eb506f89177da2eb5736b7a62336b0f2d156e81feca04de1ef5747ce27f7eb8a
```

Real `exec_image=draft` remains fail-closed until B/A land safe subprocess isolation and per-container image/mount attestation. Do not change the input profile to orchestrator mode as a workaround. Existing teaching fixed-fixture CI remains independent of this unaccepted real-project execution.
