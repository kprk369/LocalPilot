# Agent backend development checkpoint

## Start and operate locally

Use a Python 3.12 environment and install `requirements-dev.txt`. The runtime configuration belongs in `.local/runtime.json`; never commit it. It contains the API token, model tag, loopback Ollama address, database path, VM address, restricted agent key path, and dedicated known-hosts file.

Start the backend from the repository root:

    .venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8765 --no-access-log

The local operator client supports `models`, `new`, `show`, `events`, `approve`, `reject`, and `cancel`:

    .venv\Scripts\python.exe -m backend.cli models

The CLI reads the private API token locally. It never sends that token to the model or VM. An approval specifies the pending task ID and approval ID, and applies only to the exact reviewed command. Approvals are not reusable.

## Permission boundaries

The setup helper uses administrator credentials only for provisioning. `backend/` uses a separate pilot key. The guest SSH service forces `/usr/local/lib/localpilot/executor.py` and denies port forwarding and interactive PTYs for pilot. Program files and SSH authorization are root-owned. Code execution runs as pilot with limited resources and no sudo privileges. Approved code can access that user's own files and network; this is an account boundary, not a hardened per-command filesystem sandbox.

File tools are confined to relative workspace paths. Shell commands always wait for explicit authenticated operator approval. The model has no approval tool. A separate restricted installer key now reaches a root-owned broker for approved tree, jq, ripgrep, and Firefox plans; see package-installation.md. Pilot sudo permissions are unchanged.

## State and limits

One task runs at a time, with up to eight queued/active requests. Each task has at most sixteen model turns and eight tool calls per turn. Shell commands have a maximum sixty-second deadline and 64 KiB returned output. Pending approvals expire after five minutes. Cancellation kills the remote process group, including background descendants. Cancel markers cover requests cancelled before remote startup.

Task summaries and event history persist in SQLite. Interrupted tasks do not resume or replay commands automatically after restart. The backend listens on Windows loopback and is privately routed to the mobile app through the restricted SSH transport. Mobile approvals, GUI tools, and takeover are implemented. Normal-user startup supervision and backend/transport recovery are implemented; the second user restart passed service checks. The initial package broker is implemented; broader privileged operations remain outside its scope.

## Validation

    .venv\Scripts\python.exe -m pytest -q

Live tests are opt-in and operate only in the configured LocalPilot guest:

    $env:LOCALPILOT_INTEGRATION='1'
    .venv\Scripts\python.exe -m pytest -q

The auto-approval checkpoint regression passed 104 tests with two opt-in GUI tests skipped. Actual browser GUI workflows were validated separately; see browser-control.md. Enable LOCALPILOT_GUI_INTEGRATION=1 as well to include GUI input checks against the shared session. Real model-driven terminal and folder-opening tasks completed with independently checked results. One upstream TestClient deprecation warning remains.

The active inference configuration uses only the installed Ollama 27B model with a 16,384-token context. Older desktop observations are compacted while preserving the latest screenshot and current state. Shell process allowance is 2,048 because Linux counts the shared Firefox threads against the pilot account; time, memory, output limits, and no-sudo policy remain in force. Strata and model switching are explicitly out of scope per the user.

Optional routine auto-approval supersedes the general terminal-review rule only for its fixed grammar; see auto-approval.md.
