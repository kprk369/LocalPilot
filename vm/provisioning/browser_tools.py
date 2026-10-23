"""Shared URL validation and fixed Firefox launch configuration."""
import json
from pathlib import Path
from urllib.parse import urlsplit

def browser_url(value):
    if not isinstance(value,str) or not 1<=len(value)<=2048 or any(c.isspace() or ord(c)<32 or ord(c)==127 for c in value):
        raise ValueError('Use a complete HTTP or HTTPS URL without spaces or control characters')
    parsed=urlsplit(value)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username is not None or parsed.password is not None:
        raise ValueError('Only HTTP/HTTPS websites without embedded credentials are supported')
    if parsed.port is not None and not 1<=parsed.port<=65535:raise ValueError('Invalid website port')
    return value

def firefox_command(url):
    url=browser_url(url)
    binary=Path('/usr/bin/firefox')
    if not binary.is_file():raise ValueError('Firefox is not installed. Request an approved firefox package plan first.')
    profile=Path.home()/'.local/share/localpilot/browser'
    profile.mkdir(parents=True,exist_ok=True,mode=0o700)
    prefs=profile/'user.js'
    if not prefs.exists():
        values={'browser.shell.checkDefaultBrowser':False,'browser.startup.homepage_override.mstone':'ignore','browser.aboutwelcome.enabled':False,'browser.startup.homepage':'about:blank','browser.startup.page':0,'browser.newtabpage.enabled':False,'browser.sessionstore.resume_from_crash':False,'signon.rememberSignons':False,'datareporting.policy.dataSubmissionEnabled':False,'toolkit.telemetry.enabled':False}
        prefs.write_text(''.join('user_pref('+json.dumps(k)+','+json.dumps(v)+');\n' for k,v in values.items()))
    return [str(binary),'--profile',str(profile),'--new-window',url]
