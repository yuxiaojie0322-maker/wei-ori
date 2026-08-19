# GitHub 仓库配置指南

## 1. 创建仓库

打开 https://github.com/new → 填仓库名（如 `orihost-renew`）→ 选 **Private** → 创建

## 2. 推送代码

```bash
git clone https://github.com/你的用户名/orihost-renew.git
cp -r renew_orihost/* orihost-renew/
cd orihost-renew
git add .
git commit -m "初始化：Orihost 自动续期脚本"
git push -u origin main
```

## 3. 设置 Secrets

仓库 → Settings → Secrets and variables → Actions → New repository secret

| Secret | 值 |
|--------|-----|
| `ORIHOST_EMAIL` | `yxj0322` |
| `ORIHOST_PASSWORD` | `YxJ223512@` |
| `TG_BOT_TOKEN` | `8867499536:AAF2vlfTao3wvy0x7HdlNhZJgfqi5i_vINk` |
| `TG_CHAT_ID` | `7772205808` |

## 4. 触发测试

Actions → **Orihost 每日续期** → **Run workflow**

每天 UTC 2:00（北京时间 10:00）自动执行。