# Smart Waste Quick Start Memo

首次从 GitHub 复现时，按顺序在 PowerShell 中运行以下命令。`docker compose up`
会重新构建镜像并启动全部容器。

```powershell
git clone https://github.com/tung-sahura/smart-waste-softing.git
cd smart-waste-softing
docker compose up --build -d
docker compose exec app python3 -m unittest discover -s tests -v
```

测试全部通过时应看到：

```text
Ran 30 tests in ...
OK
```

## Git Local Commit

首次使用 Git 时，先配置提交作者。把姓名和邮箱替换成自己的 GitHub 信息：

```powershell
git config --global user.name "你的姓名或 GitHub 用户名"
git config --global user.email "你的GitHub邮箱"
```

进入项目目录后，把公开文件加入本地 Git 仓库：

```powershell
cd smart-waste-softing
git init -b main
git add .
git status --short
git commit -m "feat: complete smart waste sorting assessment"
```

`git add .` 会遵守 `.gitignore`，因此 `AGENTS.md`、`TASKS.md` 和 `local-only/`
不会进入 Git。提交前应确认 `git status --short` 中没有这些文件。

检查提交结果：

```powershell
git log --oneline
git status
```

## GitHub Upload

先在 GitHub 创建一个空仓库，然后把下面的地址替换成实际仓库地址：

```powershell
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main
```

如果远程仓库地址已经存在，可以检查或修改：

```powershell
git remote -v
git remote set-url origin https://github.com/你的用户名/你的仓库名.git
```

## Docker Web UI

容器启动后，在浏览器打开：

```text
http://localhost:6080/vnc.html?autoconnect=1&resize=scale
```

## Stop

停止并删除当前容器，但保留镜像：

```powershell
docker compose down
```
