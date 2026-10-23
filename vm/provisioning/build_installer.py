"""Build private Ubuntu installation media from a checksum-verified official ISO.
Generated credentials and media remain under .local and must never be committed.
"""
from pathlib import Path
import hashlib, io, json, secrets, subprocess, sys

ROOT = Path(__file__).resolve().parents[2]
LOCAL = ROOT / '.local'
sys.path.insert(0, str(LOCAL / 'python-packages'))
import pycdlib

SOURCE = LOCAL / 'downloads/ubuntu-24.04.5-live-server-amd64.iso'
EXPECTED = '97f3d7ffb032c3eb3b23d2c8be9cc76e60c2c1f2c0146ba5ba9fe01cafae0fd8'
TARGET = LOCAL / 'downloads/localpilot-ubuntu-serial-autoinstall.iso'

def main():
    if TARGET.exists():
        raise SystemExit('Custom installer already exists; refusing to overwrite it.')
    print('Verifying official ISO...', flush=True)
    with SOURCE.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if digest != EXPECTED:
        raise SystemExit('Official ISO checksum mismatch.')
    private = LOCAL / 'credentials'
    private.mkdir(exist_ok=True)
    key = private / 'admin_ed25519'
    if not key.exists():
        subprocess.run(['ssh-keygen.exe', '-q', '-t', 'ed25519', '-N', '', '-C', 'localpilot-bootstrap', '-f', str(key)], check=True)
    public = key.with_suffix('.pub').read_text().strip()
    credentials_file = private / 'bootstrap.json'
    if credentials_file.exists():
        credentials = json.loads(credentials_file.read_text())
    else:
        credentials = {'admin_user':'localpilot', 'admin_password': secrets.token_urlsafe(24), 'desktop_user':'pilot', 'desktop_password': secrets.token_urlsafe(24)}
        credentials_file.write_text(json.dumps(credentials, indent=2))
    def password_hash(value):
        result = subprocess.run([r'C:\Program Files\Git\usr\bin\openssl.exe','passwd','-6','-stdin'], input=(value+'\n').encode(), capture_output=True, check=True)
        return result.stdout.decode().strip()
    config = f'''autoinstall:
  version: 1
  refresh-installer:
    update: false
  locale: en_US.UTF-8
  keyboard:
    layout: us
  timezone: Asia/Kolkata
  identity:
    hostname: localpilot
    username: localpilot
    password: "{password_hash(credentials['admin_password'])}"
  ssh:
    install-server: true
    allow-pw: false
    authorized-keys:
      - "{public}"
  storage:
    layout:
      name: direct
    swap:
      size: 0
  packages:
    - xfce4
    - xrdp
    - dbus-x11
    - xterm
    - xdotool
    - scrot
    - python3-venv
    - curl
    - ca-certificates
    - ufw
  updates: security
  late-commands:
    - curtin in-target --target=/target -- useradd --create-home --shell /bin/bash pilot
    - curtin in-target --target=/target -- usermod --password '{password_hash(credentials['desktop_password'])}' pilot
    - curtin in-target --target=/target -- sh -c 'echo startxfce4 > /home/pilot/.xsession; chown pilot:pilot /home/pilot/.xsession'
    - curtin in-target --target=/target -- adduser xrdp ssl-cert
    - curtin in-target --target=/target -- systemctl enable xrdp ssh
    - curtin in-target --target=/target -- sh -c 'mkdir -p /home/pilot/Workspace; chown pilot:pilot /home/pilot/Workspace'
    - curtin in-target --target=/target -- sh -c 'mkdir -p /etc/localpilot; echo installed > /etc/localpilot/bootstrap-complete'
  shutdown: poweroff
'''
    (LOCAL / 'autoinstall.yaml').write_text(config)
    iso = pycdlib.PyCdlib()
    iso.open(str(SOURCE))
    changed = []
    for path in ['/boot/grub/grub.cfg', '/boot/grub/loopback.cfg']:
        data = io.BytesIO()
        iso.get_file_from_iso_fp(data, rr_path=path)
        text = data.getvalue().decode()
        lines = []
        for line in text.splitlines():
            if line.lstrip().startswith('linux') and '/casper/vmlinuz' in line:
                line = line.replace(' ---', ' autoinstall fsck.mode=skip console=tty0 console=ttyS0,115200n8 ---')
                if 'autoinstall' not in line:
                    line += ' autoinstall fsck.mode=skip console=tty0 console=ttyS0,115200n8'
            if line.startswith('set timeout='):
                line = 'set timeout=3'
            lines.append(line)
        record = iso.get_record(rr_path=path)
        # Obtain the original ISO9660 name rather than guessing its case/version.
        components = []
        current = record
        while not current.is_root:
            components.append(current.file_identifier().decode())
            current = current.parent
        iso_path = '/' + '/'.join(reversed(components))
        iso.rm_file(iso_path=iso_path)
        content = ('\n'.join(lines)+'\n').encode()
        iso.add_fp(io.BytesIO(content), len(content), iso_path=iso_path, rr_name=Path(path).name)
        changed.append(path)
    encoded = config.encode()
    iso.add_fp(io.BytesIO(encoded), len(encoded), iso_path='/AUTOINSTALL.YAML;1', rr_name='autoinstall.yaml')
    print('Writing automated installer...', flush=True)
    iso.write(str(TARGET))
    iso.close()
    check = pycdlib.PyCdlib()
    check.open(str(TARGET))
    content = io.BytesIO()
    check.get_file_from_iso_fp(content, rr_path='/autoinstall.yaml')
    assert content.getvalue() == encoded
    boot = io.BytesIO()
    check.get_file_from_iso_fp(boot, rr_path='/boot/grub/grub.cfg')
    assert b'autoinstall fsck.mode=skip console=tty0 console=ttyS0,115200n8' in boot.getvalue()
    assert check.eltorito_boot_catalog is not None
    check.close()
    print(json.dumps({'installer':str(TARGET), 'bytes':TARGET.stat().st_size, 'verified_config':True, 'boot_catalog_present':True}))

if __name__ == '__main__':
    main()
