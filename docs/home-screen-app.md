# Home Screen app

LocalPilot now has a dark monochrome interface and installable web-app metadata: stable identity/start URL/scope, standalone display, matching theme/background, 192/512/maskable icons, Apple touch icon, and legacy Apple standalone metadata. The LP monogram is code-native typography; no external font/CDN or paid service is required.

## iPhone

Open the private URL in Safari. Tap Share, Add to Home Screen, leave Open as Web App enabled if shown, then Add. Open LocalPilot from the new icon and sign in if requested. Install app in the footer opens the same guidance. The user confirmed that the installed dark app opens correctly without the Safari address bar.

The laptop must remain awake, connected, and signed in; Tailscale must be connected on the phone. Installation does not turn the phone into the Linux host. Tasks continue on the laptop/VM while the phone is backgrounded; returning to the app reloads/reconnects to saved task history. Push notifications and background sync are not implemented.

On iOS, Home Screen web apps can have separate cookies/storage from Safari, so a new sign-in is normal. The install entry hides in standalone mode. Supported phone scope is iPhone/iOS; other platform installation is not part of the current validation.

Apple/WebKit references: [current iOS 26 Home Screen behavior](https://webkit.org/blog/17333/webkit-features-in-safari-26-0/), [standalone manifest and app storage](https://developer.apple.com/videos/play/wwdc2023/10120/).

## Offline behavior and privacy

The root-scoped service worker caches only public reconnect HTML/CSS/JS and icons under localpilot-public-v1. It never caches the authenticated app document, app JS, API responses, task history, credentials, screenshots, or Guacamole traffic. It does not queue or replay requests. Opening the app without connectivity, or during an upstream server error, shows reconnect guidance and Try again. Authenticated operations still require a live connection and the same session/origin protections as before.

Updates use normal network requests for app code and API data. The worker updates without automatically reloading a live task. Future changes to cached public offline assets should bump the public cache version; activation removes only this app's previous public-cache namespace. Logout revokes the backend session; offline caches contain no private task data.

## Verification

See the project README for current validation scope. 28 tests passed with two suite GUI checks skipped; a real browser flow separately verified desktop takeover. Normal-profile browser installability had no errors. Offline/online transition, cookie revocation, public-only cache contents, icon dimensions, and real approvals passed. The user confirmed physical iPhone Home Screen installation and dark standalone launch.
