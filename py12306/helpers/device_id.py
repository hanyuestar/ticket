# -*- coding: utf-8 -*-
"""
12306 浏览器会话预热 / 设备指纹 (RAIL_DEVICEID) 获取 —— 无头浏览器方案

背景（2026-09 实测验证）：
    12306 已强化风控：
    - 旧的明文 GET /otn/HttpZF/logdevice 流程被 302 拒绝（跳 error.html），
      request_device_id2() 拿不到 RAIL_DEVICEID。
    - 但实测发现：查询接口 302 的真正原因不是缺少 RAIL_DEVICEID——
      在无任何 RAIL Cookie 的干净无头浏览器会话中，queryG 直接返回 200 真实数据；
      将浏览器会话 Cookie（_uab_collina / JSESSIONID / BIGipServerotn / SF_cookie_2 等，
      由页面 JS 与服务端会话建立）导出给 Python requests 后，查询同样 200。
    - 结论：风控针对的是"会话是否由真实浏览器环境建立"，而非设备指纹本身。

方案（两级）：
    1. 会话预热（核心）：无头浏览器打开余票查询页，由 12306 自家 JS 完成
      反爬 Cookie 种植，把整套 Cookie + UA 导入 py12306 的 requests 会话，
      查询即可通过。对应 fetch_browser_session()。
    2. 设备指纹（兼容）：部分场景（登录/下单）仍校验 RAIL_DEVICEID，
      浏览器方案顺路等待指纹 Cookie。对应 fetch_device_id_by_browser()。

说明：
    - 本模块不依赖 py12306 内部包（可独立测试），日志由调用方输出。
    - 浏览器候选：优先系统已安装的 Chrome/Edge/Chromium；全部缺失时才回退
      pyppeteer 自带 Chromium（Docker 镜像已预下载），且仅在其二进制存在时启用。
    - 进程级熔断：浏览器方案失败一次后，本进程内不再重试，避免每次
      预热都白等几十秒。
"""
import asyncio
import os
import threading

# 与 query.py 中保持一致的浏览器 UA（标准 Chrome UA，避免 HeadlessChrome 字样）
BROWSER_UA = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
)

INIT_PAGE_URL = 'https://kyfw.12306.cn/otn/leftTicket/init'

# 页面加载后等待指纹 Cookie 出现的最长秒数（指纹 JS 执行需要几秒）
WAIT_COOKIE_SECONDS = 30
# 会话 Cookie（反爬 JS 种植）等待的最长秒数
WAIT_SESSION_SECONDS = 30
# 页面导航超时秒数
NAVIGATE_TIMEOUT_SECONDS = 60

# 会话预热需要拿到的关键 Cookie（缺一视为预热失败）
SESSION_COOKIES_REQUIRED = ('JSESSIONID', 'BIGipServerotn', '_uab_collina')

# 浏览器候选（None 表示 pyppeteer 自带 Chromium，仅作最后兜底，
# 且仅在其二进制确实已下载时才启用，见 _normalize_candidates）
_SYSTEM_BROWSER_CANDIDATES = [
    'C:/Program Files/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Google/Chrome/Application/chrome.exe',
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    None,
]

# 进程级熔断标志
_browser_disabled = threading.Event()


def _normalize_candidates():
    """
    过滤候选列表：
    - 不存在的系统浏览器路径直接剔除；
    - None（pyppeteer 自带 Chromium）只有在其二进制确实存在时才保留，
      否则 launch 会触发联网下载 Chromium（可能失败/卡死）。
    """
    candidates = [c for c in _SYSTEM_BROWSER_CANDIDATES
                  if c is None or os.path.exists(c)]
    if None in candidates:
        try:
            from pyppeteer.chromium_downloader import chromium_executable_path
            path = chromium_executable_path()
            if not (path and os.path.exists(str(path))):
                candidates.remove(None)
        except Exception:
            candidates.remove(None)
    return candidates


def is_browser_fingerprint_available():
    """
    浏览器方案是否可用：pyppeteer 可导入且进程未熔断。
    """
    if _browser_disabled.is_set():
        return False
    try:
        import pyppeteer  # noqa: F401
    except Exception:
        _browser_disabled.set()
        return False
    return True


