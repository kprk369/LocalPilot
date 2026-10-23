# Approval-controlled software installation

Implemented on 23 October 2026. This is an initial, deliberately limited package capability for the LocalPilot VM.

## Phone flow

Ask to install tree, jq, ripgrep, or Firefox. The agent previews the requested packages and dependency versions, then shows Review software installation. Approve starts that plan; Reject stops the task without starting installation. The completed result includes verified installed versions. The phone can reload during review without losing the plan.

Current catalog: **tree, jq, ripgrep, firefox**. Firefox uses the official Mozilla signed APT repository configured during setup; see browser-control.md. jq was already present in this VM. tree was installed during QA. ripgrep was subsequently installed successfully in the user's approved phone test. Other tools require an explicitly reviewed catalog expansion; arbitrary sudo, repositories, package URLs, local deb files, APT flags, upgrades, and removals are not exposed.

## Permission boundary

The ordinary pilot account still has no sudo rights. It cannot modify the root-owned broker, SSH authorization, sudo policy, or root-only plan directory. The backend uses a distinct installer SSH key kept privately on Windows. The model, browser, and Linux pilot account do not receive that key or the setup administrator password.

The lp-installer identity has forced-command SSH, no PTY, no forwarding, password login disabled, root-owned authorized keys, and exactly one permitted sudo invocation: Python running the root-owned broker with its fixed script argument. Additional arguments and arbitrary shells were checked and denied. This capability trusts the Windows backend as the approval authority; possession of its private key grants the bounded broker operations. It is not a separate cryptographic attestation of a human browser click.

## Plans and execution

package_plan is read-only with respect to installed software. It simulates APT's actions, rejects removals/upgrades/unrelated configuration, and saves an immutable root-owned plan with a ten-minute expiry and SHA-256 fingerprint. It returns exact new package/dependency versions. The backend retrieves the authoritative plan for the approval screen; approval freezes the tool and arguments. package_install checks the fingerprint, expiry, and unused state before consuming the plan. Replays are denied.

A root-managed systemd job rechecks the pinned-version simulation immediately before installation, then executes fixed APT options and verifies installed versions. Only one broker install is accepted at a time. Existing trusted APT configuration and repository signing remain the package trust boundary; concurrent manual administrator changes are outside the broker's coordination. The runtime broker does not refresh metadata or add repositories. Setup configured the official Mozilla repository for Firefox only; the other catalog entries use the existing Ubuntu sources. Stale package metadata or unsupported dependency changes fail rather than expanding permissions.

The background job continues after phone disconnect, backend observation cancellation, or manual takeover. Cancel task stops the agent's observation; it does not terminate apt/dpkg or roll back packages already installed. package_status reads the saved outcome using the plan ID shown in task activity. A guest reboot interrupts a running package job and may need operator inspection; the broker does not claim safe continuation across reboot or automatically replay installation. Unfinished agent tasks remain interrupted after backend restart.

Implementation references: [Ubuntu APT simulation and install options](https://manpages.ubuntu.com/manpages/jammy/man8/apt-get.8.html), [systemd detached service execution](https://www.freedesktop.org/software/systemd/man/255/systemd-run.html).

## Verification

The full non-GUI regression run passed **41 tests**, with two GUI integration tests intentionally skipped and one upstream TestClient deprecation warning. Package tests cover strict catalog/payloads, expiry, fingerprint mismatch, single use, exact operator approval, rejection, and live read-only broker access. Earlier shared-desktop tests remain recorded separately.

Real model/browser flow over the private HTTPS address: sign in -> preview tree -> reject -> request a fresh plan -> approve -> install -> package_status -> complete. The rejected root plan remained unconsumed. The approved plan could not be replayed. Independently, tree --version and dpkg verification agreed on 2.1.1-2ubuntu3.24.04.2, while pilot sudo remained denied. Root policy modes and denied shell/worker-argument escalation were inspected.

Browser plugin not available; Edge/Playwright tested 430x932 and 1280x900 with normal HTTPS verification through a temporary QA tunnel. Page identity, meaningful rendering, absence of error overlays, zero JavaScript page exceptions, approval interaction, and screenshots passed. A visual check found an old-result race when switching tasks; generation guards fixed it. A fresh ripgrep preview/rejection check confirmed clean task selection and preserved approval after reload. Screenshots and JSON evidence are outside the repo in the LocalPilot visualization folder. The user confirmed that the ripgrep installation completes successfully on the physical iPhone after reviewing and approving the plan. Actual disconnection during a running install was not forcibly tested; background continuity follows the detached job design.

## Setup and disable

Provision with scripts/deploy_package_broker.py using setup credentials. Runtime loads only installer_key. To disable, remove the lp-installer SSH authorization/sudo policy through setup administration and remove installer_key from private runtime configuration, then restart idle services. Do not terminate a running package job. Existing installed packages and audit plans are retained. Expanding the catalog requires changes to both broker policy and the backend schema, followed by the same approval and live checks.
