# GitHub 仓库配置指南

## 1. 创建仓库

打开 https://github.com/new → 填仓库名 → 选 **Private** → 创建

## 2. 推送代码

```bash
git clone https://github.com/你的用户名/你的仓库名.git
cp -r renew_orihost/* 你的仓库名/
cd 你的仓库名
git add .
git commit -m "初始化：Orihost 自动续期脚本"
git push -u origin main
```

## 3. 设置 Secrets

仓库 → Settings → Secrets and variables → Actions → New repository secret

### 方式一：多账号（推荐）

添加一个 Secret `ORIHOST_ACCOUNTS`，值为 JSON 数组：

```json
[
  {"email":"账号1","password":"密码1","name":"别名1"},
  {"email":"账号2","password":"密码2","name":"别名2"}
]
```

脚本会遍历每个账号，各自续期并推送 TG 通知。

### 方式二：单账号

| Secret | 值 |
|--------|-----|
| `ORIHOST_EMAIL` | 你的 Orihost 邮箱/用户名 |
| `ORIHOST_PASSWORD` | 你的 Orihost 密码 |
| `TG_BOT_TOKEN` | Telegram Bot Token |
| `TG_CHAT_ID` | Telegram 用户 ID |

## 4. 触发测试

Actions → **Orihost 每日续期** → **Run workflow**

每天 UTC 2:00（北京时间 10:00）自动执行。