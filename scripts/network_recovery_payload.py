"""Provisioning-only root payload; never used by the runtime agent."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def payload():
    helper = (ROOT / 'vm/provisioning/refresh_host_firewall.py').read_text(encoding='utf-8')
    service = "[Unit]\nDescription=Refresh LocalPilot Windows host SSH firewall\nWants=network-online.target\nAfter=network-online.target ufw.service\n[Service]\nType=oneshot\nExecStart=/usr/bin/python3 /usr/local/lib/localpilot/refresh_host_firewall.py\n[Install]\nWantedBy=multi-user.target\n"
    timer = "[Unit]\nDescription=Follow LocalPilot Windows gateway changes\n[Timer]\nOnBootSec=15\nOnUnitActiveSec=30\nAccuracySec=5\n[Install]\nWantedBy=timers.target\n"
    return "from pathlib import Path; import subprocess; p=Path('/usr/local/lib/localpilot/refresh_host_firewall.py'); p.parent.mkdir(parents=True,exist_ok=True); p.write_text("+repr(helper)+"); p.chmod(0o644); Path('/etc/systemd/system/localpilot-host-firewall.service').write_text("+repr(service)+"); Path('/etc/systemd/system/localpilot-host-firewall.timer').write_text("+repr(timer)+"); subprocess.run(['systemctl','daemon-reload'],check=True); subprocess.run(['systemctl','enable','--now','localpilot-host-firewall.service','localpilot-host-firewall.timer'],check=True); subprocess.run(['systemctl','is-active','localpilot-host-firewall.timer'],check=True); print('LOCALPILOT_NETWORK_RECOVERY_INSTALLED')"
