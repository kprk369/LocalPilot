# Reliability checkpoint - 23 October 2026

Current scope: iPhone/iOS, with the existing Ollama 27B model only. Android, Strata, and model switching are excluded.

## Real-model task checks

The repeatable runner is `scripts/reliability_check.py`. Run it from the project root with `.venv\Scripts\python.exe -m scripts.reliability_check`. It refuses an active queue or human desktop ownership, uses a unique integration-tests workspace folder, grants no approvals, and cancels only its own tasks. Evidence is private under `.local/reliability/`. Successful file results are independently read through the restricted execution channel rather than trusting the model's reply.

| Case | Final state | Elapsed | Result |
| --- | --- | --- | --- |
| unicode_file_roundtrip | completed | 16.89 s | Pass |
| multi_step_files | completed | 17.44 s | Pass |
| reject_pending_command | rejected | 3.67 s | Pass |
| cancel_pending_command | cancelled | 2.62 s | Pass |

The Unicode test wrote and verified exact UTF-8 content. The multi-step test wrote/read four source files and a sum file: ten successful tool results, with all five exact contents independently verified. The rejection and cancellation cases reached real terminal approval prompts; neither started a terminal tool or created its marker file.

These are single-run timings with the already available local model, not cold-start performance statistics or broad success-rate claims. No production browser/desktop actions were injected by this runner. It leaves its harmless QA files for inspection.

## Command and package boundaries

The regression run passed 40 tests with three opt-in tests skipped (two GUI and the separate package-channel check), plus one upstream Starlette TestClient deprecation warning. The live package-channel test was then enabled and passed separately: 41 passing tests across the two invocations, with the two GUI checks intentionally omitted. No installation was performed. Tests include terminal deadlines, bounded output, cancellation of a running process before its delayed marker is written, pre-start cancellation, workspace boundaries, no sudo, immutable approval payloads, and restart reconciliation without replay.

## Private connection recovery

While the task queue was idle, the test selected exactly one SSH process by its forwarding port, gateway account, pinned host alias, and expected LocalPilot gateway-worker parent. It interrupted only that forwarding child. The normal worker restored access in approximately 9.0 seconds, measured from before process selection through a successful guest-to-backend probe. The backend's authenticated route returned its expected unauthenticated 401 through the repaired tunnel; authenticated local health and real Linux readiness subsequently passed. All 30 saved task statuses matched their pre-test values. The backend, VM, and desktop were not restarted. The initial test guard rejected Windows path separators before stopping anything; correcting that guard enabled the test.

This checks a deliberately closed transport process, not a ten-minute internet outage, changed subnet, full guest crash, or forced model crash. Earlier user laptop restarts and recovery are documented separately in startup-and-recovery.md. A new physical iPhone test was not requested for this internal checkpoint.

## Remaining work

Prepare and verify private backups and recovery instructions; run a broader representative task set; document reproducible setup and known limitations. Keep the supported phone target iOS. Browser security updates still need operator maintenance. The laptop must remain awake, signed in, and online.
