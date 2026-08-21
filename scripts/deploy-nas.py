#!/usr/bin/env python3
"""一键部署/更新 family-learning 到群晖 NAS。

用法：
    $env:NAS_SSH_PASSWORD='<admin密码>'   # 必填，仅本次会话环境变量，不落盘
    python scripts/deploy-nas.py [--skip-build] [--version v0.3.0]

流程（本地）：
    1. docker buildx 构建 linux/amd64 镜像 family-learning:latest
    2. docker save 导出 tar + sha256 到 dist/
流程（远程，走 SSH/SFTP）：
    3. 上传 tar
    4. 优雅停止并移除旧容器（含手动命名的 family-learning-v2.5）
    5. 备份数据目录关键文件（app.db* 等）
    6. docker load 加载新镜像
    7. 删除被顶替的旧镜像（仅本项目的悬空镜像）
    8. docker compose up -d --force-recreate
    9. 轮询 http://<host>:<port>/api/health 直到 "worker":true

依赖：本地需安装 docker(+buildx) 与 paramiko（pip install paramiko）。
"""

import argparse
import hashlib
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import paramiko

DOCKER_REMOTE = '/usr/local/bin/docker'
DOCKER_COMPOSE_REMOTE = '/usr/local/bin/docker-compose'
REMOTE_PROJECT_DIR = '/volume1/docker/family-learning'
REMOTE_PORT = 6633
IMAGE_NAME = 'family-learning:latest'


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def build_and_save(version: str) -> tuple[Path, str]:
    print(f'[build] docker buildx linux/amd64 family-learning:latest ...', flush=True)
    subprocess.run(
        ['docker', 'buildx', 'build', '--platform', 'linux/amd64', '--load',
         '-t', IMAGE_NAME, '-f', 'deploy/Dockerfile', '.'],
        check=True,
    )
    out_dir = Path('dist')
    out_dir.mkdir(parents=True, exist_ok=True)
    tar = out_dir / f'family-learning-ds918plus-amd64-{version}.tar'
    subprocess.run(['docker', 'save', '-o', str(tar), IMAGE_NAME], check=True)
    digest = sha256_file(tar)
    (out_dir / f'family-learning-ds918plus-amd64-{version}.tar.sha256').write_text(f'{digest}  {tar.name}\n')
    print(f'[build] saved {tar.name} ({tar.stat().st_size / 1e6:.0f} MB) sha256 {digest[:16]}...', flush=True)
    return tar, digest


class Nas:
    def __init__(self, host: str, user: str, password: str):
        self.client = paramiko.SSHClient()
        self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.client.connect(host, username=user, password=password, timeout=20)
        self.host, self.password = host, password

    def sudo(self, cmd: str, timeout: int = 300) -> tuple[int, str]:
        full = f"echo {shq(self.password)} | sudo -S {cmd}"
        _i, o, e = self.client.exec_command(full, timeout=timeout)
        out = o.read().decode(errors='replace')
        err = e.read().decode(errors='replace')
        code = o.channel.recv_exit_status()
        return code, (out + err).strip()

    def sudo_sh(self, script: str, timeout: int = 300) -> tuple[int, str]:
        """Run a shell script (with cd + compose) under sudo via ``sh -c``."""
        return self.sudo(f"sh -c {shq(script)}", timeout)

    def sh(self, cmd: str, timeout: int = 60) -> tuple[int, str]:
        _i, o, e = self.client.exec_command(cmd, timeout=timeout)
        out = o.read().decode(errors='replace')
        err = e.read().decode(errors='replace')
        return o.channel.recv_exit_status(), (out + err)

    def upload(self, local: Path, remote: str) -> None:
        """Stream the file over an SSH exec channel (Synology may lack SFTP)."""
        print(f'[upload] {local.name} -> {remote}', flush=True)
        stdin, stdout, stderr = self.client.exec_command(f'cat > {shq(remote)}')
        sent = 0
        try:
            with local.open('rb') as source:
                while True:
                    block = source.read(1 << 20)
                    if not block:
                        break
                    stdin.write(block)
                    sent += len(block)
            stdin.close()
        finally:
            stdin.close()
        code = stdout.channel.recv_exit_status()
        err = stderr.read().decode(errors='replace')
        stdout.read()
        if code != 0:
            raise RuntimeError(f'upload failed: {err}')
        print(f'[upload] done ({sent // (1 << 20)} MB)', flush=True)

    def close(self):
        self.client.close()


