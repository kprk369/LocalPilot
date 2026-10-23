"""Publication guards reject secrets and private/escaping artifacts."""
from scripts import check_publication as publication


def test_publication_rejects_private_or_unknown_roots(tmp_path,monkeypatch):
    monkeypatch.setattr(publication,'ROOT',tmp_path)
    result=publication.inspect_files(['.local/runtime.json','unknown-file.txt'])
    assert not result['passed'] and len(result['findings'])==2


def test_publication_detects_key_headers_without_printing_key_material(tmp_path,monkeypatch):
    monkeypatch.setattr(publication,'ROOT',tmp_path)
    path=tmp_path/'backend';path.mkdir()
    marker='-----BEGIN '+'OPENSSH PRIVATE KEY-----'
    (path/'bad.py').write_text(marker,encoding='utf-8')
    result=publication.inspect_files(['backend/bad.py'])
    assert not result['passed']
    assert result['findings']==[{'file':'backend/bad.py','reason':'private-key header'}]
    assert marker not in str(result)


def test_publication_compares_known_secrets_without_disclosing_values(tmp_path,monkeypatch):
    monkeypatch.setattr(publication,'ROOT',tmp_path)
    path=tmp_path/'backend';path.mkdir()
    (path/'bad.py').write_text('a private installation credential',encoding='utf-8')
    result=publication.inspect_files(['backend/bad.py'],[b'private installation credential'])
    assert not result['passed']
    assert 'private installation credential' not in str(result)


def test_publication_accepts_small_source_file(tmp_path,monkeypatch):
    monkeypatch.setattr(publication,'ROOT',tmp_path)
    path=tmp_path/'backend';path.mkdir()
    (path/'good.py').write_text('print("LocalPilot")\n',encoding='utf-8')
    result=publication.inspect_files(['backend/good.py'])
    assert result['passed'] and result['file_count']==1
