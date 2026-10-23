"""Switch the existing private HTTPS service to the verified combined gateway."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vm/provisioning'))
import guest_setup
guest_setup.ssh('test -f /opt/localpilot/config/tailscale-desktop-only.json || tailscale serve status --json > /opt/localpilot/config/tailscale-desktop-only.json; tailscale serve --bg http://127.0.0.1:8081; tailscale serve status',privileged=True)
