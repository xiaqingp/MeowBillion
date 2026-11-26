# 服务器运行配置：仓库为唯一来源

`ops/` 是运行配置和备份脚本的唯一维护位置。系统路径里的文件是安装副本，不直接编辑。GitHub push 本身不会安装或重启服务。

## 唯一安装入口

先修改仓库、验证并提交，再执行：

```bash
cd /home/xiaqingp/MeowBillion
sudo python3 ops/manage.py install
```

安装器只接受已提交且干净的 `ops/`，自动执行以下步骤：

1. 检查脚本语法、拒绝仓库之外的 systemd drop-in，检查私有备份配置。
2. 暂停备份定时器，等待当前备份结束，避免更新运行中的任务。
3. 原样安装下表中的文件，设置权限，并记录提交号及 SHA-256 清单。
4. 验证 systemd 配置、执行 daemon-reload，逐文件核对仓库、安装文件和清单一致。
5. 重启网站并检查 HTTP；实际运行已安装的备份服务，上传后重新下载验证。
6. 启用网站及备份定时器的开机启动，再次检查一致性，全部成功才报告 `INSTALL VERIFIED`。

安装需要管理员权限。使用互斥锁防止两个安装同时进行。文件安装/配置验证失败会尝试恢复先前的系统文件；文件一致性验证通过后的服务或备份失败会保留已匹配仓库的配置，明确返回失败供排查，不会假报安装成功。第一次备份验证失败时不要认为恢复能力已得到确认；检查日志后重新执行安装命令。

| 仓库文件 | 安装位置 |
| --- | --- |
| `systemd/meowbillion.service` | `/etc/systemd/system/meowbillion.service` |
| `systemd/meowbillion-backup.service` | `/etc/systemd/system/meowbillion-backup.service` |
| `systemd/meowbillion-backup.timer` | `/etc/systemd/system/meowbillion-backup.timer` |
| `meowbillion-backup` | `/usr/local/bin/meowbillion-backup` |
| `manage.py` | `/usr/local/lib/meowbillion/manage.py` |

安装记录位于 `/var/lib/meowbillion/ops-installed.json`。它记录安装来源，不是另一套可编辑配置。

## 一致性检查

```bash
python3 ops/manage.py check
```

检查文件内容、权限、root 所有权、提交状态、安装清单及 systemd 加载路径；拒绝额外覆盖配置和未执行 daemon-reload 的状态。网站和备份服务的 `ExecStartPre` 都执行已安装的同一检查器，失败就拒绝启动该次服务。

这能在安装结束、手动检查和服务启动时发现偏离，不是持续监控，也不能阻止管理员绕过工具直接修改文件。修改/拉取新的 `ops/` 后应及时安装，期间旧服务若重启会因配置不一致而拒绝启动。普通应用代码提交不需要重新安装 ops。

## 私有参数与当前机器

账号和路径固定为当前服务器的 `xiaqingp`、`/home/xiaqingp/MeowBillion`；换机器使用同一布局，或在仓库中修改脚本、安装器和 unit 后重新提交。

`/etc/meowbillion/backup.env` 是唯一机器私有参数文件，只允许一项：

```dotenv
GDRIVE_ROOT_FOLDER_ID=实际的备份根目录ID
```

它不进入 Git，归 root 所有、权限 0600，由 systemd 读取后传入备份进程。首次安装在本机自动从原备份脚本迁移原有目录 ID，不在日志中打印；新机器没有旧脚本时，管理员先按 `backup.env.example` 创建此文件。之后安装保留并验证它，不覆盖目标。

Google OAuth 授权保存在服务账号自身的 gcloud 配置中，不能提交到 Git。账号必须拥有目标 Drive 的访问权限及相应 OAuth scope。备份通过短期令牌连接 rclone，不依赖 `rclone.conf`；缺少该文件的 NOTICE 在本配置下正常。

## 新机器准备

安装 Git、Python 3（含 venv）、rsync、rclone、Google Cloud CLI、flock。测试还需要 Node.js。恢复/克隆代码，建立 `.venv` 并安装 `requirements.txt`，安全恢复 `.env`、数据库和 Google 授权。定时器按服务器本地时间每天 02:00 运行，当前时区是 `America/Los_Angeles`，关机错过后补执行。最后运行上述唯一安装入口。

网站仍绑定 `0.0.0.0:8090`；网络访问范围由现有防火墙/Tailscale 控制。这些网络配置、操作系统和 App 签名密钥不在本目录中。

## 每次备份的验证

1. rsync 暂存代码和 `.env`，跳过 Git 历史、虚拟环境和部分缓存。
2. SQLite backup API 生成一致性数据库快照并做完整性检查。
3. rclone 将文件同步到 Drive `current/`，旧文件移入 `versions/时间戳/`。
4. 从 Drive 下载 `current/` 到临时目录，比对全部文件 SHA-256，并检查数据库完整性及关键表可读。
5. 验证成功后才清理超过约 30 天的版本；退出时删除下载的临时副本。

验证过程中不覆盖生产数据库，不启动恢复出来的 App，不向银行发起同步。因此它证明文件往返完整、数据库可读，不等于人工验证了每个业务页面或任意历史时点。脚本互斥锁避免新版备份同时运行。

查看结果：

```bash
journalctl -u meowbillion-backup.service -n 60 --no-pager
systemctl status meowbillion.service meowbillion-backup.timer
```

备份 oneshot 执行完成后 inactive 是正常状态，成功应为 `status=0/SUCCESS`，日志包含 `Restore verification OK`。

## 人工恢复

先停止网站、备份定时器及备份任务，另存当前数据库、WAL/SHM 和 `.env`。从 Drive 下载到临时目录，检查数据库完整性；用 Git 恢复对应代码版本。确认网站已停止后，将旧数据库及 WAL/SHM 一起移走，再安装备份数据库和 `.env`，确保账号与权限正确。恢复 Python 依赖，通过安装入口恢复 ops。网站启动后核对登录、交易与资产，再确认定时备份正常。

`versions/` 是被替换/删除的旧文件集合，不是完整每日快照。恢复旧数据库需选取对应的 `finance.db`；恢复代码使用 Git。缺少完整历史文件清单时，不能把任一版本目录当作整机备份。

## 本次验证记录（2026-11-26）

仓库版脚本已直接完成真实 Drive 上传、重新下载、全部文件哈希比对、SQLite 完整性及关键表读取检查。Python 测试套件 118 项通过，覆盖配置内容/权限/缺失文件/符号链接漂移，以及 systemd 覆盖配置与未重载状态。Bash 语法及 systemd 静态检查通过。

当前操作账号缺少安装到系统目录的 sudo 权限，因此尚未完成管理员安装，旧系统配置仍在运行。直接运行仓库脚本的验证不等于已安装 systemd 服务的验证；管理员执行安装入口后，安装器会重新完成后者并打印 `INSTALL VERIFIED`。本地 App 最新代码同步仍需在本地电脑核对。
