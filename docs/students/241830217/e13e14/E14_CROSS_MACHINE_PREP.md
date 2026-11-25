# E14 cross-machine preparation — 241830217

Status: proposed, not a deployed service and not formal bilateral acceptance.
Baseline PR #28 84cc47fbd21948fb286e12cc4c49f527112a17ee has independent CI/ECS
preflight evidence. This increment must not relabel those old runs as its own.

## Access agreement (pending B13 response)

Record the actual connector, public-key fingerprint, two time windows with
timezone and end times, exact role-to-loopback mapping, independently pinned
source/request/candidate/profile identity and the permitted operations. No
private SSH key or session credential in Git, chat logs, command lines,
environment dumps, Docker inspect or evidence archives.

Do not grant root shell, Docker group, unrestricted TCP forwarding or access
to raw role APIs. The server administrator must use a dedicated unprivileged
temporary SSH identity, public-key-only authentication, AllowTcpForwarding
local, exact PermitOpen loopback destinations, no shell/subsystems/PTY/agent/
X11/tunnel, expiry and explicit session termination. Validate effective sshd
Match settings and actual denial/allowance using the agreed key before opening
the formal window. Key expiry alone does not terminate an existing SSH
connection. No changes to the server's existing root account or other groups'
authorized_keys. Confirm SSH host key fingerprint out of band. Remove the
temporary identity/access at the end, check port closure and retain redacted
authorization/revocation observations. This document does not apply changes.

## Proposed access surface (requires bilateral agreement)

Keep the four existing Compose roles on their private loopback ports.
The raw DRAFT /v1/execute and role /v1/run are trusted local interfaces, NOT
safe remote API endpoints; they accept project/output paths and build input.
pair_session.py exposes a distinct loopback listener per agreed role:
authenticated /health and /v1/session only. No forwarding of mutation
requests. For C8 use a separate agreed temporary listener and a fresh
dedicated E11/E12 async Store with a private loopback upstream. Do not include
backend ports in PermitOpen. Stop the gateways at the deadline and revoke SSH.

The async listener accepts one exact approved E12 input (strict JSON,
canonical semantic comparison) and one idempotency key; the same key may
replay or submit precisely the reserved all-zero target conflict. All other
requests fail closed, and reads are limited to that Job and manifest-listed
artifacts. It forwards actual upstream 202/409 and downloads, checks bytes
and hashes, and never writes the credential. A lost POST response reserves
the same key; restart is NOT resumable (stop the session and reconcile its
Store before opening another). The deadline blocks new requests, not an
already-running server job. Use only a staged, trusted course repository,
a read-only operator-approved candidate/profile and fresh private Store.
The gateway is not a hostile-code sandbox, not internet-facing, and does
not prove deployment identity simply from declared pins.

Start each listener on an agreed unused loopback port with:
    python3 labs/e13e14/pair_session.py --role ROLE \
      --listen-port GATEWAY_PORT --upstream-port PRIVATE_PORT \
      --approved-request REQUEST --request-sha256 REQUEST_SHA \
      --candidate-sha256 CANDIDATE_SHA --source-commit SOURCE_SHA \
      --expires ISO8601_WITH_TZ --credential-file PRIVATE_FILE

Credential file outside /course and work/evidence, owner-only mode 0600,
generated using cryptographic randomness and privately exchanged. Never use
a real credential as a CLI argument or include it in the archive. Verify
the actual deployed source, upstream service IDs and candidate/profile bytes
before startup. The async API must not be accessible on the raw backend port
through the authorized SSH account. Separate the private Store from prior
experiments. The gateway intentionally accepts no client-provided URL, path
to a local file, role command, arbitrary patch or Docker action.

Client (after SSH authorization and agreed port mapping):
    python3 labs/e13e14/pair_c8_client.py --port LOCAL_API_PORT \
      --request REQUEST --request-sha256 REQUEST_SHA \
      --candidate-sha256 CANDIDATE_SHA --source-commit SOURCE_SHA \
      --out FRESH_CLIENT_OUT

