#!/usr/bin/env python3
"""Install committed ops files and reject drift before service startup."""
import argparse
import hashlib
import fcntl
import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

REPO = Path('/home/xiaqingp/MeowBillion')
FILES = {
    'ops/systemd/meowbillion.service': ('etc/systemd/system/meowbillion.service', 0o644),
    'ops/systemd/meowbillion-backup.service': ('etc/systemd/system/meowbillion-backup.service', 0o644),
    'ops/systemd/meowbillion-backup.timer': ('etc/systemd/system/meowbillion-backup.timer', 0o644),
    'ops/meowbillion-backup': ('usr/local/bin/meowbillion-backup', 0o755),
    'ops/manage.py': ('usr/local/lib/meowbillion/manage.py', 0o755),
}
UNITS = ['meowbillion.service', 'meowbillion-backup.service', 'meowbillion-backup.timer']
MANIFEST = 'var/lib/meowbillion/ops-installed.json'
PRIVATE = 'etc/meowbillion/backup.env'


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def git(*args):
    command = ['git', '-C', str(REPO), *args]
    if os.geteuid() == 0:
        owner = pwd.getpwuid(REPO.stat().st_uid).pw_name
        command = ['runuser', '-u', owner, '--', *command]
    return run(*command)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_write(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.install-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, mode)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def committed_sources():
    if git('status', '--porcelain', '--untracked-files=all', '--', 'ops'):
        raise RuntimeError('Commit all ops changes before installation/checking')
    sources = {}
    for source in FILES:
        data = (REPO / source).read_bytes()
        # Git text output helpers strip newlines; read the blob as bytes instead.
        blob_hash = git('rev-parse', 'HEAD:' + source)
        if git('hash-object', str(REPO / source)) != blob_hash:
            raise RuntimeError('Repository file differs from HEAD: ' + source)
        sources[source] = data
    return sources


def compare_files(sources, root=Path('/')):
    errors = []
    for source, (target, mode) in FILES.items():
        path = root / target
        if not path.is_file() or path.is_symlink() or path.read_bytes() != sources[source]:
            errors.append(target + ': content differs or missing')
        elif path.stat().st_mode & 0o777 != mode:
            errors.append(target + ': permissions differ')
        elif root == Path('/') and path.stat().st_uid != 0:
            errors.append(target + ': must be owned by root')
    if errors:
        raise RuntimeError('\n'.join(errors))


def check_loaded_units():
    for unit in UNITS:
        expected = '/etc/systemd/system/' + unit
        if run('systemctl', 'show', unit, '-p', 'FragmentPath', '--value') != expected:
            raise RuntimeError(unit + ': unexpected systemd configuration path')
        if run('systemctl', 'show', unit, '-p', 'DropInPaths', '--value'):
            raise RuntimeError(unit + ': unmanaged systemd override present')
        if run('systemctl', 'show', unit, '-p', 'NeedDaemonReload', '--value') == 'yes':
            raise RuntimeError(unit + ': daemon-reload required')


def check():
    sources = committed_sources()
    compare_files(sources)
    manifest = json.loads(Path('/' + MANIFEST).read_text())
    if manifest['sha256'] != {k: digest(v) for k, v in sources.items()}:
        raise RuntimeError('Installed manifest differs from repository; run install')
    check_loaded_units()
    print('OK: installed configuration matches committed repository files')


def folder_id(text):
    lines = [line.strip() for line in text.splitlines()
             if line.strip() and not line.lstrip().startswith('#')]
    if len(lines) != 1 or not re.fullmatch(r'GDRIVE_ROOT_FOLDER_ID=[A-Za-z0-9_-]+', lines[0]):
        raise RuntimeError('backup.env must contain only GDRIVE_ROOT_FOLDER_ID=<folder ID>')
    return lines[0].split('=', 1)[1]


