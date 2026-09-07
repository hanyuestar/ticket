# 🚂 py12306 购票助手
分布式，多账号，多任务购票

## Features
- [x] 多日期查询余票
- [x] 自动打码下单（完整抢票链路：查询→验票→提交订单→确认支付）
- [x] 用户状态恢复（Cookie 持久化）
- [x] 电话语音通知
- [x] 多账号、多任务、多线程支持
- [x] 单个任务多站点查询
- [x] 分布式运行
- [x] Docker 支持（docker-compose 一键部署）
- [x] Web 管理后台（账号管理、扫码登录、任务管理、实时日志、仪表盘）
- [x] 邮件通知
- [x] 微信消息通知
- [ ] 代理池支持

## 快速开始（Docker 部署，推荐）

### 前置要求
- Docker & Docker Compose
- 无需额外部署数据库（项目使用本地文件存储）
- 无需 Redis（单机模式默认关闭集群功能）

### 一键部署

```bash
# 1. 克隆或进入项目目录
cd yiken123-py12306

# 2. 修改配置文件（可选，默认已启用 Web 管理）
# 编辑 env.py，设置 12306 账号、查询任务、通知方式等
# vim env.py

# 3. 构建并启动
docker-compose up -d --build

# 4. 查看日志
docker-compose logs -f
```

启动后访问 **http://localhost:8008** 即可打开 Web 管理页面。

默认登录账号：`admin` / `admin123`（可在 `env.py` 的 `WEB_USER` 中修改）

### 数据持久化
- 静态配置：`./env.py`（挂载到容器 `/config/env.py`，只读）
- 运行数据：Docker 命名卷 `py12306_data`（挂载到 `/data`）
  - 动态配置：`/data/config.json`（Web 后台添加的账号和任务）
  - 日志文件：`/data/12306.log`
  - 乘客信息：`/data/user/*_passengers.json`
  - 登录 Cookie：`/data/user/*.cookie`
  - 登录二维码：`/data/user/qrcode/*.png`
  - 查询缓存：`/data/query/`

### 常用命令

```bash
# 启动
docker-compose up -d

# 停止
docker-compose down

# 重启
docker-compose restart

# 查看实时日志
docker-compose logs -f

# 修改配置后重启生效
docker-compose restart
```

## 本地运行

py12306 需要运行在 Python 3.11 以上版本。

**1. 安装依赖**
```bash
pip install -r requirements.txt
```

**2. 配置程序**
```bash
# 复制配置文件（项目已自带 env.py，可直接修改）
cp env.py.example env.py  # 如需要模板
```

**3. 启动前测试**
```bash
python main.py -t
```

**4. 运行程序**
```bash
python main.py
```

### 参数列表
- `-t` 测试配置信息
- `-t -n` 测试配置信息以及通知消息
- `-c` 指定自定义配置文件位置

## 配置说明

### Web 管理
```python
WEB_ENABLE = 1
WEB_USER = {
    'username': 'admin',
    'password': 'admin123'
}
WEB_PORT = 8008
```

### 12306 账号
```python
USER_ACCOUNTS = [
    {
        'key': 0,
        'user_name': 'your_user_name',
        'password': 'your_password',
        'type': 'qr'  # qr 扫码登录，其他为密码登录
    },
]
```
留空则仅查询余票，不自动下单。

### 查询任务
```python
QUERY_JOBS = [
    {
        'account_key': 0,
        'left_dates': ['2026-10-01'],
        'stations': {'left': '北京', 'arrive': '深圳'},
        'members': ['张三'],
        'seats': ['硬卧', '硬座'],
        'train_numbers': [],
    },
]
```

### 通知方式
支持：语音电话、钉钉、Telegram、ServerChan、PushBear、Bark、邮件。在 `env.py` 中对应配置项开启即可。

## 关于数据库

本项目**不需要**额外部署数据库：
- 车站代码：`data/stations.txt`（已内置）
- CDN 列表：`data/cdn.txt`（已内置）
- 乘客信息：运行时自动生成 JSON 文件
- 查询缓存：运行时自动生成
- 日志：文本文件

Redis 仅在分布式集群模式下需要，单机部署默认关闭（`CLUSTER_ENABLED = 0`）。

## Web 管理后台

启动后访问 `http://主机IP:8008`，默认账号 `admin` / `admin123`。

### 功能模块

**📊 仪表盘**
- 账号数、已登录数、任务数、运行中任务、累计查询次数
- 系统运行状态（Web/集群/CDN/日志）

**👤 账号管理（核心功能）**
- **添加 12306 账号**：支持扫码登录（推荐）和密码登录两种方式
- **扫码登录**：点击"扫码登录"按钮，页面显示二维码，用 12306 APP 扫描即可完成登录，无需在配置文件中填写密码
- **切换账号**：可添加多个 12306 账号，每个抢票任务可指定使用不同账号
- **乘客列表**：查看已登录账号的常用联系人
- **删除账号**：移除不需要的账号
- 所有账号变更自动保存，容器重启后自动恢复

**🎫 抢票任务管理**
- **新建任务**：选择已登录账号、填写出发日期、出发站/到达站（支持搜索自动补全）、乘客、座位类型、指定车次、时间范围
- **任务列表**：查看所有任务状态（运行中/待启动）
- **删除任务**：移除不需要的抢票任务
- 任务创建后立即开始运行，自动查询余票并在有票时自动提交订单

**📋 实时日志**
- 实时查看程序运行日志
- 支持自动滚动、手动刷新

### 抢票完整流程

1. 在"账号管理"中添加 12306 账号并完成扫码登录
2. 在"抢票任务"中新建任务，选择账号、填写行程和乘客
3. 系统自动循环查询余票，发现符合条件的车票后自动提交订单
4. 下单成功后可在 12306 APP 中完成支付
5. 支持多账号同时运行，不同任务可使用不同账号

### 动态配置持久化

通过 Web 后台添加的账号和任务保存在 `/data/config.json` 中（Docker 数据卷持久化），容器重启后自动加载，无需修改 `env.py` 配置文件。

## 分布式集群

集群依赖 Redis，支持主节点自动切换、配置同步等。将 `CLUSTER_ENABLED` 设为 `1` 并配置 Redis 连接即可开启。

## 更新日志
- 19-01-10 支持分布式集群
- 19-01-11 配置文件支持动态修改
- 19-01-12 新增免费打码
- 19-01-14 新增 Web 页面支持
- 19-01-15 新增钉钉/Telegram/微信推送
- 19-01-18 新增 CDN 查询

## 关于防封
查询和登录操作是分开的，查询不依赖用户是否登录。建议在家庭宽带等非云服务器环境下运行。

## Thanks
- 感谢 [testerSunshine](https://github.com/testerSunshine/12306)，借鉴了部分实现
- 感谢所有提供 PR 的贡献者
- 感谢 [zhaipro](https://github.com/zhaipro/easy12306) 的验证码本地识别模型与算法

## License
[Apache License.](https://github.com/pjialin/py12306/blob/master/LICENSE)
