"""Resolve only the provisioned VM; SSH still verifies its pinned host key."""
import ipaddress
import json
import os
from pathlib import Path
import uuid

ROOT=Path(__file__).resolve().parents[1]
DISCOVERY=Path(os.environ.get('ProgramData',r'C:\ProgramData'))/'LocalPilot'/'network.json'


def provisioned_vm_id(path=None):
    """Read this installation's private creation record; never guess a VM ID."""
    path=Path(path) if path is not None else ROOT/'.local/vm-created.json'
    try:
        state=json.loads(path.read_text(encoding='utf-8-sig'))
        if state.get('Name')!='LocalPilot':return None
        return str(uuid.UUID(state['Id']))
    except (OSError,ValueError,TypeError,KeyError,AttributeError):return None


def resolve_host(fallback,alias='',state_path=DISCOVERY,*,expected_id=None):
    if alias!='localpilot-vm':return fallback
    expected_id=expected_id or provisioned_vm_id()
    if not expected_id:return fallback
    try:
        state=json.loads(Path(state_path).read_text(encoding='utf-8-sig'))
        if str(uuid.UUID(state.get('VMId','')))!=str(uuid.UUID(expected_id)) or state.get('State')!='Running':return fallback
        addresses=[ipaddress.ip_address(value) for value in state['IPs']]
        for address in addresses:
            if address.version==4 and address.is_private and not address.is_loopback and not address.is_link_local and not address.is_unspecified:return str(address)
    except (OSError,ValueError,TypeError,KeyError,AttributeError):pass
    return fallback
