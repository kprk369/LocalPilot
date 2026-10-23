#!/bin/bash
set -euo pipefail
[[ $(hostname) == localpilot ]] || { echo 'Wrong host'; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y nginx
if ! id lp-gateway >/dev/null 2>&1; then
    useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin lp-gateway
    usermod --password '*' lp-gateway
fi
install -d -m 755 /etc/ssh/authorized_keys
python3 - <<'PY'
from pathlib import Path
key=Path('/home/localpilot/localpilot-gateway.pub').read_text().strip()
if not key.startswith('ssh-ed25519 '):raise ValueError('Invalid gateway key')
Path('/etc/ssh/authorized_keys/lp-gateway').write_text('restrict,port-forwarding,permitlisten="127.0.0.1:18765" '+key+'\n')
Path('/etc/ssh/authorized_keys/lp-gateway').chmod(0o644)
Path('/etc/ssh/sshd_config.d/61-localpilot-gateway.conf').write_text('''Match User lp-gateway
    AuthorizedKeysFile /etc/ssh/authorized_keys/%u
    AuthenticationMethods publickey
    PasswordAuthentication no
    KbdInteractiveAuthentication no
    AllowAgentForwarding no
    AllowTcpForwarding remote
    AllowStreamLocalForwarding no
    PermitListen 127.0.0.1:18765
    PermitOpen none
    GatewayPorts no
    PermitTTY no
    X11Forwarding no
    MaxSessions 0
    ForceCommand /bin/false
Match all
''')
PY
/usr/sbin/sshd -t
systemctl reload ssh
if [[ -L /etc/nginx/sites-enabled/default ]]; then
    cp /etc/nginx/sites-available/default /opt/localpilot/config/nginx-default.backup
    unlink /etc/nginx/sites-enabled/default
fi
cat > /etc/nginx/sites-available/localpilot <<'NGINX'
server {
    listen 127.0.0.1:8081;
    server_name _;
    access_log off;
    client_max_body_size 128k;
    location /guacamole/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_buffering off;
        proxy_read_timeout 3600s;
    }
    location / {
        proxy_pass http://127.0.0.1:18765;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_read_timeout 3600s;
    }
}
NGINX
ln -sf /etc/nginx/sites-available/localpilot /etc/nginx/sites-enabled/localpilot
nginx -t
systemctl enable --now nginx
systemctl reload nginx
printf 'Private gateway prepared on VM loopback. Existing Tailscale route has not been changed.\n'
