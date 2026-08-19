#!/usr/bin/env python3
"""
Orihost 免费 VPS 自动续期脚本
通过 sing-box 代理绕过 CF 盾
流程: 登录 → Renew → Read Article → 等广告 → Claim Renewal
"""

import asyncio
import os
import subprocess
import time
from pathlib import Path

from playwright.async_api import async_playwright

# ============ 配置 ============
LOGIN_URL = "https://panel.orihost.com/auth/login"
SOCKS_PORT = int(os.environ.get("SOCKS_PORT", "10822"))
EMAIL = os.environ.get("ORIHOST_EMAIL", "yxj0322")
PASSWORD = os.environ.get("ORIHOST_PASSWORD", "YxJ223512@")
SCREENSHOT_DIR = Path(os.environ.get("SCREENSHOT_DIR", "/tmp/orihost_screenshots"))
TG_BOT_TOKEN = os.environ.get("TG_BOT_TOKEN", "")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID", "")
HEADLESS = os.environ.get("HEADLESS", "true") == "true"


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


async def send_tg(text: str, photo: str = None):
    """发送 TG 通知"""
    if not TG_BOT_TOKEN or not TG_CHAT_ID:
        return
    import aiohttp
    url = f"https://api.telegram.org/bot{TG_BOT_TOKEN}"
    async with aiohttp.ClientSession() as sess:
        async with sess.post(f"{url}/sendMessage", json={
            "chat_id": TG_CHAT_ID, "text": text, "parse_mode": "HTML"
        }) as r:
            if r.status == 200:
                print("[TG] 推送成功")
            else:
                print(f"[TG] 推送失败: {r.status}")
        if photo and os.path.exists(photo):
            form = aiohttp.FormData()
            form.add_field("chat_id", TG_CHAT_ID)
            form.add_field("caption", text, content_type="application/json")
            form.add_field("photo", open(photo, "rb"), filename="screenshot.jpg")
            async with sess.post(f"{url}/sendPhoto", data=form) as r:
                print(f"[TG] 图片: {r.status}")


async def main():
    start_singbox()
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

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
            print("[1/6] 打开登录页面...")
            await page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(3000)

            # 2. 等待 CF Turnstile 完成（最多 60 秒）
            print("[2/6] 等待 CF 验证...")
            for i in range(60):
                await page.wait_for_timeout(1000)
                # 检查 cf-turnstile-response 是否有值
                resp = await page.evaluate("""
                    () => {
                        const input = document.querySelector('input[name="cf-turnstile-response"]');
                        return input ? input.value : null;
                    }
                """)
                if resp and len(resp) > 10:
                    print(f"      Turnstile 完成 ({i+1}s)")
                    break
                # 检查按钮是否启用
                btn_enabled = await page.evaluate("""
                    () => {
                        const btn = document.querySelector('button[type="submit"]');
                        return btn ? !btn.disabled : false;
                    }
                """)
                if btn_enabled:
                    print(f"      按钮已启用 ({i+1}s)")
                    break
                if i % 10 == 0:
                    print(f"      等待中... {i+1}s")
            else:
                print("      [!] Turnstile 等待超时，继续尝试...")

            await page.screenshot(path=str(SCREENSHOT_DIR / "01_turnstile_done.jpg"))

            # 3. 填写表单并登录
            print("[3/6] 登录...")
            await page.wait_for_timeout(500)
            await page.fill('input[name="username"]', EMAIL)
            await page.fill('input[name="password"]', PASSWORD)
            await page.click('button[type="submit"]')
            print(f"      账号: {EMAIL}")
            print("      已点击 Sign In")
            await page.wait_for_timeout(5000)

            # 检查登录结果
            current_url = page.url
            if "login" in current_url.lower() or "auth" in current_url.lower():
                print("[!] 登录失败")
                await page.screenshot(path=str(SCREENSHOT_DIR / "02_login_fail.jpg"))
                await send_tg("❌ Orihost 续期失败：登录失败")
                return
            print("[3/6] 登录成功 ✅")
            await page.screenshot(path=str(SCREENSHOT_DIR / "03_logged_in.jpg"))

            # 4. 点击 Renew
            print("[4/6] 点击 Renew...")
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
                print("[!] 未找到 Renew 按钮")
                await page.screenshot(path=str(SCREENSHOT_DIR / "04_no_renew.jpg"))
                await send_tg("❌ Orihost 续期失败：未找到 Renew 按钮")
                return
            print("      已点击 Renew")
            await page.wait_for_timeout(3000)

            # 5. 点击 Read Article
            print("[5/6] 点击 Read Article...")
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
                print("[!] 未找到 Read Article 按钮")
                await page.screenshot(path=str(SCREENSHOT_DIR / "05_no_read_article.jpg"))
                await send_tg("❌ Orihost 续期失败：未找到 Read Article 按钮")
                return
            print("      已点击 Read Article，等待广告...")

            # 6. 等待倒计时结束 + 点击 Claim Renewal
            print("[6/6] 等待广告并 Claim...")
            claim_clicked = False
            for i in range(45):  # 最多等 45 秒
                await page.wait_for_timeout(1000)
                btn = await page.query_selector('button:has-text("Claim Renewal")')
                if btn:
                    text = await btn.inner_text()
                    if text.strip():
                        print(f"      Claim 出现（等待 {i+1}s），点击...")
                        await btn.click()
                        claim_clicked = True
                        break
                if i > 0 and i % 10 == 0:
                    print(f"      等待中... {i}s")

            if not claim_clicked:
                print("[!] 未找到 Claim Renewal 按钮")
                await page.screenshot(path=str(SCREENSHOT_DIR / "06_no_claim.jpg"))
                await send_tg("❌ Orihost 续期失败：未找到 Claim Renewal 按钮")
                return

            # 等待结果
            print("      等待续期结果...")
            await page.wait_for_timeout(8000)

            # 截图 + 检查
            result_screenshot = SCREENSHOT_DIR / "07_result.jpg"
            await page.screenshot(path=str(result_screenshot))
            print(f"      截图: {result_screenshot}")

            body_text = await page.inner_text("body")
            if "17 Days" in body_text or "Renewal" in body_text or "success" in body_text.lower():
                msg = "✅ Orihost 续期成功！"
            elif "error" in body_text.lower() or "failed" in body_text.lower():
                msg = "❌ Orihost 续期失败"
            else:
                msg = "⚠️ Orihost 续期状态未知，请检查截图"
            print(msg)

            await send_tg(msg, str(result_screenshot))

        except Exception as e:
            print(f"[!] 异常: {e}")
            import traceback
            traceback.print_exc()
            try:
                await page.screenshot(path=str(SCREENSHOT_DIR / "error.jpg"))
                await send_tg(f"❌ Orihost 续期异常：{e}")
            except:
                pass
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())