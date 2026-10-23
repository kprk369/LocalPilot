# Startup and connection recovery

LocalPilot is a signed-in Windows-user service backed by one explicitly identified Hyper-V VM. The scripts must never select an arbitrary existing VM.

## Startup

- LocalPilot VM Start starts only the UUID recorded during provisioning, and verifies its name. It does not repeatedly restart a VM intentionally stopped by the operator.
- LocalPilot VM Address publishes that VM's private address under the protected ProgramData/LocalPilot directory at boot and periodically.
- LocalPilot Services runs the loopback backend and forwarding worker with normal user privileges after Windows sign-in. A process mutex prevents duplicates. No Windows password or auto-login is configured.
- Ollama runs locally; supervision can start its server if unavailable. Models are not automatically downloaded or changed.

The installer reads `.local/vm-created.json`, checks the actual VM, and embeds its UUID in protected scheduled-task arguments. The runtime reads that same installation's private identity, rejects mismatched discovery records, and keeps SSH host-key checking enabled. The guest firewall follows the current private Windows gateway rather than a historical static address.

## Controls

From the project root:

    .\scripts\manage_services.ps1 -Action Status
    .\scripts\manage_services.ps1 -Action Start
    .\scripts\manage_services.ps1 -Action Restart
    .\scripts\manage_services.ps1 -Action Stop

Stop/Restart refuses queued, running, paused, or approval-pending tasks. A deliberate Stop persists until Start. Do not launch a second backend/tunnel. Restart revokes browser sessions and marks unfinished tasks interrupted rather than replaying commands. If ownership cannot be confirmed, tools stay paused. After a full guest shutdown, connect to Desktop before requesting GUI work.

The Windows laptop must be awake, signed in, and online. Locking the session is supported; signing out stops user services. Keep Tailscale connected on iPhone. Sleep policies and automatic laptop reboot are not changed.

## Validation

Initial reboot testing exposed a stale guest firewall gateway rule. A gateway-aware refresh service/timer corrected it; subsequent restart/service checks and physical iPhone access passed. A separate backend interruption recovered in approximately 9.62 seconds. A controlled closure of only the pinned forwarding-only SSH child recovered in approximately 9 seconds with all then-existing task statuses preserved.

These are specific observed checks, not a guarantee for every network failure. A forced model crash, arbitrary changed-subnet outage, destroyed guest, and full disaster recovery have not all been tested. Local logs/status files are private under `.local`; use `python -m scripts.doctor` for a read-only check.

The startup installer/uninstaller requires appropriate Windows administration. Ordinary runtime code is not run as administrator. Existing installations do not need startup reinstallation merely because the source was cleaned for publication.