The client prompts without echo, records request/response bodies and selected
headers (never Authorization), proves actual 202 replay and 409 conflict,
polls a new Job, downloads every manifest entry and checks SHA256/bytes,
verifies stage envelopes and nested artifact references, and retries after
completion. Client receipt is not the server job-count proof: server must
independently verify exactly one new Store entry, actual exec/inspect,
source/image/profile and original artifact bytes, and exchange archive
digests. No peer signature is inferred from a local CI run.

## Synchronous E14 and C4/C5

Pending agreement on the remote invocation model. Prefer an operator-owned
fixed campaign using the existing host orchestrator, not unrestricted
remote role writes. Retain six original HTTP exchanges for five stages,
source/request/candidate/profile pins, stage reports and all exec/inspect.
Agree how the peer independently observes/initiates the campaign and obtains
originals. Four health probes alone are not a synchronous five-stage receipt.
C4 use actual bounded timeout cleanup and new-job recovery. C5 must use B's
approved bad patch in an isolated snapshot, prove real validation rejection,
rollback and original Makefile hash, then run a new normal job. Never weaken
the DRAFT broker's exact generated patch check to permit arbitrary injection.
B's full-project make all + independent run case and repair scope remain
pending. No deployment, SSH authorization or token exchange performed by
this increment.


## Guarded real API regression

The E13 explicit-input regression can select --guarded-c8. It starts the
original private Docker API with a fresh Store; the client executes through
a distinct loopback session listener. The server checks one Store entry,
actual DRAFT exec/inspect and every downloaded artifact against the original.
CI generates a credential in memory and checks that it never occurs in
client originals. This is local real Docker validation, not SSH or B13
acceptance. The CLI additionally checks clean tracked source, candidate
bytes and both full Git commit objects before startup.


## Four-role health receipt, relocated synchronous originals, and C5

pair_health_client.py checks the four agreed local forwards independently,
including unauthenticated rejection and blocked raw role write routes.
It produces a health-only receipt and does not claim a five-stage job.

pair_sync_audit.py reuses the E14 success verifier on a copied job directory
with independently supplied original /course/work job URI, host bind path,
candidate original and expected request/candidate/source hashes. It verifies
the same five stages, six HTTP originals, reports, receipts and actual
exec/inspect without replaying requests or changing the originals. The
source record is a declared identity, not cryptographic proof of the
server's running code. Run the peer auditor on Linux/WSL.

pair_c5_gate.py is a controlled, operator-only validator preflight. It
derives a wrong dependency from the original verified good patch in a
fresh C1 clone, invokes B's existing validate inside the verified DRAFT
service with the actual successful image, and requires build/test/header
checks to pass but missing main.o -> extra.h to remain. It checks rollback,
unchanged tracked source, actual child inspect and new successful five-stage
recovery without restarting services or changing prior evidence. It does
not add an HTTP bad-patch injection endpoint or change B's algorithm.
The formal C5 project/patch/expected missing set must be approved by B,
and the formal remote invocation arrangement remains to be agreed.


## Proposed SSH plan generation and real role-health regression

Once B13 confirms the actual connector, public key, two time windows and
all ports, create a private JSON file with schema_version e14-access-plan-1,
connector, ssh_user, ssh_host, windows (two {start,end} ISO8601 values with
timezone), and ports (four role keys, plus api only if approved, each
{backend,gateway,client} integer). Use the real public key file:

    python3 labs/e13e14/pair_access_plan.py \
      --plan PRIVATE_PLAN_JSON --public-key PEER_PUBLIC_KEY --out NEW_PRIVATE_PLAN_DIR

The generator checks the public key fingerprint using ssh-keygen, rejects
root, overlapping windows and server/client port collisions, produces a
proposed Match block and two separate proposed key lines with UTC expiry.
It does not install anything or prove the account is unprivileged.
Inspect effective sshd settings and test with the actual authorized key;
install ONLY during the selected window, terminate existing sessions and
remove access at the end. Key expiry has no not-before guarantee and
does not terminate existing sessions. Do not add unapproved ports.
pair_health_gate.py exercises the four distinct authenticated loopback
gateways against actual Compose roles in CI and compares service identities.
The private gateway CLI rejects credential files under the course root;
the client will not fall back to echoed credential input.
