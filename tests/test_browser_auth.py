import pytest
from fastapi.testclient import TestClient
from backend.api import create_app
from backend.auth import COOKIE, password_hash
from backend.config import Settings
from test_security_and_tasks import FakeProvider, FakeExecutor

@pytest.fixture
def browser(tmp_path):
    settings=Settings(token='operator-token-'+'x'*40,ssh_host='127.0.0.1',ssh_key='unused',known_hosts='unused',database=str(tmp_path/'tasks.db'),password_hash=password_hash('browser-secret'),public_origin='https://testserver')
    with TestClient(create_app(settings,FakeProvider(),FakeExecutor()),base_url='https://testserver') as client:
        yield client,settings

def login(client,**kwargs):
    return client.post('/session',json={'username':'localpilot','password':'browser-secret'},headers={'Origin':'https://testserver'},**kwargs)

def test_browser_session_and_logout_revocation(browser):
    client,settings=browser
    assert client.get('/tasks').status_code==401
    response=login(client)
    assert response.status_code==200
    assert settings.token not in response.text
    cookie=response.headers['set-cookie'].lower()
    assert 'secure' in cookie and 'httponly' in cookie and 'samesite=strict' in cookie
    value=client.cookies.get(COOKIE)
    assert client.get('/health').status_code==200
    assert client.get('/tasks').json()==[]
    assert client.delete('/session',headers={'Origin':'https://testserver'}).status_code==200
    assert client.get('/health',headers={'Cookie':COOKIE+'='+value}).status_code==401

def test_cookie_mutations_reject_cross_origin_and_missing_origin(browser):
    client,_=browser
    login(client)
    for headers in ({},{'Origin':'https://attacker.example'}):
        assert client.post('/tasks',json={'request':'hello'},headers=headers).status_code==403
    assert client.post('/tasks',json={'request':'hello'},headers={'Origin':'https://testserver'}).status_code==202

def test_login_rate_limit_and_origin(browser):
    client,_=browser
    assert client.post('/session',json={'username':'localpilot','password':'browser-secret'},headers={'Origin':'https://attacker.example'}).status_code==403
    for _ in range(5):
        assert client.post('/session',json={'username':'localpilot','password':'wrong'},headers={'Origin':'https://testserver'}).status_code==401
    assert login(client).status_code==429

def test_frontend_contains_no_operator_token_or_private_files(browser):
    client,settings=browser
    response=client.get('/')
    assert response.status_code==200
    assert 'LocalPilot' in response.text and settings.token not in response.text
    assert "script-src 'self'" in response.headers['content-security-policy']
    assert client.get('/assets/app.js').status_code==200
    assert client.get('/assets/../.local/runtime.json').status_code==404


def test_install_manifest_icons_and_worker_scope(browser):
    client,settings=browser
    response=client.get('/assets/manifest.webmanifest')
    assert response.status_code==200
    manifest=response.json()
    assert manifest['display']=='standalone' and manifest['scope']=='/' and manifest['start_url']=='/'
    for icon in manifest['icons']:
        image=client.get(icon['src'])
        assert image.status_code==200 and image.content.startswith(b'\x89PNG\r\n\x1a\n')
        width=int.from_bytes(image.content[16:20],'big')
        height=int.from_bytes(image.content[20:24],'big')
        assert icon['sizes']==f'{width}x{height}'
    worker=client.get('/sw.js')
    assert worker.status_code==200 and worker.headers['service-worker-allowed']=='/'
    assert 'javascript' in worker.headers['content-type']
    assert settings.token not in worker.text
    offline=client.get('/assets/offline.html')
    assert offline.status_code==200 and settings.token not in offline.text
    assert client.get('/tasks').status_code==401


def test_linux_readiness_requires_authenticated_session(browser):
    client,_=browser
    assert client.get('/linux/status').status_code==401
    login(client)
    response=client.get('/linux/status')
    assert response.status_code==200
    assert response.json()['state']!='ready'  # API process alone is insufficient evidence.
