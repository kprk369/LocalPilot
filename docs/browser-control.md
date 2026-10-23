# Browser control and Linux readiness

LocalPilot can open HTTP/HTTPS URLs in Firefox on the shared Linux desktop, inspect screenshots, and request approved mouse/keyboard actions to navigate or fill forms. The user confirmed the workflow on iPhone, including a PlayStation website visit.

## Readiness beside Sign out

The authenticated `/linux/status` route checks the real pinned SSH connection, workspace writability, and usable shared XFCE desktop. It does not infer Linux availability from the web server responding. The frontend checks every 15 seconds; the backend shares results for five seconds. Ready means those checks passed at the last check, not a guarantee that every website or application will work. Other states explain a disconnected desktop, workspace attention, or an unreachable VM. Hover/title text includes the last check. Sign-out hides and clears the status.

## Browser and approvals

`desktop_browser_open` launches a fixed Firefox command/profile; URLs cannot contain credentials, control characters, or arbitrary command flags. Every browser launch and desktop input requires exact operator approval plus a current observation and ownership revision. Take control pauses AI actions. Browser page contents are untrusted input. Real external messages, purchases, and account changes require explicit user authorization; GUI approval is not blanket permission for unrelated actions.

The setup helper `scripts/prepare_firefox.py` configures Mozilla's HTTPS APT source, verifies signing-key fingerprint `35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3`, and pins only Firefox to that source. The package broker reviewed and installed Firefox 158.0.1~build1. It cannot add repositories, upgrade packages, or remove software. Browser updates therefore need operator maintenance; automatic updates are not implemented here. The normal Firefox sandbox remains enabled.

## Validation and limits

A fresh real-model local form task completed using five approved inputs and eleven desktop tool steps. An independent local HTTP server recorded the submitted test value. Unreachable-page reporting and subsequent public Example Domain navigation also passed. The temporary form server is stopped. The earlier model-context failure led to a 16,384-token context and compaction of superseded desktop observations; the successful task peaked at 5,063 prompt tokens. A terminal regression caused by Firefox threads was fixed by increasing the pilot process allowance to 2,048; sudo restrictions remain unchanged.

Final regression: 41 passed, two opt-in GUI tests skipped, one upstream Starlette TestClient warning. Separate live GUI checks used the actual private HTTPS address, Edge/Playwright, normal TLS verification, and widths 320/430/1280. Browser plugin was unavailable. Ready was checked against the real VM; offline/disconnected/attention displays were simulated. Screenshots and private task evidence remain outside tracked source.

This is an initial browser capability: complex sites, CAPTCHA, downloads/uploads, authentication, and long workflows are not comprehensively validated. Linux ready does not guarantee the AI model is loaded or a particular website is reachable. The Windows laptop, VM, Tailscale, and local services must remain available. Inference uses only the existing Ollama 27B model; Strata integration and model switching were removed from scope at the user's request.
