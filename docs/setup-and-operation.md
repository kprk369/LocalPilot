# Setup and daily operation

This guide describes the working installation on this Windows laptop and a reviewed rebuild sequence. Existing-machine operation is tested. A clean installation from only a public source checkout has not been tested and is not claimed as one-click reproducible: host-key enrollment, media preparation, and private network/settings enrollment remain operator steps. Do not rerun initial provisioning to repair a running installation.

## Use it from your iPhone

1. Keep the Windows laptop awake, signed in, and online. Locking its signed-in session is supported; signing out stops its user services.
2. Keep Tailscale connected on your iPhone. Open the LocalPilot Home Screen icon or the existing private HTTPS address.
3. Sign in as localpilot using your existing private phone login. Desktop authentication may be requested separately inside the Desktop tab.
4. Wait for Linux ready beside Sign out. If AI is paused, tap Resume AI. After a full guest shutdown, open Desktop and connect to establish the shared XFCE session first.
5. Submit a task, inspect approvals, and watch results. Take control pauses LocalPilot tools before manual desktop interaction. Resume AI hands control back.

Suggested starting tasks: organize text files, summarize a small CSV, fix/run a small Python script, or open a public website. Review code and commands before approving. Cancel does not undo completed changes; a package installation already started continues safely in the background.

## Laptop diagnostics and controls

Open a terminal in `the project folder`:

    .venvScriptspython.exe -m scripts.doctor
    .scriptsmanage_services.ps1 -Action Status

Doctor reads configuration presence, pinned alias, authenticated backend/Linux/control checks, installed 27B model, task database integrity, and recent supervision status. It does not restart services, load the model, run commands in Linux, or test iPhone connectivity. Human ownership can be healthy; Resume AI is still needed for tasks.

Ordinary service controls:

    .scriptsmanage_services.ps1 -Action Start
    .scriptsmanage_services.ps1 -Action Restart
    .scriptsmanage_services.ps1 -Action Stop

Stop/Restart refuses active tasks. Do not launch a second backend/tunnel when supervision is installed. A deliberate Stop persists until Start. Browser sign-in is needed again after a backend restart. Never print `.local/runtime.json`, credential files, or process environments when sharing diagnostic information.

## Troubleshooting

| Symptom | First checks |
| --- | --- |
| App unavailable on cellular | Laptop awake/signed in/online; Tailscale connected; then local Doctor/Status |
| 502 gateway error | Backend and forwarding worker; published VM address and gateway-aware guest SSH firewall; allow recovery time |
| Linux offline while app loads | VM/SSH and pinned address/key; do not disable host-key checking |
| Desktop disconnected | Open Desktop and establish the Linux session, then wait for the next status poll |
| Linux ready but AI paused | Resume AI after finishing manual work |
| Slow first task | Local model may need to load; GPU/memory pressure can affect it |
| Approval stale after takeover | Observe again and request a new approval; old actions must not be replayed |
| Unsupported package | Current catalog is tree, jq, ripgrep, firefox; review source-policy expansion separately |
| New task interrupted after restart | Resubmit deliberately after inspecting history and files; no automatic replay |
| Browser version needs updating | Operator maintenance is required; runtime broker does not perform upgrades |

Read local logs under `.local/logs` when needed; they may contain private task information. See startup-and-recovery.md for the actual reboot/firewall history and backup-and-restore.md before replacing files.

## Rebuild map: operator-reviewed, not a tested fresh installer

Other existing VMs must never be selected or modified. Existing LocalPilot must never be overwritten by initial-install scripts. Preserve a validated backup first. The following lists the source components and dependencies, not permission to reinstall this laptop.

