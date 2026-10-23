# Optional routine-command auto-approval

The operator controls a persistent opt-in toggle. A fixed command list is enforced in Linux, and automatic decisions are logged in task activity.

## Use on iPhone

Refresh or reopen LocalPilot and sign in. In Agent, enable **Auto-approve routine commands**. The setting is initially off and is saved across reloads and backend restarts in the private task database. It is shared by sessions of this single-user installation. Turn it off to return all terminal requests to review. Changing it does not consume existing approval prompts, replay old commands, stop commands already started, or override Take control.

Every automatically permitted terminal action appears as **Routine command · auto-approved** in activity, with the result and policy identifier. Persisted audit events include the exact tool/arguments and SHA-256 payload fingerprint. The model cannot change the setting through its tools.

## Exact routine-v1 scope

| Command | Permitted form |
| --- | --- |
| pwd, whoami | No arguments |
| python3 --version | Version only; no script/module/code execution |
| echo | Literal arguments, no leading-option arguments or shell syntax |
| ls | Optional -a, -l, -la, or -al; one relative workspace directory, default dot; at most 200 entries |
| cat | One relative regular workspace file |
| head, tail | Optional -n with count 1–200; one relative regular workspace file |
| wc | Optional -l, -w, or -c; one relative regular workspace file |
| mkdir | Optional -p; one relative workspace directory path |

File reads and returned output are limited to 64 KiB. Quoted spaces in paths are supported. Command separators, pipes, redirects, substitutions, control characters, wildcards, environment assignments, external/parent paths, and unknown options require normal manual review. Commands that meet the grammar but fail the guest's path/file/size checks fail closed; they are never retried automatically through a general shell. Symlink escapes and special-file reads are rejected. mkdir makes folders only; it cannot delete or change existing content/permissions.

Scripts (including Python), installs, network utilities, git operations, deletions, shell combinations, and every desktop input still require operator approval. Existing file tools remain governed by their existing workspace rules. The earlier requirement to review all shell commands is superseded only by this explicit routine policy when enabled.

## Enforcement and boundaries

The backend classifies only terminal_execute requests and checks the current saved preference again immediately before dispatch. An eligible request is routed to the internal terminal_routine dispatcher, not terminal_execute. The deployed root-owned routine_commands.py re-parses the same narrow grammar and implements operations directly with bounded Python file APIs. It never launches Bash, arbitrary programs, or model-generated Python code. The internal dispatcher is not available in model tool schemas. If classification differs or guest validation fails, there is no fallback to an unreviewed shell.

Authentication, strict boolean settings validation, same-origin browser writes, manual-control ownership, cancellation, and package/GUI approval remain active. A previously pending approval stays pending when the preference changes. The runtime/backend and its SSH keys remain the approval authority; this is not a hardened boundary against the trusted Windows user or a compromised backend. The existing pilot account boundary still permits approved code its own files/network.

## QA report

Summary: real private-app checks passed for enabling/reloading, auto-running pwd, requiring review for python3 --help, disabling/reloading, and requiring review for pwd again. No arbitrary command was approved in this QA; the non-routine request was rejected and the final pending pwd request was cancelled. The setting was returned to **off** after testing, as agreed.

Environment: actual private HTTPS origin using Edge/Playwright through a temporary pinned SSH SOCKS tunnel and normal TLS verification. Browser plugin not available. Widths 320, 430, and 1280 had no horizontal overflow. Physical iPhone Safari confirmation of this new toggle is not yet claimed.

| Check | Result |
| --- | --- |
| Intended URL/title and meaningful app content | Passed |
| Blank page/framework overlay | None observed |
| JavaScript page exceptions | Zero |
| Console errors | Two expected unauthenticated 401 responses around session lifecycle; no other errors |
| Toggle persistence on reload | On and off both passed |
| Model routine command | Completed with auto_approved audit, no approval_requested event |
| Non-routine command while enabled | Paused for exact review; rejected without execution |
| Routine command while disabled | Paused for review; cancelled without execution |
| Sign-out | Setting control hidden and disabled |
| Screenshot review | Dark UI, readable toggle/explanation, and audit activity visually inspected |

Full regression: **104 passed, two opt-in GUI-input tests skipped, one upstream Starlette TestClient deprecation warning**, 23.48 seconds. Policy tests cover shell injection, unknown tools/flags, external paths, size bounds, persistence, strict/authenticated/origin-checked preference changes, existing approvals, and package/desktop review. Live guest checks verified allowed file/folder operations, escaping-symlink/script/operator rejection, no redirected marker creation, and root ownership/mode 644 with no pilot write access to the deployed module.

Evidence: routine-approval-qa.json and routine-enabled-mobile.png, routine-result-mobile.png, routine-disabled-mobile.png in the LocalPilot visualization folder. The temporary browser script was outside source and removed afterward; its owned tasks were cleaned up without cancelling other work. No VM reboot or TU change occurred. This is a fixed initial grammar, not a claim that every harmless shell command can be recognized automatically.
