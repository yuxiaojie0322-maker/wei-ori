#!/usr/bin/env python3
"""
Orihost 免费 VPS 自动续期脚本（多账号版）
通过 sing-box 代理绕过 CF 盾
流程: 登录 → Renew → Read Article → 等广告 → Claim Renewal

多账号配置：通过 ORIHOST_ACCOUNTS 环境变量传入 JSON 数组
  格式: [{"email":"xxx","password":"xxx","name":"别名"},{"email":"yyy","password":"yyy","name":"别名2"}]
  也支持单账号: ORIHOST_EMAIL + ORIHOST_PASSWORD（兼容旧用法）
"""

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

# ============ 配置 ============
LOGIN_URL = "https://panel.orihost.com/auth/login"
SOCKS_PORT = int(os.environ.get("SOCKS_PORT", "10822"))
SCREENSHOT_DIR = Path(os.environ.get("SCREENSHOT_DIR", "/tmp/orihost_screenshots"))
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")
HEADLESS = os.environ.get("HEADLESS", "true") == "true"

# 多账号支持
ACCOUNTS_JSON = os.environ.get("ORIHOST_ACCOUNTS", "")
ORIHOST_EMAIL = os.environ.get("ORIHOST_EMAIL", "")
ORIHOST_PASSWORD = os.environ.get("ORIHOST_PASSWORD", "")


def parse_accounts():
    """解析账号列表"""
    if ACCOUNTS_JSON:
        try:
            accounts = json.loads(ACCOUNTS_JSON)
            result = []
            for acc in accounts:
                result.append({
                    "email": acc["email"],
                    "password": acc["password"],
                    "name": acc.get("name", acc["email"]),
                })
            return result
        except Exception as e:
            print(f"[!] ORIHOST_ACCOUNTS JSON 解析失败: {e}")
    if ORIHOST_EMAIL and ORIHOST_PASSWORD:
        return [{"email": ORIHOST_EMAIL, "password": ORIHOST_PASSWORD, "name": ORIHOST_EMAIL}]
    print("[!] 未找到任何账号配置，退出")
    sys.exit(1)


# ============ 代理管理 ============
def start_singbox():
    """启动 sing-box 代理"""
    result = subprocess.run(
        ["fuser", f"{SOCKS_PORT}/tcp"], capture_output=True, text=True
    )
    if result.stdout.strip():
        print(f"[sing-box] 端口 {SOCKS_PORT} 已占用，跳过")
        return
    conf = "/etc/sing-box/orihost/config.json"
    subprocess.run(
        ["nohup", "sing-box", "run", "-c", conf, ">", "/tmp/sing-box-orihost.log", "2>&1", "&"],
        shell=True, check=True
    )
    time.sleep(2)
    print(f"[sing-box] 已启动 socks5://127.0.0.1:{SOCKS_PORT}")