| Stage | Source and prerequisites |
| --- | --- |
| Windows preparation | Windows 11 Pro/Hyper-V, Default Switch, OpenSSH client, Python 3.12, Ollama/GPU runtime; create `.local/logs`, `.local/downloads`, `.local/credentials` privately |
| Python environment | Create `.venv`; install requirements-dev.txt, which includes requirements.txt. Initial ISO generation additionally needs pycdlib; the builder currently uses `.local/python-packages` and Git's fixed Windows OpenSSL path |
| New VM | Elevated vm/provisioning/New-LocalPilotVM.ps1 creates a new isolated LocalPilot, refuses an existing VM/disk, and records its identity |
| Ubuntu media | vm/provisioning/build_installer.py expects the recorded Ubuntu 24.04.5 ISO and pinned SHA-256, creates private credentials/media, refuses an existing target. Obtain/verify the intended release separately; old generated installer media must not be reused |
| Initial install | Elevated Install-LocalPilotUbuntu.ps1 verifies the recorded VM and empty disk, installs, detaches media; Watch-LocalPilotNetwork.ps1 records networking. Review each script's preconditions |
| SSH enrollment | Validate the installed guest and host key through trusted setup; establish the stable localpilot-vm alias. Identity/IP metadata and keys are private, not source defaults |
| Shared desktop | vm/provisioning/guest_setup.py check and provision; sets up XFCE/xrdp and Guacamole containers without granting pilot sudo/Docker membership |
| Private network | Install/enroll Tailscale on VM and iPhone to the same account, enable private HTTPS, establish desktop session; current working URL is account/device specific |
| Restricted execution | scripts/deploy_executor.py installs root-owned dispatcher and a separate pilot key, initializes private runtime settings |
| Browser authentication | Runtime must include salted password_hash from backend.auth.password_hash, auth_username, exact public_origin, strong operator token, stable host_key_alias, and private key/database paths. Existing hashes/settings must be retained rather than blindly regenerated |
| Private gateway | scripts/deploy_web_gateway.py provisions the forwarding-only identity/nginx. Preserve the stable host alias in gateway.json. Start backend/transport, verify locally, then activate_web_gateway.py selects the combined private route |
| Software capability | deploy_package_broker.py installs the separate bounded broker/key. prepare_firefox.py verifies/prepares Mozilla's source; Firefox itself is installed via preview and approval |
| Boot/address recovery | install_startup.ps1 takes the intended Windows user SID and installs protected discovery/start tasks plus a limited user supervisor. The created VM UUID is read from private metadata and pinned in the installed task arguments |
| Validate | Doctor, regression suite, real task evaluation, iPhone cellular/desktop/approval/takeover, restart recovery, private backup and staged restore |

VM discovery reads the private creation record and rejects a different VM identity; installed protected discovery tasks receive that identity explicitly. Changing an IP is supported; replacing a VM requires reviewed identity/key enrollment. Historical one-time repairs and development patch scripts are archived privately and are not needed to run current source.

## Validation commands

    $env:LOCALPILOT_INTEGRATION='1'
    $env:LOCALPILOT_PACKAGE_INTEGRATION='1'
    .venvScriptspython.exe -m pytest -q
    .venvScriptspython.exe -m scripts.task_evaluation

Live integration tests write unique QA files. The package-channel integration test previews/denies plans without installation. Desktop-input tests require the separate LOCALPILOT_GUI_INTEGRATION flag and should only run when nobody is using the shared session. The practical evaluator may approve only its fixed, independently checked harmless Python program; it does not broadly auto-approve commands.

Task evaluation and diagnostics are manual commands, not scheduled monitors. Scope remains iPhone/iOS and one existing local 27B model. No paid AI provider or hosting service is required by this implementation. A new-machine build, full VM/off-device recovery, a broader repeated benchmark, automatic security updates, and a security audit remain separate work.

## Optional routine auto-approval

Agent now includes a saved off-by-default Auto-approve routine commands switch. See auto-approval.md for the exact permitted grammar. Script execution, installs, destructive/compound commands, and desktop input still require review. Auto-approved steps are visible in activity; existing prompts are not automatically consumed.
