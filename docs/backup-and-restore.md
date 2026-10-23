# Private backups and staged recovery

Implemented and validated on 23 October 2026. These are manual file-level recovery copies, stored locally under `.local/backups`. They are not automatic scheduled backups or full Hyper-V VM exports. TU is outside this tool.

## Included

- Project source, frontend, tests, provisioning scripts, dependency lists, and documentation.
- Task history, copied using SQLite's online backup API so committed WAL records are included consistently.
- Runtime/gateway settings, pinned VM identity metadata, startup metadata, and the credentials directory, including private SSH keys and login recovery information.
- Regular files and empty directories in `/home/pilot/Workspace`, exported read-only as pilot through the setup SSH identity with the pinned host key. Each file receives a SHA-256 digest. Symlinks and special files are omitted and listed explicitly; this avoids following the security-test links outside the workspace.

The setup SSH key/password are used only by this manual operator tool. No new privileged model tool or runtime approval bypass was added. It refuses to start while tasks are active. Avoid modifying workspace files during backup; per-file stability checks detect changes while copying, but this is not an atomic whole-VM snapshot. Limits are 1 GiB total workspace data, 256 MiB per file, and 100,000 entries. An interrupted/failed backup has no valid COMPLETE marker and must not be used.

## Privacy and limits

Backup and restore folders have protected Windows access rules for the current user and SYSTEM; copies of private keys inherit those rules. The files are **not separately encrypted** by this tool. SHA-256 checks detect accidental corruption; they do not authenticate an archive against deliberate replacement by someone who already has access. Never publish `.local`, upload these backups to a repository, or share them as a project download.

A backup on the same laptop does not protect against loss or failure of its drive. A protected external copy is needed for that. No cloud storage, paid service, recurring job, or automatic deletion policy was configured.

Not included: the VM disk/running state, installed Linux system and packages, Firefox profile/logins, Tailscale device identity, Ollama model weights, and Windows scheduled-task installation. This cannot by itself restore a destroyed VM or guarantee the same Tailscale URL on a replacement. A full VM export plus separately protected project backup is needed for that level of recovery. Rebuilding a VM requires deliberate provisioning and host-key/account enrollment; never disable SSH host verification to reuse old settings.

## Create and verify

From the project root:

    .venv\Scripts\python.exe -m scripts.backup create
    .venv\Scripts\python.exe -m scripts.backup verify "C:\full\path\to\backup-folder"

The command prints the backup path, verified counts, and omissions; it never prints credentials. Only a folder with a valid COMPLETE marker is complete. Verification reads the standalone database immutably and never writes sidecars into the backup. The archive and all copied files must match their manifests. Keep incomplete attempts separate; they are not recovery candidates.

## Restore into a separate inspection folder

    .venv\Scripts\python.exe -m scripts.backup restore "C:\full\path\to\backup-folder" "C:\Projects\LocalPilot\.local\restore-checks\new-folder"

The destination must not exist. Live project/configuration directories are refused. Staging restores the source and private state and unpacks workspace data into `restored-workspace`; it verifies the restored hashes and database. It does not execute restored code, replace the running database, change SSH keys, alter Windows services, or overwrite Linux files. Links, traversal paths, archive duplicates, special files, and Windows device-name/path aliases are refused. Linux filenames that cannot safely map to Windows stay recoverable in the verified Linux archive, but Windows staging refuses them rather than silently renaming them. Linux modes remain recorded in the archive; Windows inspection copies do not reproduce Linux ownership or executable permissions.

For actual recovery to the existing VM, first use this staging check and review the failure. Stop LocalPilot services only after tasks are idle. Preserve the current database and configuration before replacing anything; never overwrite a database while its backend is running. Recover only the selected files, retain the verified VM identity/host key, repair any absolute paths if the project moved, and restart through `scripts/manage_services.ps1`. Workspace restoration to Linux and live configuration replacement are intentionally manual operator actions, not implemented by this staging command. Recheck Linux ready, sign-in, history, and one harmless task before resuming normal use. Do not run provisioning or re-enroll keys merely to recover a deleted workspace file.

## Verified checkpoint

The completed backup `backup-20261023T123328Z-01d74a40` contained 111 checksummed components, 30 tasks, and 28 regular workspace files (2,588 bytes). Eleven symlinks from boundary tests were explicitly omitted. Staging into a new restore-checks folder passed: all workspace bytes and copied components matched, database integrity passed, and task count remained 30. Windows access rules on the backup and a restored private key were inspected: current user and SYSTEM only. The working app and VM were unchanged.

Thirteen focused regression checks cover exact binary restoration and history, refusing existing destinations, incomplete/corrupted copies, traversal, links, Windows filename aliases, and committed SQLite WAL data. A real first attempt caught verification-generated SQLite sidecars; the snapshot now uses DELETE journaling and immutable reads, and repeated verification of a WAL-format fixture is covered. That first attempt is explicitly marked incomplete and is not the validated recovery copy. A Windows PowerShell module mismatch was also corrected before credentials were copied. Full suite results are recorded in CHANGELOG.md.