# ============ TG 推送 ============
async def send_tg(account_name: str, text: str, photo: str = None):
    """发送 TG 通知"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        print(f"[{account_name}] TG 未配置，跳过推送")
        return
    import aiohttp
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"
    # 加上账号名前缀
    full_text = f"📍 {account_name}\n{text}"
    async with aiohttp.ClientSession() as sess:
        async with sess.post(f"{url}/sendMessage", json={
            "chat_id": TG_CHAT_ID, "text": full_text, "parse_mode": "HTML"
        }) as r:
            if r.status == 200:
                print(f"[{account_name}] TG 推送成功")
            else:
                print(f"[{account_name}] TG 推送失败: {r.status}")
        if photo and os.path.exists(photo):
            form = aiohttp.FormData()
            form.add_field("chat_id", TG_CHAT_ID)
            form.add_field("caption", full_text, content_type="application/json")
            form.add_field("photo", open(photo, "rb"), filename="screenshot.jpg")
            async with sess.post(f"{url}/sendPhoto", data=form) as r:
                print(f"[{account_name}] 图片: {r.status}")


async def run_account(account: dict):
    """执行单个账号的续期流程"""
    email = account["email"]
    password = account["password"]
    name = account["name"]
    print(f"\n{'='*50}")
    print(f"📍 开始处理账号: {name} ({email})")
    print(f"{'='*50}")

    proxy = {"server": f"socks5://127.0.0.1:{SOCKS_PORT}"}
    browser_opts = {
        "headless": HEADLESS,
        "proxy": proxy,
        "args": ["--ignore-certificate-errors", "--ignore-certificate-errors-spki-list"],
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(**browser_opts)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
        )
        page = await ctx.new_page()

        try:
            # 1. 打开登录页
            print(f"[{name}] [1/6] 打开登录页面...")
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            # 2. 等待 CF Turnstile 完成（最多 60 秒）
            print(f"[{name}] [2/6] 等待 CF 验证...")
            for i in range(60):
                await page.wait_for_timeout(1000)
                resp = await page.evaluate("""
                    () => {
                        const input = document.querySelector('input[name="cf-turnstile-response"]');
                        return input ? input.value : null;
                    }
                """)
                if resp and len(resp) > 10:
                    print(f"[{name}]      Turnstile 完成 ({i+1}s)")
                    break
                btn_enabled = await page.evaluate("""
                    () => {
                        const btn = document.querySelector('button[type="submit"]');
                        return btn ? !btn.disabled : false;
                    }
                """)
                if btn_enabled:
                    print(f"[{name}]      按钮已启用 ({i+1}s)")
                    break
                if i % 10 == 0:
                    print(f"[{name}]      等待中... {i+1}s")
            else:
                print(f"[{name}]      [!] Turnstile 等待超时，继续尝试...")

            # 3. 填写表单并登录
            print(f"[{name}] [3/6] 登录...")
            await page.wait_for_timeout(500)
            await page.fill('input[name="username"]', email)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            print(f"[{name}]      已点击 Sign In")
            await page.wait_for_timeout(5000)

            # 检查登录结果
            current_url = page.url
            if "login" in current_url.lower() or "auth" in current_url.lower():
                print(f"[{name}] [!] 登录失败")
                await page.screenshot(path=str(SCREENSHOT_DIR / f"{name}_login_fail.jpg"))
                await send_tg(name, "❌ 登录失败\n请检查账号密码或 CF 盾验证")
                return False
            print(f"[{name}] [3/6] 登录成功 ✅")

            # 4. 点击 Renew
            print(f"[{name}] [4/6] 点击 Renew...")
            await page.wait_for_timeout(2000)
            renew_clicked = await page.evaluate("""
                () => {
                    const btn = document.querySelector('button:has-text("Renew")');
                    if (btn) { btn.click(); return true; }
                    const all = document.querySelectorAll('button');
                    for (const b of all) {
                        if (b.textContent.includes('Renew')) { b.click(); return true; }
                    }
                    return false;
                }
            """)
            if not renew_clicked:
                print(f"[{name}] [!] 未找到 Renew 按钮")
                await page.screenshot(path=str(SCREENSHOT_DIR / f"{name}_no_renew.jpg"))
                await send_tg(name, "❌ 续期失败：未找到 Renew 按钮")
                return False
            print(f"[{name}]      已点击 Renew")
            await page.wait_for_timeout(3000)

            # 5. 点击 Read Article
            print(f"[{name}] [5/6] 点击 Read Article...")
            read_article_clicked = await page.evaluate("""
                () => {
                    const btn = document.querySelector('button:has-text("Read Article")');
                    if (btn) { btn.click(); return true; }
                    const all = document.querySelectorAll('button');
                    for (const b of all) {
                        if (b.textContent.includes('Read Article')) { b.click(); return true; }
                    }
                    return false;
                }
            """)
            if not read_article_clicked:
                print(f"[{name}] [!] 未找到 Read Article 按钮")
                await page.screenshot(path=str(SCREENSHOT_DIR / f"{name}_no_read_article.jpg"))
                await send_tg(name, "❌ 续期失败：未找到 Read Article 按钮")
                return False
            print(f"[{name}]      已点击 Read Article，等待广告...")

            # 6. 等待倒计时结束 + 点击 Claim Renewal
            print(f"[{name}] [6/6] 等待广告并 Claim...")
            claim_clicked = False
            for i in range(45):
                await page.wait_for_timeout(1000)
                btn = await page.query_selector('button:has-text("Claim Renewal")')
                if btn:
                    text = await btn.inner_text()
                    if text.strip():
                        print(f"[{name}]      Claim 出现（等待 {i+1}s），点击...")
                        await btn.click()
                        claim_clicked = True
                        break
                if i > 0 and i % 10 == 0:
                    print(f"[{name}]      等待中... {i}s")

            if not claim_clicked:
                print(f"[{name}] [!] 未找到 Claim Renewal 按钮")
                await page.screenshot(path=str(SCREENSHOT_DIR / f"{name}_no_claim.jpg"))
                await send_tg(name, "❌ 续期失败：未找到 Claim Renewal 按钮")
                return False

            # 等待结果
            print(f"[{name}]      等待续期结果...")
            await page.wait_for_timeout(8000)

            # 截图 + 检查
            result_screenshot = SCREENSHOT_DIR / f"{name}_result.jpg"
            await page.screenshot(path=str(result_screenshot))
            print(f"[{name}]      截图已保存")

            body_text = await page.inner_text("body")
            if "17 Days" in body_text or "Renewal" in body_text or "success" in body_text.lower():
                msg = "✅ 续期成功！+17 天"
                print(f"[{name}] {msg}")
            elif "error" in body_text.lower() or "failed" in body_text.lower():
                msg = "❌ 续期失败"
                print(f"[{name}] {msg}")
            else:
                msg = "⚠️ 续期状态未知，请检查截图"
                print(f"[{name}] {msg}")

            await send_tg(name, msg, str(result_screenshot))
            return True

        except Exception as e:
            print(f"[{name}] [!] 异常: {e}")
            import traceback
            traceback.print_exc()
            try:
                await page.screenshot(path=str(SCREENSHOT_DIR / f"{name}_error.jpg"))
                await send_tg(name, f"❌ 异常：{e}")
            except:
                pass
            return False
        finally:
            await browser.close()


async def main():
    accounts = parse_accounts()
    print(f"共找到 {len(accounts)} 个账号待处理")

    start_singbox()
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    for account in accounts:
        success = await run_account(account)
        results.append((account["name"], success))

    # 汇总结果
    print(f"\n{'='*50}")
    print("📊 续期汇总")
    print(f"{'='*50}")
    success_count = sum(1 for _, ok in results if ok)
    for name, ok in results:
        status = "✅ 成功" if ok else "❌ 失败"
        print(f"  {name}: {status}")
    print(f"\n总计: {success_count}/{len(results)} 个账号续期成功")


if __name__ == "__main__":
    asyncio.run(main())