def private_configuration():
    path = Path('/' + PRIVATE)
    if path.exists():
        folder_id(path.read_text())
        if path.is_symlink() or path.stat().st_uid != 0 or path.stat().st_mode & 0o077:
            raise RuntimeError('backup.env must be a root-owned private regular file (0600)')
        return
    old_script = Path('/usr/local/bin/meowbillion-backup')
    old = old_script.read_text() if old_script.exists() else ''
    match = re.search(r'^export RCLONE_CONFIG_GDRIVE_ROOT_FOLDER_ID="([A-Za-z0-9_-]+)"$', old, re.M)
    if not match:
        raise RuntimeError('Create /etc/meowbillion/backup.env from ops/backup.env.example first')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    atomic_write(path, ('GDRIVE_ROOT_FOLDER_ID=' + match[1] + '\n').encode(), 0o600)
    print('Migrated existing Drive destination into private configuration')


def wait_for_backup():
    deadline = time.monotonic() + 300
    while run('systemctl', 'show', 'meowbillion-backup.service', '-p', 'ActiveState', '--value') in ('active', 'activating', 'deactivating'):
        if time.monotonic() >= deadline:
            raise RuntimeError('Backup is still running; retry installation after it finishes')
        time.sleep(1)


def health_check():
    for attempt in range(20):
        try:
            with urllib.request.urlopen('http://127.0.0.1:8090/api/auth/status', timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.5)
    raise RuntimeError('Website health check failed')


def install():
    if os.geteuid() != 0:
        raise RuntimeError('Administrator required: sudo python3 ops/manage.py install')
    sources = committed_sources()
    # Refuse hidden overrides instead of silently discarding them.
    for unit in UNITS:
        if run('systemctl', 'show', unit, '-p', 'DropInPaths', '--value'):
            raise RuntimeError(unit + ': remove or version its override before installing')
    run('bash', '-n', str(REPO / 'ops/meowbillion-backup'))
    private_configuration()
    timer_active = run('systemctl', 'show', 'meowbillion-backup.timer', '-p', 'ActiveState', '--value') == 'active'
    old_files = {}
    paths = [Path('/' + dst) for dst, _ in FILES.values()] + [Path('/' + MANIFEST)]
    for path in paths:
        if path.is_symlink():
            raise RuntimeError('Refusing to overwrite symlink: ' + str(path))
        old_files[path] = (path.read_bytes(), path.stat().st_mode & 0o777) if path.exists() else None
    run('systemctl', 'stop', 'meowbillion-backup.timer')
    installed = False
    changed = False
    consistent = False
    try:
        wait_for_backup()
        changed = True
        for source, (target, mode) in FILES.items():
            atomic_write(Path('/' + target), sources[source], mode)
        manifest = {'commit': git('rev-parse', 'HEAD'), 'sha256': {k: digest(v) for k, v in sources.items()}}
        atomic_write(Path('/' + MANIFEST), (json.dumps(manifest, indent=2) + '\n').encode(), 0o644)
        run('systemd-analyze', 'verify', *['/etc/systemd/system/' + u for u in UNITS])
        run('systemctl', 'daemon-reload')
        check()
        consistent = True
        run('systemctl', 'restart', 'meowbillion.service')
        health_check()
        # Runs the actual installed unit, including Drive download verification.
        run('systemctl', 'start', 'meowbillion-backup.service')
        if run('systemctl', 'show', 'meowbillion-backup.service', '-p', 'Result', '--value') != 'success':
            raise RuntimeError('Installed backup service did not succeed')
        run('systemctl', 'enable', 'meowbillion.service', 'meowbillion-backup.timer')
        run('systemctl', 'start', 'meowbillion-backup.timer')
        check()
        installed = True
        print('INSTALL VERIFIED: configuration matches, website responds, backup download verifies')
    except Exception:
        if consistent:
            print('Files match the repository, but runtime verification failed; inspect service logs and retry install', file=sys.stderr)
            raise
        if not changed:
            raise
        print('Installation failed; restoring previous system files', file=sys.stderr)
        for path, old in old_files.items():
            if old is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, *old)
        run('systemctl', 'daemon-reload')
        run('systemctl', 'restart', 'meowbillion.service')
        raise
    finally:
        if not installed and timer_active:
            run('systemctl', 'start', 'meowbillion-backup.timer')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'check'])
    args = parser.parse_args()
    try:
        if args.action == 'install' and os.geteuid() == 0:
            with open('/run/lock/meowbillion-ops-install.lock', 'w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                install()
        else:
            {'install': install, 'check': check}[args.action]()
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print('ERROR:', error, file=sys.stderr)
        sys.exit(1)
