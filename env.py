# -*- coding: utf-8 -*-
# ============================================================
# py12306 优化版 · 配置文件（开箱即用 · 面向 Docker 单节点部署）
# ------------------------------------------------------------
# 部署方式：配合仓库根目录 docker-compose.yml 使用（单台主机 Docker
#           Compose 部署，无需外部数据库 / Redis，不依赖任何上游仓库）。
# 使用步骤：
#   1. 按需修改本文件（默认已启用 Web 管理后台，无需 12306 账号即可启动）。
#   2. 在项目根目录执行：docker compose up -d --build
#   3. 浏览器访问 http://<本机IP>:8008 （默认账号 admin / admin123，请尽快修改）。
# 注意：本文件中的 /data/* 路径对应容器内数据卷；若改为本地直接运行，
#       请将路径改为本机可写目录。
# 验证码（自动下单必需）：默认 AUTO_CODE_PLATFORM='free' 指向的免费打码接口
#       已停用，请改为 'user' + API_USER_CODE_QCR_API 指向自有 OCR 服务，
#       或使用 'ruokuai' 若快平台；未配置 OCR 时仅能查询、无法自动下单。
# ============================================================

# 12306 账号（留空则仅查询不下单；如需自动下单请填写账号信息）
USER_ACCOUNTS = [
    # {
    #     'key': 0,
    #     'user_name': 'your_user_name',
    #     'password': 'your_password',
    #     'type': 'qr'  # qr 为扫码登录，填写其他为密码登录
    # },
]

# 查询间隔（秒），默认取间隔/2 到 间隔之间的随机数
QUERY_INTERVAL = 1

# 网络请求重试次数
REQUEST_MAX_RETRY = 5

# 用户心跳检测间隔（秒）
USER_HEARTBEAT_INTERVAL = 120

# 多线程查询（0=关闭，1=开启）
QUERY_JOB_THREAD_ENABLED = 0

# 打码平台（free=免费接口，ruokuai=若快，user=自定义）
AUTO_CODE_PLATFORM = 'free'
API_USER_CODE_QCR_API = ''
AUTO_CODE_ACCOUNT = {
    'user': '',
    'pwd': ''
}

# 语音验证码通知（需阿里云 API 市场 APPCODE）
NOTIFICATION_BY_VOICE_CODE = 0
NOTIFICATION_VOICE_CODE_TYPE = 'dingxin'
NOTIFICATION_API_APP_CODE = ''
NOTIFICATION_VOICE_CODE_PHONE = ''

# 钉钉通知
DINGTALK_ENABLED = 0
DINGTALK_WEBHOOK = ''

# Telegram 推送
TELEGRAM_ENABLED = 0
TELEGRAM_BOT_API_URL = ''

# ServerChan 微信推送
SERVERCHAN_ENABLED = 0
SERVERCHAN_KEY = ''

# PushBear 微信推送
PUSHBEAR_ENABLED = 0
PUSHBEAR_KEY = ''

# Bark iOS 推送
BARK_ENABLED = 0
BARK_PUSH_URL = ''

# 输出日志到文件
OUT_PUT_LOG_TO_FILE_ENABLED = 1
OUT_PUT_LOG_TO_FILE_PATH = '/data/12306.log'

# 运行时数据目录（Docker 数据卷挂载点）
RUNTIME_DIR = '/data/'
QUERY_DATA_DIR = '/data/query/'
USER_DATA_DIR = '/data/user/'
USER_PASSENGERS_FILE = '/data/user/%s_passengers.json'

# 分布式集群配置（默认关闭，无需 Redis）
CLUSTER_ENABLED = 0
NODE_IS_MASTER = 1
NODE_SLAVE_CAN_BE_MASTER = 1
NODE_NAME = 'master'
REDIS_HOST = 'localhost'
REDIS_PORT = '6379'
REDIS_PASSWORD = ''

# 邮箱通知
EMAIL_ENABLED = 0
EMAIL_SENDER = 'sender@example.com'
EMAIL_RECEIVER = 'receiver@example.com'
EMAIL_SERVER_HOST = 'localhost'
EMAIL_SERVER_USER = ''
EMAIL_SERVER_PASSWORD = ''

# Web 管理界面（Docker 部署默认启用）
WEB_ENABLE = 1
WEB_USER = {
    'username': 'admin',
    'password': 'admin123'
}
WEB_PORT = 8008

# CDN 查询加速（默认关闭）
CDN_ENABLED = 0
CDN_CHECK_TIME_OUT = 2

# 浏览器缓存 RAIL ID（默认关闭）
CACHE_RAIL_ID_ENABLED = 0
RAIL_EXPIRATION = ''
RAIL_DEVICEID = ''

# 查询任务（示例，可根据需要修改或通过 Web 界面管理）
QUERY_JOBS = [
    # {
    #     'account_key': 0,
    #     'left_dates': ['2026-10-01'],
    #     'stations': {
    #         'left': '北京',
    #         'arrive': '深圳',
    #     },
    #     'members': ['张三'],
    #     'allow_less_member': 0,
    #     'seats': ['硬卧', '硬座'],
    #     'train_numbers': [],
    #     'except_train_numbers': [],
    #     'period': {
    #         'from': '00:00',
    #         'to': '24:00'
    #     }
    # },
]
