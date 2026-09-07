# 🚂 py12306 购票助手（优化版 / hanyuestar 维护分支）

分布式、多账号、多任务购票助手。本仓库为面向 **Python 3.14** 适配并修复了若干 12306 接口变更的维护分支（基于社区版 py12306 优化而来），内置 Web 管理后台，支持 Docker 一键部署。

> 仓库地址：`https://github.com/hanyuestar/ticket`
> 本地默认分支：`main`

---

## 一、优化版本特性（相比社区原版的关键改动）

本分支在保留原版完整能力的基础上，针对 12306 近期接口变化与运行环境做了以下修复与优化：

| # | 优化点 | 说明 |
|---|--------|------|
| 1 | **Python 3.14 适配** | 代码层面完成 Python 3.14 兼容（本地基于 3.14 验证通过）；Docker 镜像默认 `python:3.11-slim`，向下兼容 3.11+。 |
| 2 | **扫码登录修复** | 重写 `py12306/user/job.py` 登录流程，修复 12306 扫码登录失效问题，适配最新登录接口。 |
| 3 | **车次信息获取修复** | 修复 `query/query.py` 与 `query/job.py` 对车次列表/余票的解析逻辑，适配 12306 接口变更。 |
| 4 | **自动购票完整链路** | 查询 → 验证码打码 → 提交订单 → 确认支付 全链路贯通并验证可用。 |
| 5 | **起始/到达站一致性校验** | 新增 `from/to` 站点码校验（`query/job.py`），避免因同名站点买到错站车票（如误购「广州北→衡阳东」而非「广州→衡阳」）。 |
| 6 | **代码清理** | 移除调试期 `[DEBUG]` 日志与死代码（提交 `24229d5`），提升可读性与运行稳定性。 |
| 7 | **Web 管理后台** | 内置 Flask Web 管理界面：账号扫码登录、任务管理、实时日志、仪表盘，Docker 一键部署。 |

> 其余能力（多账号/多任务/多线程、分布式集群、语音/钉钉/Telegram/ServerChan/Bark/邮件通知、CDN 加速等）与原版一致，详见下方「功能列表」。

---

## 二、功能列表

- [x] 多日期、多站点查询余票
- [x] 自动打码下单（完整抢票链路：查询 → 验票 → 提交订单 → 确认支付）
- [x] 用户状态恢复（Cookie 持久化）
- [x] 电话语音通知
- [x] 多账号、多任务、多线程支持
- [x] 单个任务多站点查询
- [x] 分布式运行（依赖 Redis，可选）
- [x] Docker 支持（docker-compose 一键部署）
- [x] **Web 管理后台**（账号管理、扫码登录、任务管理、实时日志、仪表盘）
- [x] 邮件 / 钉钉 / Telegram / ServerChan / PushBear / Bark 通知
- [ ] 代理池支持

---

## 三、快速开始（Docker 部署，推荐）

### 前置要求
- Docker & Docker Compose
- 无需额外部署数据库（使用本地文件存储）
- 无需 Redis（单机模式默认关闭集群功能）

### 一键部署

```bash
# 1. 进入项目目录
cd yiken123-py12306

# 2. （可选）修改配置文件
# 默认已启用 Web 管理；如需预置 12306 账号与查询任务，编辑 env.py

# 3. 启动（默认拉取已发布镜像，无需本地构建）
docker compose up -d

# 4. 查看日志
docker-compose logs -f
```

启动后访问 **http://localhost:8008** 打开 Web 管理页面。

> 默认登录账号：`admin` / `admin123`（请在 `env.py` 的 `WEB_USER` 中修改，避免弱口令暴露于公网）。

### 镜像地址

`docker-compose.yml` 默认使用已发布的容器镜像，无需本地构建：

| 注册表 | 镜像地址 | 说明 |
|--------|----------|------|
| GitHub Container Registry（默认） | `ghcr.io/hanyuestar/ticket:latest` | compose 默认拉取 |
| Docker Hub | `kyson666/ticket:latest` | 需显式指定 |

