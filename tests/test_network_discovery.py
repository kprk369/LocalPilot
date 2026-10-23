import json
from backend.network import provisioned_vm_id, resolve_host as original_resolve

VM_ID='11111111-1111-4111-8111-111111111111'

def resolve_host(*args,**kwargs):
    return original_resolve(*args,expected_id=VM_ID,**kwargs)

def test_only_provisioned_vm_address_is_accepted(tmp_path):
    path = tmp_path / 'network.json'
    def write(**changes):
        state = {'VMId': VM_ID, 'State': 'Running', 'IPs': ['172.30.200.9']}
        state.update(changes)
        path.write_text(json.dumps(state), encoding='utf-8')
    write()
    assert resolve_host('172.30.165.6', 'localpilot-vm', path) == '172.30.200.9'
    assert resolve_host('example.test', '', path) == 'example.test'
    write(VMId='other-vm')
    assert resolve_host('original', 'localpilot-vm', path) == 'original'
    write(IPs=['127.0.0.1', '169.254.1.2', '8.8.8.8', '0.0.0.0'])
    assert resolve_host('original', 'localpilot-vm', path) == 'original'
    write(State='Off')
    assert resolve_host('original', 'localpilot-vm', path) == 'original'
    path.write_text('{broken', encoding='utf-8')
    assert resolve_host('original', 'localpilot-vm', path) == 'original'


def test_private_identity_is_validated_and_missing_identity_fails_closed(tmp_path,monkeypatch):
    import backend.network as network
    path=tmp_path/'vm.json'
    assert provisioned_vm_id(path) is None
    path.write_text(json.dumps({'Name':'LocalPilot','Id':VM_ID}),encoding='utf-8')
    assert provisioned_vm_id(path)==VM_ID
    path.write_text(json.dumps({'Name':'another-vm','Id':VM_ID}),encoding='utf-8')
    assert provisioned_vm_id(path) is None
    monkeypatch.setattr(network,'provisioned_vm_id',lambda:None)
    assert original_resolve('fallback','localpilot-vm',tmp_path/'network.json')=='fallback'
