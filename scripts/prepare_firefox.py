"""Provision Mozilla's official signed APT source; agent cannot edit sources."""
from pathlib import Path
import shlex
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'vm/provisioning'))
import guest_setup
program=r"""
from pathlib import Path
import subprocess,tempfile,urllib.request
expected='35BAA0B33E9EB396F59CA838C0BA5CE6DC6315A3'
with urllib.request.urlopen('https://packages.mozilla.org/apt/repo-signing-key.gpg',timeout=30) as response:
    key=response.read(65537)
if len(key)>65536:raise ValueError('Unexpected signing key size')
with tempfile.TemporaryDirectory() as directory:
    candidate=Path(directory)/'key.asc';candidate.write_bytes(key)
    result=subprocess.run(['gpg','--batch','--no-options','--homedir',directory,'--show-keys','--with-colons',str(candidate)],capture_output=True,text=True,check=True)
    fingerprints=[line.split(':')[9] for line in result.stdout.splitlines() if line.startswith('fpr:')]
    if not fingerprints or fingerprints[0]!=expected:raise ValueError('Mozilla signing key fingerprint mismatch')
keypath=Path('/etc/apt/keyrings/localpilot-mozilla.asc');keypath.parent.mkdir(parents=True,exist_ok=True)
keypath.write_bytes(key);keypath.chmod(0o644)
source=Path('/etc/apt/sources.list.d/localpilot-mozilla.list')
source.write_text('deb [signed-by=/etc/apt/keyrings/localpilot-mozilla.asc] https://packages.mozilla.org/apt mozilla main\n')
prefs=Path('/etc/apt/preferences.d/localpilot-firefox')
prefs.write_text('Package: firefox\nPin: origin packages.mozilla.org\nPin-Priority: 1000\n\nPackage: firefox\nPin: release o=Ubuntu\nPin-Priority: -1\n')
subprocess.run(['apt-get','-o','Acquire::Retries=1','-o','Acquire::https::Timeout=20','update'],check=True,timeout=180)
subprocess.run(['apt-cache','policy','firefox'],check=True)
print('Verified Mozilla signing key; Firefox source prepared. No browser package installed yet.')
"""
with (ROOT/'.local/logs/firefox-source-setup.log').open('ab') as log:
    guest_setup.ssh('python3 -c '+shlex.quote(program),privileged=True,log=log)
print('Mozilla signed source prepared; package installation still uses the review/approval broker.')