```bash
# 默认（ghcr.io）
docker compose up -d

# 切换到 Docker Hub
IMAGE=kyson666/ticket:latest docker compose up -d

# 基于本地源码构建（修改代码后）
docker compose build && docker compose up -d
```

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
docker-compose up -d          # 启动
docker-compose down           # 停止
docker-compose restart        # 重启（修改配置后生效）
docker-compose logs -f        # 实时日志
```

---

## 四、本地运行

支持 **Python 3.11 及以上**（本分支已在 Python 3.14 下验证）。

**1. 安装依赖**
```bash
pip install -r requirements.txt
```

**2. 配置程序**
```bash
# 项目已自带 env.py（已纳入版本控制），直接修改即可
```

**3. 启动前测试（校验配置与账号）**
```bash
python main.py -t
```

**4. 运行程序**
```bash
python main.py
```

### 命令行参数
- `-t` 测试配置信息
- `-t -n` 测试配置信息以及通知消息
- `-c <path>` 指定自定义配置文件位置

---

## 五、配置说明

所有配置集中在 `env.py`。常用配置项如下（完整字段见 `env.py`）：

### Web 管理
```python
WEB_ENABLE = 1
WEB_USER = {
    'username': 'admin',
    'password': 'admin123'   # 请务必修改为强口令
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
        'type': 'qr'  # qr 扫码登录；其他为密码登录
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
        'allow_less_member': 0,
        'seats': ['硬卧', '硬座'],
        'train_numbers': [],
        'except_train_numbers': [],
        'period': {'from': '00:00', 'to': '24:00'}
    },
]
```

### 打码平台
```python
AUTO_CODE_PLATFORM = 'free'   # free=免费接口，ruokuai=若快，user=自定义
```
- 免费接口默认可用；若使用若快，填写 `AUTO_CODE_ACCOUNT`。
- 自定义打码：`API_USER_CODE_QCR_API` 指向自有 OCR 服务。

### 通知方式
支持：语音电话、钉钉、Telegram、ServerChan、PushBear、Bark、邮件。在 `env.py` 中对应配置项开启即可。

### 分布式集群（可选）
集群依赖 Redis。将 `CLUSTER_ENABLED` 设为 `1` 并配置 Redis 连接即可开启（支持主节点自动切换、配置同步）。

---

## 六、Web 管理后台

启动后访问 `http://<主机IP>:8008`，默认账号 `admin` / `admin123`。

### 功能模块
**📊 仪表盘**
- 账号数、已登录数、任务数、运行中任务、累计查询次数
- 系统运行状态（Web / 集群 / CDN / 日志）

**👤 账号管理（核心）**
- 添加 12306 账号：支持扫码登录（推荐）与密码登录
- 扫码登录：点击「扫码登录」显示二维码，用 12306 App 扫描完成登录，无需在配置中填写密码
- 多账号切换：不同抢票任务可指定不同账号
- 乘客列表、删除账号；变更自动保存，容器重启后自动恢复

**🎫 抢票任务管理**
- 新建任务：选择账号、出发日期、出发/到达站（支持搜索自动补全）、乘客、座位、指定车次、时间范围
- 任务列表：查看状态（运行中 / 待启动）
- 删除任务；任务创建后立即开始运行，自动查询并在有票时提交订单

**📋 实时日志**
- 实时查看运行日志，支持自动滚动、手动刷新

### 抢票完整流程
1. 在「账号管理」添加 12306 账号并完成扫码登录
2. 在「抢票任务」新建任务，选择账号、填写行程与乘客
3. 系统循环查询余票，发现符合条件的车票后自动提交订单
4. 下单成功后于 12306 App 完成支付
5. 支持多账号同时运行，不同任务可使用不同账号

### 动态配置持久化
Web 后台添加的账号与任务保存在 `/data/config.json`（Docker 数据卷持久化），容器重启后自动加载，无需修改 `env.py`。

---

## 七、关于数据库与依赖

本项目**不需要**额外部署数据库：
- 车站代码：`data/stations.txt`（已内置）
- CDN 列表：`data/cdn.txt`（已内置）
- 乘客信息：运行时自动生成 JSON
- 查询缓存：运行时自动生成
- 日志：文本文件

Redis 仅在分布式集群模式下需要，单机部署默认关闭（`CLUSTER_ENABLED = 0`）。

滑块验证依赖 `pyppeteer` 内置 Chromium（Docker 镜像已预下载；本地首次运行会自动下载）。

---

## 八、常见问题（FAQ）

**Q1：扫码登录一直失败 / 二维码不显示？**
A：确认 `WEB_ENABLE=1` 且端口已映射；若使用 Docker，确保 `8008` 端口未被占用且可从宿主机访问。本版本已修复扫码登录流程，若仍失败多为 12306 临时风控，可重试或改用密码登录。

**Q2：能查到票但不下单？**
A：检查 `USER_ACCOUNTS` 是否已配置且登录成功（Web 后台「账号管理」查看登录状态）；`QUERY_JOBS` 中 `account_key` 需对应已登录账号。仅配置任务而未配置账号时，程序只查询不下单。

**Q3：买到错误的车站（如广州北而非广州）？**
A：本版本已加入起始/到达站码一致性校验，正常情况下不会再出现该问题。如仍遇到，请提交 Issue 并附日志。