def shq(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def deploy(host, user, password, tar, version, skip_build):
    nas = Nas(host, user, password)
    docker = DOCKER_REMOTE
    project = REMOTE_PROJECT_DIR
    remote_tar = f'{project}/TAR/{tar.name}'

    try:
        # 1. capture the old image id (to remove after it is replaced)
        code, old_images = nas.sudo(f"{docker} images -q {IMAGE_NAME}")
        old_id = old_images.splitlines()[0].strip() if code == 0 and old_images.strip() else ''

        # 2. upload
        nas.upload(tar, remote_tar)
        nas.upload(tar.with_suffix('.tar.sha256'), f'{remote_tar}.sha256')

        # 3. graceful stop + remove old containers (legacy manual name + compose orphans)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        nas.sudo(f"{docker} stop {shq('family-learning-v2.5')} || true")
        nas.sudo_sh(f"cd {project} && {DOCKER_COMPOSE_REMOTE} down --remove-orphans || true")
        nas.sudo(f"{docker} rm -f {shq('family-learning-v2.5')} || true")

        # 4. back up data files before touching anything else
        backup_dir = f'{project}/backups/pre-upgrade-{stamp}'
        nas.sudo(f"mkdir -p {backup_dir}")
        nas.sudo_sh(f"cd {project} && cp -f app.db app.db-wal app.db-shm tts-settings.key ai-settings.key {backup_dir}/ 2>/dev/null || true")

        # 5. load the new image (the old :latest becomes a dangling image)
        print('[remote] docker load ...', flush=True)
        code, out = nas.sudo(f"{docker} load -i {remote_tar}", timeout=600)
        print(out, flush=True)

        # 6. recreate with compose v1 (Synology ships docker-compose, not `docker compose`)
        print('[remote] docker-compose up -d --force-recreate ...', flush=True)
        code, out = nas.sudo_sh(f"cd {project} && {DOCKER_COMPOSE_REMOTE} -f compose.yaml up -d --force-recreate", timeout=600)
        print(out, flush=True)

        # 7. remove the now-dangling old image (this project only)
        if old_id:
            nas.sudo(f"{docker} image rm -f {old_id} || true")

        # 8. health check
        print('[verify] waiting for /api/health ...', flush=True)
        for _ in range(60):
            code, body = nas.sh(f"curl -fsS http://127.0.0.1:{REMOTE_PORT}/api/health || true")
            if '"worker":true' in body or '"worker": true' in body:
                print(f'[verify] OK: {body}', flush=True)
                return
            time.sleep(2)
        raise RuntimeError(f'health check failed: last response {body!r}')
    finally:
        nas.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='<nas-ip>')
    parser.add_argument('--user', default='admin')
    parser.add_argument('--version', default=None)
    parser.add_argument('--skip-build', action='store_true', help='reuse an existing dist tar instead of rebuilding')
    parser.add_argument('--tar', default=None, help='path to an already-built tar (implies --skip-build)')
    args = parser.parse_args()

    password = os.environ.get('NAS_SSH_PASSWORD', '')
    if not password:
        print('请先设置环境变量 NAS_SSH_PASSWORD（NAS 管理员密码），仅用于本次会话。', file=sys.stderr)
        sys.exit(2)

    if args.tar:
        tar = Path(args.tar)
        digest = sha256_file(tar)
        version = args.version or tar.stem.split('amd64-')[-1]
    elif args.skip_build:
        # pick the most recent dist tar
        tars = sorted(Path('dist').glob('family-learning-ds918plus-amd64-*.tar'))
        if not tars:
            print('dist/ 下没有可复用的 tar，去掉 --skip-build 重试。', file=sys.stderr)
            sys.exit(2)
        tar = tars[-1]
        version = args.version or tar.stem.split('amd64-')[-1]
        digest = sha256_file(tar)
    else:
        version = args.version or datetime.now(timezone.utc).strftime('%Y%m%d')
        tar, digest = build_and_save(version)

    print(f'[deploy] version={version} tar={tar.name} sha256={digest[:16]}...', flush=True)
    deploy(args.host, args.user, password, tar, version, args.skip_build)
    print(f'部署完成：http://{args.host}:{REMOTE_PORT}', flush=True)


if __name__ == '__main__':
    main()
