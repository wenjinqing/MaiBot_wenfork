"""手动扫码登录 QQ 空间，获取完整 Cookie 并保存"""
import asyncio
import json
import os
import re
import sys
from pathlib import Path

import httpx

QRCODE_URL = "https://ssl.ptlogin2.qq.com/ptqrshow?appid=549000912&e=2&l=M&s=3&d=72&v=4&t=0.31232733520361844&daid=5&pt_3rd_aid=0"
LOGIN_CHECK_URL = "https://xui.ptlogin2.qq.com/ssl/ptqrlogin?u1=https://qzs.qq.com/qzone/v5/loginsucc.html?para=izone&ptqrtoken={}&ptredirect=0&h=1&t=1&g=1&from_ui=1&ptlang=2052&action=0-0-1656992258324&js_ver=22070111&js_type=1&login_sig=&pt_uistyle=40&aid=549000912&daid=5&has_onekey=1&&o1vId=1e61428d61cb5015701ad73d5fb59f73"
CHECK_SIG_URL = "https://ptlogin2.qzone.qq.com/check_sig?pttype=1&uin={}&service=ptqrlogin&nodirect=1&ptsigx={}&s_url=https://qzs.qq.com/qzone/v5/loginsucc.html?para=izone&f_url=&ptlang=2052&ptredirect=100&aid=549000912&daid=5&j_later=0&low_login_hour=0&regmaster=0&pt_login_type=3&pt_aid=0&pt_aaid=16&pt_light=0&pt_3rd_aid=0"

QRCODE_PATH = str(Path(__file__).parent / "qrcode.png")
COOKIE_PATH = str(Path(__file__).parent / "cookies-2477702109.json")


def get_ptqrtoken(qrsig: str) -> str:
    e = 0
    for i in range(1, len(qrsig) + 1):
        e += (e << 5) + ord(qrsig[i - 1])
    return str(2147483647 & e)


async def main():
    print("=" * 50)
    print("QQ Zone QR Login")
    print("=" * 50)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Get QR code
        print("[1/3] Fetching QR code...")
        resp = await client.get(QRCODE_URL)
        qrsig = ""
        for sc in resp.headers.get("Set-Cookie", "").split(";"):
            if sc.strip().startswith("qrsig"):
                qrsig = sc.split("=")[1].strip()
                break
        if not qrsig:
            print("FAIL: could not get qrsig")
            return

        with open(QRCODE_PATH, "wb") as f:
            f.write(resp.content)
        print(f"OK  QR saved: {QRCODE_PATH}")
        print(f"    Scan with phone QQ within 2 minutes")
        print()

        # 2. Wait for scan
        print("[2/3] Waiting for scan...")
        ptqrtoken = get_ptqrtoken(qrsig)
        cookies = None
        uin = None

        for i in range(60):
            await asyncio.sleep(2)
            try:
                check_resp = await client.get(
                    LOGIN_CHECK_URL.format(ptqrtoken),
                    cookies={"qrsig": qrsig},
                )
                text = check_resp.text
                if "二维码已失效" in text:
                    print("FAIL: QR code expired, re-run this script")
                    if os.path.exists(QRCODE_PATH):
                        os.remove(QRCODE_PATH)
                    return
                if "登录成功" in text:
                    url_part = eval(text.replace("ptuiCB", ""))[2]
                    m = re.findall(r"uin=[\d]*&", url_part)
                    uin = m[0].replace("uin=", "").replace("&", "")
                    m = re.findall(r"ptsigx=[A-z\d]*&", url_part)
                    ptsigx = m[0].replace("ptsigx=", "").replace("&", "")

                    sig_resp = await client.get(
                        CHECK_SIG_URL.format(uin, ptsigx),
                        cookies={"qrsig": qrsig},
                        headers={"Cookie": check_resp.headers.get("Set-Cookie", "")},
                    )
                    final_cookie_str = sig_resp.headers.get("Set-Cookie", "")
                    cookies = {}
                    for sc_group in final_cookie_str.split(";,"):
                        for sc in sc_group.split(";"):
                            spt = sc.strip().split("=", 1)
                            if len(spt) == 2 and spt[0] not in cookies:
                                cookies[spt[0]] = spt[1]
                    break
                print(f"    waiting... ({i+1}/60)", end="\r")
            except Exception:
                pass

        if not cookies:
            print("\nFAIL: scan timeout, no login detected")
            if os.path.exists(QRCODE_PATH):
                os.remove(QRCODE_PATH)
            return

        # 3. Save cookies
        print(f"\n[3/3] Saving cookies (uin={uin})...")
        os.makedirs(os.path.dirname(COOKIE_PATH), exist_ok=True)
        with open(COOKIE_PATH, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        print(f"OK  Cookies saved: {COOKIE_PATH}")
        key_fields = [k for k in ["p_skey", "skey", "uin", "p_uin"] if k in cookies]
        print(f"    Key fields present: {key_fields}")
        print()
        print("Now restart MaiBot, then @君君 to send a feed.")

        if os.path.exists(QRCODE_PATH):
            os.remove(QRCODE_PATH)


if __name__ == "__main__":
    asyncio.run(main())
