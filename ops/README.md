# 服务器启动、备份与恢复

此目录保存正式服务器现有配置的可安装版本。GitHub 上的代码不会自动替换系统配置，也不会自动重启服务。

| 文件 | 安装位置 | 用途 |
| --- | --- | --- |
| `systemd/meowbillion.service` | `/etc/systemd/system/meowbillion.service` | 开机启动网站/API，端口 8090 |
| `systemd/meowbillion-backup.service` | `/etc/systemd/system/meowbillion-backup.service` | 执行 Drive 备份 |
| `systemd/meowbillion-backup.timer` | `/etc/systemd/system/meowbillion-backup.timer` | 每天凌晨 02:00 备份，错过后补执行 |
| `meowbillion-backup` | `/usr/local/bin/meowbillion-backup` | 文件同步、SQLite 一致性快照、历史清理 |
| `backup.env.example` | `/etc/meowbillion/backup.env` | 私有备份目标配置模板 |

## 与当前服务器的差异

服务账号和项目路径仍按当前服务器的 `xiaqingp`、`/home/xiaqingp/MeowBillion` 保存。换账号或目录时需修改两个 service 和备份脚本中的路径。

公开仓库不保存实际 Drive 文件夹 ID。仓库版本的备份服务从 `/etc/meowbillion/backup.env` 加载 `GDRIVE_ROOT_FOLDER_ID`，脚本检查它非空；当前已安装脚本仍使用原来的内置目标。此次归档没有替换正在运行的系统配置。

真正的 Google OAuth 凭据不在仓库里。脚本仍由服务账号调用 `gcloud auth print-access-token` 获取短期令牌，再通过环境变量传给 rclone；必须使用具有目标 Drive 访问权限和相应 OAuth scope 的账号授权。仅安装 gcloud 或登录一个没有 Drive 权限的账号不足以完成备份。

## 安装或迁移

1. 安装 Git、Python 3（含 venv）、rsync、rclone、Google Cloud CLI。测试套件还需要 Node.js。
2. 将仓库放到 `/home/xiaqingp/MeowBillion`，创建 `.venv`，执行 `.venv/bin/pip install -r requirements.txt`。
3. 新安装可从 `.env.example` 创建 `.env` 并生成密钥；恢复旧系统应安全恢复原 `.env` 和数据库。不要提交这些文件。
4. 使用服务账号配置 Google Drive 授权，确认它能访问原备份目录。私下记录原 Drive 根目录 ID，以便机器损坏后找回。
5. 检查服务器时区。定时器按服务器本地时间执行；当前为 `America/Los_Angeles`。
6. 在仓库根目录执行以下命令（需要管理员权限）。已有服务时先确认下面的配置内容，再安装：

```bash
sudo install -d -m 700 /etc/meowbillion
# 首次安装时复制模板；已有配置不要覆盖。
sudo test -f /etc/meowbillion/backup.env || sudo install -m 600 ops/backup.env.example /etc/meowbillion/backup.env
sudoedit /etc/meowbillion/backup.env
# 填入正确的 GDRIVE_ROOT_FOLDER_ID 后再继续。
sudo install -m 755 ops/meowbillion-backup /usr/local/bin/meowbillion-backup
sudo install -m 644 ops/systemd/meowbillion.service /etc/systemd/system/
sudo install -m 644 ops/systemd/meowbillion-backup.service /etc/systemd/system/
sudo install -m 644 ops/systemd/meowbillion-backup.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now meowbillion.service
# 若替换了已经运行的网站服务配置，需另行 restart 才会应用。
sudo systemctl start meowbillion-backup.service
sudo systemctl enable --now meowbillion-backup.timer
systemctl status meowbillion.service meowbillion-backup.timer
journalctl -u meowbillion-backup.service -n 50 --no-pager
curl --fail http://127.0.0.1:8090/api/auth/status
```

备份服务成功执行后应退出并显示 `status=0/SUCCESS`；oneshot 服务显示 inactive 不代表失败。`rclone.conf` 不存在的提示在此配置下正常，因为连接配置通过环境变量传入。网站绑定 `0.0.0.0`，网络访问范围仍由原有防火墙/Tailscale 配置控制；这些网络配置不包含在本目录中。

## 备份内容和恢复

备份包括项目文件、`.env` 及 SQLite backup API 生成的数据库快照；跳过 Git 历史、Python 虚拟环境和部分缓存。上传前执行数据库完整性检查。Drive `current/` 是最新副本，`versions/时间戳/` 保存被替换/删除的旧文件，清理超过约 30 天的版本目录。历史目录不是每天完整快照。

恢复时：

1. 停止网站、备份定时器，并等待或停止正在运行的备份任务，防止恢复过程再次上传覆盖备份。先另外保存现有数据库及其 WAL/SHM 和 `.env`。
2. 从 Drive 下载所需版本到临时目录；优先使用 GitHub 的对应代码版本、备份里的 `finance.db` 与原 `.env`。不要将完整备份直接覆盖到已有 Git 工作区。
3. 对下载的数据库运行 SQLite `PRAGMA integrity_check`，结果应为 `ok`。这只是结构检查，不等于业务数据验证。
4. 确认网站已停止，将旧 `finance.db`、`finance.db-wal`、`finance.db-shm` 一起移到安全保留目录，再安装备份中的 `finance.db` 和 `.env`，确保归属服务账号且私密文件权限正确。不要把旧 WAL 与恢复的数据库混用。
5. 按代码版本安装 Python 依赖，启动网站，验证登录、交易与资产数据。确认无误后恢复备份定时器。

若需恢复历史时点，先在临时目录重建：从 `current/` 复制，按时间从新到旧应用目标之后各次 `versions/` 的旧文件。该机制没有完整文件清单，新建文件的历史删除不能仅靠旧文件目录自动还原；数据库可挑选所需旧版 `finance.db`，代码版本用 Git 恢复。不要宣称任意历史目录可直接整机恢复。

本目录不保存操作系统、防火墙、Tailscale、Google 登录凭据或 App 签名密钥。它们需要单独配置或安全保存。
