# 🔄 Orihost 免费 VPS 自动续期

自动续期 Orihost 免费 VPS（每次 +7 天）。

## 功能

- ✅ 自动处理 Cloudflare Turnstile 验证
- ✅ 通过 sing-box 代理绕过地区限制
- ✅ 自动点击 Renew → Read Article → 等待广告 → Claim Renewal
- ✅ Telegram 推送结果 + 截图
- ✅ GitHub Actions 每日自动执行

## 部署步骤

### 1. 创建 GitHub 仓库

打开 https://github.com/new → 填仓库名 → 选 **Private** → 创建

### 2. 推送代码

```bash
# 在你的电脑上
git clone https://github.com/你的用户名/你的仓库名.git
cp -r renew_orihost/* 你的仓库名/
cd 你的仓库名
git add .
git commit -m "初始化：Orihost 自动续期脚本"
git push -u origin main
```

### 3. 设置 Secrets

仓库 → Settings → Secrets and variables → Actions → New repository secret

#### 方式一：多账号（推荐）

添加一个 Secret `ORIHOST_ACCOUNTS`，值为 JSON 数组，每个账号一个对象：

```json
[
  {"email":"账号1","password":"密码1","name":"别名1"},
  {"email":"账号2","password":"密码2","name":"别名2"}
]
```

脚本会自动遍历每个账号，逐一续期并各自推送 TG 通知。

#### 方式二：单账号

| Secret | 值 |
|--------|-----|
| `ORIHOST_EMAIL` | 你的 Orihost 邮箱/用户名 |
| `ORIHOST_PASSWORD` | 你的 Orihost 密码 |
| `TG_BOT_TOKEN` | Telegram Bot Token |
| `TG_CHAT_ID` | Telegram 用户 ID |

### 4. 手动触发测试

Actions → Orihost 每日续期 → Run workflow

每天 UTC 2:00（北京时间 10:00）自动续期。

## 本地运行

```bash
pip install -r requirements.txt
playwright install chromium

# 确保 sing-box 已启动
nohup sing-box run -c /etc/sing-box/config.json > /tmp/sing-box.log 2>&1 &

# 运行
ORIHOST_EMAIL=your@email.com ORIHOST_PASSWORD=yourpassword \
TG_BOT_TOKEN=xxx TG_CHAT_ID=xxx \
python renew_orihost.py
```
