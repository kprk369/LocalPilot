# LocalPilot

A private Linux workstation you can use from your iPhone and operate with a local 27B AI model. Windows runs the AI on the laptop GPU; a separate Ubuntu Hyper-V VM provides the shared desktop, Firefox, and workspace.

Provisioning must create its own VM and never modify other existing VMs. Supported scope is **iPhone/iOS and the existing Ollama 27B model only**. Android, Strata, and model switching are excluded.

## Working features

- Private Tailscale HTTPS access and a dark Home Screen web app.
- AI file/terminal tasks, saved history, exact command approvals, rejection, and cancellation.
- Optional routine-command auto-approval with a saved toggle, Linux-enforced command list, and audit trail.
- Shared desktop screenshots and approved GUI actions, with Take control / Resume AI.
- Approved Firefox browsing and form input on the same desktop.
- Live Linux readiness beside Sign out.
- Approved catalog installation: tree, jq, ripgrep, firefox.
- Startup supervision, pinned VM address discovery, and private connection recovery.
- Restricted local file backups and verified restore into a separate inspection folder.

The user confirmed cellular desktop/AI access, GUI takeover, software installation, standalone iPhone launch, and Firefox browsing. The latest regression passed **109 tests**, with two opt-in GUI tests skipped and one upstream warning. A separate real-model evaluation passed **six of six selected practical tasks** with independently checked outputs. This small evaluation is not a general success-rate claim.

The system is a functional private MVP. Complex/unfamiliar GUI tasks, long coding sessions, clean-machine installation, full VM/off-device recovery, automatic browser updates, and security auditing remain outside the completed validation.

## Start here

- [Use, check, and troubleshoot the existing setup](docs/setup-and-operation.md)
- [Understand the architecture and permission boundaries](docs/architecture.md)
- [Practical task results and timing limits](docs/task-evaluation.md)
- [Reliability and connection recovery checks](docs/reliability.md)
- [Backup coverage and staged restore](docs/backup-and-restore.md)

From the existing project directory, run the read-only diagnostic command:

    .venv\Scripts\python.exe -m scripts.doctor

Daily operation requires the laptop awake, signed in, and online, with Tailscale connected on iPhone. Use the existing private app and credentials. Linux ready checks the guest/desktop, not website availability or model-loading time.

## Configuration and contribution

See [the example runtime configuration](config/runtime.example.json), [contribution guide](CONTRIBUTING.md), and [security notes](SECURITY.md). Copy no credentials or VM state into source control. The example intentionally has no usable token/password.

## Source and private state

`backend/` contains authentication, orchestration, approvals, persistence, inference, and SSH transport. `frontend/` contains the installable web app. `vm/provisioning/` and `scripts/` contain setup and operator utilities. `tests/` covers the tool, account, session, recovery, and backup boundaries.

`.local/` contains VM disks/media, keys, generated credentials, task history, screenshots, logs, evaluation evidence, and backups. It is ignored and must never be published. Generated installer media and local backups also contain private recovery information. No paid AI API or cloud hosting is configured.

## Further documentation

- [Routine-command auto-approval](docs/auto-approval.md)
- [Browser and readiness](docs/browser-control.md)
- [Software installation](docs/package-installation.md)
- [Startup and reboot recovery](docs/startup-and-recovery.md)
- [Home Screen behavior](docs/home-screen-app.md)
- [Backend development](docs/agent-backend.md)
- [Changelog](docs/CHANGELOG.md)

The setup guide explicitly distinguishes the tested current laptop from an unvalidated clean-machine rebuild. Do not rerun initial installation or one-time repair scripts to troubleshoot the working VM.

## Publication status

Source-only cleanup and known-secret checks passed. VM disks, credentials, runtime state, logs, backups, evidence, and historical development artifacts stay under ignored `.local/`. Run `python -m scripts.check_publication --archive` to create a verified source-only ZIP. No upload is performed by that command. A project license has not yet been selected.
