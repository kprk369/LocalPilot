#!/usr/bin/env bash
# Run as root only inside the LocalPilot Ubuntu VM.
set -euo pipefail
[[ $(hostname) == localpilot ]] || { echo 'Refusing: unexpected VM hostname'; exit 1; }
[[ -f /etc/localpilot/bootstrap-complete ]] || { echo 'Ubuntu bootstrap incomplete'; exit 1; }
[[ -f /home/localpilot/localpilot-bootstrap.json ]] || { echo 'Private bootstrap input missing'; exit 1; }
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y docker.io docker-compose-v2 python3 linux-cloud-tools-virtual
udevadm control --reload
udevadm trigger --subsystem-match=misc --action=change
systemctl start --no-block hv-kvp-daemon.service hv-vss-daemon.service
systemctl enable --now docker
install -d -m 700 /opt/localpilot /opt/localpilot/initdb /opt/localpilot/config
install -m 600 /home/localpilot/localpilot-bootstrap.json /opt/localpilot/config/bootstrap.json
# Provisioning never gives the pilot account sudo or Docker access.
if id -nG pilot | grep -Eq '(^| )(sudo|docker|adm)( |$)'; then
    echo 'Unexpected privileged group on pilot account'; exit 1
fi
python3 - <<'PY'
import json, os, secrets
from pathlib import Path
root=Path('/opt/localpilot')
bootstrap=json.loads((root/'config/bootstrap.json').read_text())
bootstrap.setdefault('database_password', secrets.token_urlsafe(32))
bootstrap.setdefault('guacamole_password', secrets.token_urlsafe(24))
(root/'config/bootstrap.json').write_text(json.dumps(bootstrap,indent=2))
os.chmod(root/'config/bootstrap.json',0o600)
config={
 'name':'localpilot',
 'services':{
  'database':{
   'image':'postgres:17-alpine','restart':'unless-stopped',
   'environment':{'POSTGRES_DB':'guacamole','POSTGRES_USER':'guacamole','POSTGRES_PASSWORD':bootstrap['database_password']},
   'volumes':['database:/var/lib/postgresql/data','./initdb:/docker-entrypoint-initdb.d:ro'],
   'healthcheck':{'test':['CMD-SHELL','pg_isready -U guacamole -d guacamole'],'interval':'5s','timeout':'5s','retries':30},
   'networks':['private']},
  'guacd':{'image':'guacamole/guacd:1.6.0','restart':'unless-stopped',
   'extra_hosts':['host.docker.internal:host-gateway'],'networks':['private']},
  'web':{'image':'guacamole/guacamole:1.6.0','restart':'unless-stopped',
   'ports':['127.0.0.1:8080:8080'],
   'environment':{'GUACD_HOSTNAME':'guacd','POSTGRESQL_ENABLED':'true','POSTGRESQL_HOSTNAME':'database','POSTGRESQL_DATABASE':'guacamole','POSTGRESQL_USERNAME':'guacamole','POSTGRESQL_PASSWORD':bootstrap['database_password'],'REMOTE_IP_VALVE_ENABLED':'true'},
   'depends_on':{'database':{'condition':'service_healthy'},'guacd':{'condition':'service_started'}},
   'networks':['private']}
 },
 'volumes':{'database':{}},
 'networks':{'private':{'driver':'bridge','driver_opts':{'com.docker.network.bridge.name':'br-localpilot'}}}
}
(root/'compose.json').write_text(json.dumps(config,indent=2))
os.chmod(root/'compose.json',0o600)
PY
chmod 755 /opt/localpilot/initdb
cd /opt/localpilot
docker compose -f compose.json pull
if [[ ! -f initdb/001-schema.sql ]]; then
    docker run --rm guacamole/guacamole:1.6.0 /opt/guacamole/bin/initdb.sh --postgresql > initdb/001-schema.sql
    python3 - <<'PY'
import hashlib, json, secrets
from pathlib import Path
root=Path('/opt/localpilot')
data=json.loads((root/'config/bootstrap.json').read_text())
salt=secrets.token_bytes(32)
hash=hashlib.sha256((data['guacamole_password']+salt.hex().upper()).encode()).hexdigest()
def quote(s):return "'"+s.replace("'","''")+"'"
sql=f"""
UPDATE guacamole_user SET password_hash=decode('{hash}','hex'),password_salt=decode('{salt.hex()}','hex'),password_date=CURRENT_TIMESTAMP
WHERE entity_id=(SELECT entity_id FROM guacamole_entity WHERE name='guacadmin' AND type='USER');
UPDATE guacamole_entity SET name='localpilot' WHERE name='guacadmin' AND type='USER';
INSERT INTO guacamole_connection (connection_name,protocol) VALUES ('LocalPilot Linux Desktop','rdp');
"""
params={'hostname':'host.docker.internal','port':'3389','username':'pilot','password':data['desktop_password'],'security':'tls','ignore-cert':'true','resize-method':'display-update','enable-wallpaper':'false','enable-font-smoothing':'true','color-depth':'24'}
for name,value in params.items():
 sql += f"INSERT INTO guacamole_connection_parameter(connection_id,parameter_name,parameter_value) SELECT connection_id,{quote(name)},{quote(value)} FROM guacamole_connection WHERE connection_name='LocalPilot Linux Desktop';\n"
sql += "INSERT INTO guacamole_connection_permission(entity_id,connection_id,permission) SELECT e.entity_id,c.connection_id,'READ' FROM guacamole_entity e CROSS JOIN guacamole_connection c WHERE e.name='localpilot' AND e.type='USER' AND c.connection_name='LocalPilot Linux Desktop';\n"
(root/'initdb/002-localpilot.sql').write_text(sql)
(root/'initdb/002-localpilot.sql').chmod(0o644)
PY
fi
# Web access stays on loopback. Only the Windows gateway can SSH into the VM.
gateway=$(ip -4 route show default | awk 'NR==1 {print $3}')
[[ -n "$gateway" ]] || { echo 'No default gateway found'; exit 1; }
ufw default deny incoming
ufw default allow outgoing
ufw allow from "$gateway" to any port 22 proto tcp
ufw allow in on br-localpilot to any port 3389 proto tcp
ufw --force enable
docker compose -f compose.json up -d
# Add Tailscale through its signed official Ubuntu package repository.
curl --fail --silent --show-error https://pkgs.tailscale.com/stable/ubuntu/noble.noarmor.gpg -o /usr/share/keyrings/tailscale-archive-keyring.gpg
curl --fail --silent --show-error https://pkgs.tailscale.com/stable/ubuntu/noble.tailscale-keyring.list -o /etc/apt/sources.list.d/tailscale.list
apt-get update
apt-get install -y tailscale
systemctl enable --now tailscaled
rm -f /home/localpilot/localpilot-bootstrap.json
printf '\nLocalPilot desktop gateway installed. Tailscale account login is still required.\n'
