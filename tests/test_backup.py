"""Recovery must preserve real bytes and refuse unsafe/incomplete archives."""
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tarfile
import pytest
from scripts import backup


def make_backup(tmp_path):
    root=tmp_path/'backup';(root/'private').mkdir(parents=True)
    content='Restored LocalPilot \u2713\n'.encode('utf-8')+b'\x00\xff'
    metadata={'files':{'folder/data.bin':{'bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()}},'omitted':[]}
    with tarfile.open(root/'workspace.tar.gz','w:gz') as archive:
        for name,data in [('workspace/folder/data.bin',content),('workspace-manifest.json',json.dumps(metadata).encode())]:
            item=tarfile.TarInfo(name);item.size=len(data);archive.addfile(item,io.BytesIO(data))
    with sqlite3.connect(root/'private/tasks.sqlite3') as db:
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('CREATE TABLE tasks(id TEXT,status TEXT)');db.execute("INSERT INTO tasks VALUES('saved-task','completed')")
    db.close()
    files={p.relative_to(root).as_posix():{'bytes':p.stat().st_size,'sha256':backup.digest(p)} for p in root.rglob('*') if p.is_file()}
    (root/'manifest.json').write_text(json.dumps({'format':1,'vm_id':'11111111-1111-4111-8111-111111111111','files':files}),encoding='utf-8')
    (root/'COMPLETE').write_text(backup.digest(root/'manifest.json')+'\n',encoding='ascii')
    return root,content


def test_staged_restore_preserves_binary_and_database_without_overwriting(tmp_path):
    source,content=make_backup(tmp_path);destination=tmp_path/'new-restore'
    assert backup.verify(source)['tasks']==1
    assert backup.verify(source)['tasks']==1
    assert not (source/'private/tasks.sqlite3-wal').exists()
    assert not (source/'private/tasks.sqlite3-shm').exists()
    result=backup.restore(source,destination)
    assert result['restored'] and not result['live_setup_modified']
    assert (destination/'restored-workspace/folder/data.bin').read_bytes()==content
    with sqlite3.connect(destination/'private/tasks.sqlite3') as db:
        assert db.execute('SELECT * FROM tasks').fetchone()==('saved-task','completed')
    with pytest.raises(ValueError,match='must not exist'):backup.restore(source,destination)
    assert (destination/'restored-workspace/folder/data.bin').read_bytes()==content
    assert backup.verify(source)['verified']


def test_corruption_and_incomplete_copy_are_rejected_before_restore(tmp_path):
    source,_=make_backup(tmp_path)
    (source/'COMPLETE').unlink()
    with pytest.raises(FileNotFoundError):backup.restore(source,tmp_path/'restore')
    assert not (tmp_path/'restore').exists()
    (source/'COMPLETE').write_text(backup.digest(source/'manifest.json')+'\n',encoding='ascii')
    with (source/'workspace.tar.gz').open('ab') as stream:stream.write(b'corruption')
    with pytest.raises(ValueError,match='checksum mismatch'):backup.restore(source,tmp_path/'restore')
    assert not (tmp_path/'restore').exists()


@pytest.mark.parametrize('name',['../escape','/absolute','workspace/../../escape','workspace\\escape','C:/escape'])
def test_workspace_path_traversal_is_rejected(tmp_path,name):
    path=tmp_path/'unsafe.tar.gz'
    with tarfile.open(path,'w:gz') as archive:
        item=tarfile.TarInfo(name);item.size=1;archive.addfile(item,io.BytesIO(b'x'))
    with pytest.raises(ValueError):backup.verify_workspace(path)
    assert not (tmp_path/'escape').exists()


def test_workspace_symlink_is_rejected(tmp_path):
    path=tmp_path/'unsafe.tar.gz'
    with tarfile.open(path,'w:gz') as archive:
        item=tarfile.TarInfo('workspace/link');item.type=tarfile.SYMTYPE;item.linkname='/etc/passwd';archive.addfile(item)
    with pytest.raises(ValueError,match='Links'):backup.verify_workspace(path)


@pytest.mark.parametrize('name',['workspace/NUL','workspace/filename.','workspace/name ','workspace/a?b'])
def test_linux_names_that_alias_windows_files_are_rejected(name):
    with pytest.raises(ValueError):backup.safe_windows_member(name)


def test_consistent_sqlite_backup_includes_uncheckpointed_wal(tmp_path):
    live=tmp_path/'live.db';saved=tmp_path/'snapshot.db'
    with sqlite3.connect(live) as db:
        db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA wal_autocheckpoint=0')
        db.execute('CREATE TABLE tasks(id TEXT)');db.execute("INSERT INTO tasks VALUES('recent')");db.commit()
        assert Path(str(live)+'-wal').stat().st_size>0
        with sqlite3.connect(saved) as target:db.backup(target)
    with sqlite3.connect(saved) as restored:
        assert restored.execute('SELECT id FROM tasks').fetchone()[0]=='recent'
        assert restored.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
