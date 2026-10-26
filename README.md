# 2026 DevOps A13

This repository is used for the 2026-Fall DevOps course project conducted by ISE, Nanjing University.

A13 is responsible for **BuildChecker** and **EChecker**. Paired group B13 is responsible for **DRAFT** and **MDFixer**.

## E2

Key files:

- `docs/E2/B13_DELIVERY.md`: A13 -> B13 contract delivery and point-by-point reply.
- `docs/E2/A13_E2_INTERNAL_GUIDE.md`: detailed internal guide for A13 members.
- `docs/E2/PAIR_REVIEW.md`: pair-review decisions and unresolved items.
- `docs/E2/BACKLOG.md`: remaining work and acceptance criteria.
- `docs/E2/ADR-*.md`: design decisions for the E2 contract.
- `contracts/schemas/`: A13-owned schemas.
- `contracts/examples/`: valid/invalid examples.
- `contracts/artifacts/`: repository-backed E2 sample artifacts.
- `scripts/validate_e2.py`: offline semantic validator.
- `tests/test_e2_contracts.py`: contract tests.

Pinned B13 proposal: `ma058/2026-Devops-B13` at commit `af194c40ffd1394fb56cc9f5b2367b7feffb5a3b`.

E2 examples are **synthetic contract fixtures** and not evidence that all production services have been reproduced.

## E3

See [E3 README](docs/E3/README.md) for the C0/C1/C2 test baselines and evidence, and [review](docs/E3/REVIEW.md) for current review/acceptance status.

## E4

See [E4 README](docs/E4/README.md) for the BuildChecker environment template, `make all` workflow, and isolated evidence.

## E5

The 2026-10-20 teaching reference and adaptations are recorded in [E5 source manifest](docs/E5/source-manifest.json). The [E5 report](docs/E5/实验报告.md) identifies member 241830088's real runtime SHA and trace. An [A13 → B13 handoff](docs/E5/B13_HANDOFF.md) and [raw evidence](evidence/E5/241830088/README.md) are retained.

## E6

Responsible branch: `e6/241870063-mvp` (student ID 241870063). On the A13 course server, `full-check` detected MD(`main.o`, `config.h`) and RD(`main.o`, `unused.h`) on the original `md-rd` fixture, and returned `findings=[]` after repairing only the Makefile in an isolated copy. One added service test (16 passed) and the A gate (8/8) were rerun on the rebuilt image.

E6 report: [`docs/E6/实验报告.md`](docs/E6/实验报告.md); raw evidence: [`evidence/E6/241870063/`](evidence/E6/241870063/README.md).

## E7 — BuildChecker validation

Responsible study branch: `e7/241830217-reproduction` (student ID 241830217).

- [E7 status and run commands](docs/E7/README.md)
- [E7 experimental submission report](docs/E7/实验提交报告.md)
- [E7 acceptance matrix](docs/E7/验收记录.csv)
- [GitHub Actions evidence index](evidence/E7/241830217/ci-40154562661/README.md)
- [Team handoff and pending collaboration](docs/E7/组内交接与后续安排.md)
- [Course-server environment compliance confirmation](docs/E7/课程云服务器环境合规确认.md)

On GitHub-hosted `ubuntu-24.04`, [CI run #40154562661](https://github.com/Dufunare/2026-Devops-A13/actions/runs/40154562661) at `76a8f004e61560edc3f1d77a6c51fb2113413cc4` passed 15 service tests, 11 independent tests, all 8 E7 scenarios, and the saved-evidence audit. **This is not a claim of execution on the assigned course cloud server.** Course-server substitution is pending teacher confirmation, and protected-branch rejection/recovery PR evidence is still pending.

The large `docs/tmp-references/` teaching/reference upload has been removed from the **current E7 tree**. Its source identities and E7 applicability are summarized in [course source index](docs/E7/课程材料来源索引.md); pre-cleanup Git history has not been rewritten.