def fetch_browser_session():
    """
    浏览器会话预热：无头浏览器打开 12306 余票查询页，等待 12306 自家
    反爬 JS 种下会话 Cookie，然后采集整套 Cookie。

    :return: {'cookies': {name: value, ...}, 'user_agent': str}；失败返回 None
    """
    result = _run_browser_flow(wait_rail=False)
    if not result:
        return None
    return {
        'cookies': result['cookies'],
        'user_agent': result.get('user_agent') or BROWSER_UA,
    }


def fetch_device_id_by_browser():
    """
    通过无头浏览器获取设备指纹 (RAIL_DEVICEID / RAIL_EXPIRATION)。

    :return: {'RAIL_DEVICEID': xx, 'RAIL_EXPIRATION': xx}；失败返回 None
    """
    result = _run_browser_flow(wait_rail=True)
    if not result:
        return None
    device_id = result['cookies'].get('RAIL_DEVICEID')
    expiration = result['cookies'].get('RAIL_EXPIRATION')
    if device_id and expiration:
        return {'RAIL_DEVICEID': device_id, 'RAIL_EXPIRATION': expiration}
    return None


def _run_browser_flow(wait_rail):
    """
    遍历浏览器候选执行采集流程；全部失败则熔断本进程的浏览器方案。

    :param wait_rail: 是否额外等待 RAIL_DEVICEID / RAIL_EXPIRATION 指纹 Cookie
    :return: {'cookies': {...}, 'user_agent': ...}；失败返回 None
    """
    if not is_browser_fingerprint_available():
        return None
    candidates = _normalize_candidates()
    if not candidates:
        # 本机无任何可用浏览器，熔断本进程的浏览器方案
        _browser_disabled.set()
        return None
    for executable in candidates:
        try:
            result = _run_with_new_loop(executable, wait_rail)
            if result:
                return result
        except Exception:
            # 当前浏览器候选失败，尝试下一个
            continue
    # 所有候选均失败，熔断本进程的浏览器方案
    _browser_disabled.set()
    return None


def _run_with_new_loop(executable, wait_rail):
    """
    在独立事件循环中执行采集（py12306 的查询运行在工作线程中，
    不能依赖主线程事件循环）。
    """
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_collect_by_browser(executable, wait_rail))
    finally:
        loop.close()


async def _collect_by_browser(executable, wait_rail):
    from pyppeteer import launch

    launch_kwargs = {
        'headless': True,
        'handleSIGINT': False,
        'handleSIGTERM': False,
        'handleSIGHUP': False,
        'args': [
            '--no-sandbox',
            '--disable-dev-shm-usage',
            '--disable-gpu',
            # 从浏览器层面移除 navigator.webdriver 自动化标志
            '--disable-blink-features=AutomationControlled',
            f'--user-agent={BROWSER_UA}',
        ],
    }
    if executable:
        launch_kwargs['executablePath'] = executable

    browser = await launch(**launch_kwargs)
    try:
        page = await browser.newPage()
        await page.setUserAgent(BROWSER_UA)
        await page.setViewport({'width': 1366, 'height': 768})
        await page.goto(
            INIT_PAGE_URL,
            options={'waitUntil': 'networkidle2', 'timeout': NAVIGATE_TIMEOUT_SECONDS * 1000},
        )

        # 阶段一：等待会话 Cookie（反爬 JS 种植）
        waited = 0
        while waited < WAIT_SESSION_SECONDS:
            cookies = await page.cookies()
            values = {c.get('name'): c.get('value') for c in cookies}
            if all(name in values for name in SESSION_COOKIES_REQUIRED):
                break
            await asyncio.sleep(1)
            waited += 1
        else:
            return None  # 会话 Cookie 未就绪

        result = {'cookies': values, 'user_agent': BROWSER_UA}

        if wait_rail:
            # 阶段二（可选）：继续等待设备指纹 Cookie（指纹 JS 需额外几秒）
            waited = 0
            while waited < WAIT_COOKIE_SECONDS:
                cookies = await page.cookies()
                values = {c.get('name'): c.get('value') for c in cookies}
                if 'RAIL_DEVICEID' in values and 'RAIL_EXPIRATION' in values:
                    result['cookies'] = values
                    break
                await asyncio.sleep(1)
                waited += 1

        return result
    finally:
        try:
            await browser.close()
        except Exception:
            pass
