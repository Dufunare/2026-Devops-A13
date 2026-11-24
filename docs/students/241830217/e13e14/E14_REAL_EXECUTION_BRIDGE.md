# E14 real DRAFT execution bridge — member C (241830217)

Development baseline: d43c67860b66d5ed8ac3ff95cf016d6b839650e9.
Review increment only; this is not a final acceptance record.

- DRAFT alone retains Docker socket access. Its /v1/execute is a restricted
  serial operation broker, registered after the current DRAFT succeeds.
  No arbitrary argv, mount, URL, image override or output path is accepted.
- Operation order: full-check-baseline, full-check-target, scan-baseline,
  scan-target, validate, full-check-recheck. Existing imgrunner and lab.validate
  provide actual child execution. BuildChecker/EChecker/MDFixer retain their roles.
- The orchestrator saves original request bytes in draft mode, binds the
  request and candidate hashes, resolved profile, C0/C1, Job/Trace and
  actual DRAFT image ID. It verifies every exec/inspect pair and operation
  receipt before admitting the final stage. Full-project MISSING=0 is still required.
- Existing default teaching mode retains its original contract and artifact count.
- Trusted course workspace only; not an authenticated public API or a hostile-code
  sandbox. Keep loopback bindings. A new DRAFT invalidates the previous broker
  context; execute jobs serially.

Pending: B's full-project build/run target and repair-scope contract, official
paired inputs, real-engine execution evidence and final ECS acceptance. The
existing validation assumes the build target is executable, so draft mode rejects
make all rather than invoking ./all or silently falling back to orchestrator.
Offline synthetic evidence tests are not proof of real container execution.

## Independent controlled-fixture execution gate

real_job_gate.py requires expected original request and candidate hashes; checks
all five stages, all six HTTP exchanges, raw DRAFT image inspect, report payload,
validation output, complete findings, attestation receipts and exact artifact
manifest coverage (nonempty, no fixed item count). It also checks the four
services before/after the job and preserves logs. CI runs a new controlled
fixture request with exec_image=draft and a separate candidate adding Git and
strace. The original fixture stays unchanged. CI runs that new job as root to
match ECS/Compose snapshot ownership; no wildcard Git trust is added.
The new gate is a single-job success preflight, not a substitute for formal
paired inputs or the real-project timeout/recovery campaign.


## Controlled downstream timeout and recovery (development increment)

The optional request field downstream_full_timeout is valid only in
exec_image=draft mode, with numeric seconds in [1, 900]; omission preserves
the prior 900s full-check child budget. The DRAFT build budget is unchanged.
The broker reads the bound request bytes, not an arbitrary execute parameter.

Evidence-backed imgrunner operations now create one uniquely named container,
obtain its actual ID before starting it, preserve partial output on timeout,
inspect the child, remove only that child, and check absence by exact name.
An unconfirmed cleanup is a failure (not a successful timeout test).
A timed-out Docker create cannot be declared cleaned merely because the name
is momentarily absent; no start is attempted without a valid ID. This change
does not promise a hostile-code sandbox or change the historical no-evidence
runner interface.

real_job_fault_gate.py requires a prior successful real_job_gate result from
the same four services. It creates a new teaching repository derived from the
normal fixture: the base clean recipe writes a marker, sleeps, and would write
a second marker; the target tree is identical to the original target. The
original fixture is not edited. A 20-second outer child timeout interrupts the
50-second delay. The gate checks actual running inspect, exact image/mount/ID,
cleanup and host absence, original HTTP error identity and TIMEOUT propagation,
rejected replay, distinct successful recovery, no late writes after the
original delay, unchanged evidence, and service identities before/during/after.
A Git bundle of the derived fixture and raw requests are archived. This is a
controlled fixture fault preflight, not formal bilateral project acceptance.

Use the same request and candidate hashes, worktree, ports and Compose project
as the fresh success gate on the CURRENT source. Invoke from the host:

    python3 labs/e13e14/real_job_fault_gate.py \
      --request "$REQUEST" --request-sha256 "$REQUEST_SHA" \
      --candidate-sha256 "$CANDIDATE_SHA" \
      --success-out "$SUCCESS_OUT" --out "$FRESH_FAULT_OUT" \
      --project "$E14_PROJECT" --image "$E14_IMAGE"

The historical ECS success/scan/archive is bound to
2d8aef95f815882e1ca2439a7ba72fce51f0ecdc and is not evidence that this new
increment ran there. Archive /root/devops-materials/e14-pr28-241830217-20261124T140118Z.tar.gz
(144878 bytes, 492 entries, SHA256
28e24ac62725440eb6f2cb9e931b3eff2d1bf3b9ce1ad28c009064b4ea4ee608).
C supplied the ECS terminal record; independent archive verification by A is
pending. The new code and CI must be verified separately.