**Q4：本地运行报缺少 `pyppeteer` 或 Chromium 相关错误？**
A：执行 `pip install -r requirements.txt` 安装依赖；首次运行 `pyppeteer` 需下载 Chromium，请保证网络连通（或直接使用 Docker 镜像，已预置）。

**Q5：Docker 启动后 Web 打不开？**
A：检查 `docker-compose ps` 状态与日志 `docker-compose logs -f`；确认防火墙/安全组放行 `8008`；确认 `WEB_ENABLE=1`。

**Q6：如何修改默认管理员口令？**
A：编辑 `env.py` 中 `WEB_USER['password']`，或（若已用 Web 后台）在对应管理入口修改；修改后 `docker-compose restart` 生效。

---

## 九、关于防封

查询与登录操作是分开的，查询不依赖用户是否登录。建议在家庭宽带等非云服务器环境下运行，降低账号风控风险。

---

## 十、更新日志

### v1.0.0（2026-09-07 发布）

首个独立维护版本，可脱离上游仓库独立部署运行。

**新特性与修复**
- 适配 Python 3.14（兼容 3.11+，Docker 镜像默认 3.11）
- 修复 12306 扫码登录失效问题
- 修复车次信息获取（适配 12306 接口变更）
- 自动购票完整链路贯通（查询 → 打码 → 提交订单 → 确认支付）
- 新增起始/到达站一致性校验，避免买到同名错站车票（如「广州北」≠「广州」）
- 内置 Web 管理后台（扫码登录 / 任务管理 / 实时日志 / 仪表盘）
- 开箱即用：`docker compose up -d` 一键部署，双注册表镜像同步发布

**开发节点**

| 日期 | 内容 |
|------|------|
| 2026-07-20 | 修复 12306 扫码登录、获取车次信息 |
| 2026-07-25 | 自动购票功能实现 |
| 2026-08-27 | 修复购票起始站和查询站不一致问题 |
| 2026-09-07 | 移除调试日志与死代码；提供开箱即用 Docker 部署；发布 v1.0.0 |

### v1.0.2（2026-09-07 发布）

- **修复余票查询 302 风控拦截**：新增「无头浏览器会话预热」机制——启动时及被拦截自愈时，用无头浏览器（pyppeteer）打开 12306 查询页，由 12306 自家反爬 JS 完成会话 Cookie 种植（`JSESSIONID` / `_uab_collina` / `BIGipServerotn` / `SF_cookie_2` 等），再将整套 Cookie + UA 导入查询会话，查询恢复 200。实测确认 302 的根因是缺少浏览器侧会话 Cookie，而非设备指纹缺失
- **302 风控自愈**：查询遇到 302（跳 error.html）时自动触发自愈——重新预热浏览器会话 + 刷新设备指纹 + 刷新查询接口地址，带 60 秒冷却与线程锁，防止并发刷新风暴
- **设备指纹获取重构**（`py12306/helpers/device_id.py`，新增）：浏览器候选改为系统 Chrome/Edge 优先、pyppeteer 自带 Chromium 兜底（仅在其二进制已存在时启用，避免触发联网下载卡死）；启动参数加入 `--disable-blink-features=AutomationControlled` 移除自动化标志；进程级熔断避免反复白等
- **明确风控日志**：302 拦截时输出清晰指引日志（原因、自愈动作、手动兜底方案）
- Docker 镜像已预装 pyppeteer Chromium 与运行依赖，上述功能开箱即用

### v1.0.1（2026-09-07 发布）

- **修复 Web 管理后台登录 404**（登录接口 `/login` 与前端调用路径 `/user/login` 不一致，v1.0.0 及之前版本登录必定失败）
- Docker Compose 改为接入 Docker 内置默认 bridge 网络（`network_mode: bridge`），不再创建项目网络，规避群晖等环境「could not find an available, non-overlapping IPv4 address pool」报错
- v1.0.0 标签因上述登录缺陷已废弃删除，请直接使用 **v1.0.1** 及以上版本

### 社区原版历史
- 支持分布式集群 / 配置文件动态修改 / 免费打码 / Web 页面 / 钉钉·Telegram·微信推送 / CDN 查询

---

## 十一、致谢

- 感谢 [testerSunshine](https://github.com/testerSunshine/12306)，借鉴了部分实现
- 感谢所有提供 PR 的贡献者
- 感谢 [zhaipro](https://github.com/zhaipro/easy12306) 的验证码本地识别模型与算法
- 本分支基于 [yiken123/py12306](https://github.com/yiken123/py12306) 优化而来

## License
[Apache License.](./LICENSE)
