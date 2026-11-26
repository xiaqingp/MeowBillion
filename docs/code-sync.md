# 代码同步与备份

网站、API、App 共用 GitHub 仓库 `xiaqingp/MeowBillion`。服务器继续在 `~/MeowBillion` 的 `main` 分支开发和运行网站/API，本地电脑开发 `mobile/`。不新增开发服务或自动部署。

## 每次修改

1. 开始前运行 `git status`，有未完成修改时先处理，不直接覆盖。
2. 运行 `git fetch origin`，然后在工作区干净时执行 `git pull --ff-only`。
3. 修改并测试；服务器修改的是运行目录，重启后会加载这些修改。数据库改动前先执行现有备份并确认成功。
4. 用 `git add <具体文件>` 选择代码，运行 `git diff --cached` 检查内容。
5. `git commit -m "说明修改"`，然后 `git push origin main`。

服务器已设置 `pull.ff=only`、`push.default=simple` 和 `fetch.prune=true`。本地电脑应对同一仓库设置相同选项。没有设置自动 push 或自动 merge。

若两端都有新提交，pull 会拒绝快进：先保存当前工作，再由开发者明确合并 `origin/main`、解决冲突、测试并 push。禁止用 `push --force` 或 `reset --hard` 解决同步问题。多人同时修改时可使用短期分支和 PR。

## App 本地接入

本地先检查 `git remote -v` 和 `git status`，确认当前代码是否已经属于此仓库。存在未推送 App 修改时先在本地保存提交，再 fetch 并比较；不要直接用服务器版本覆盖本地文件。远端已有 `mobile/`，但不能据此认定它就是本地最新版本。

## 发布与恢复

GitHub push 只备份代码，不会自动重启服务。需要发布时，确认本机代码和依赖无误后由具备权限的操作者重启 `meowbillion.service`，检查网站/API。现有 systemd 服务与每日 Google Drive 备份保持原样。

GitHub 不保存真实数据库、WAL/SHM、`.env`、签名密钥和本地归档。财务数据继续由服务器每日备份到 Google Drive。不要将数据库放进 Git，也不要把未提交代码的 Drive 副本当成 Git 同步。

## 初始同步状态（2026-11-26）

服务器有四个此前未提交的业务修复文件，作为当前运行代码快照单独提交：`database.py`、`routes_plaid.py`、`transaction_dedup.py`、`tests/test_investment_income_sync.py`。此次同步未修改其业务逻辑。

此前对相同应用代码运行 109 项测试，107 项通过，2 项失败：交易修改日期断言，以及前端子分类筛选的字符串断言。这份快照是备份现有运行状态，不代表测试全部通过；后续业务发布前应处理这两个问题。
