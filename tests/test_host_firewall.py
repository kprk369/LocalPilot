import importlib.util
from pathlib import Path
import pytest
spec=importlib.util.spec_from_file_location('host_firewall',Path(__file__).resolve().parents[1]/'vm/provisioning/refresh_host_firewall.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

def test_only_private_gateway_with_valid_interface_is_used():
    assert module.host_route([{'gateway':'192.168.100.1','dev':'eth0'}]) == {'gateway':'192.168.100.1','device':'eth0'}
    for route in [{'gateway':'8.8.8.8','dev':'eth0'},{'gateway':'127.0.0.1','dev':'eth0'},{'gateway':'192.168.100.1','dev':'bad;command'}]:
        with pytest.raises(RuntimeError): module.host_route([route])
