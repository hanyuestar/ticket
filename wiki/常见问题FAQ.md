# 常见问题 FAQ

**Q1：扫码登录一直失败 / 二维码不显示？**
A：确认 `WEB_ENABLE=1` 且端口已映射；Docker 确保 `8008` 可从宿主机访问。本版本已修复扫码登录流程，若仍失败多为 12306 临时风控，可重试或改用密码登录。

**Q2：能查到票但不下单？**
A：检查 `USER_ACCOUNTS` 是否已配置且登录成功（Web 后台「账号管理」查看状态）；`QUERY_JOBS` 的 `account_key` 需对应已登录账号。仅配置任务未配置账号时，程序只查询不下单。

**Q3：买到错误的车站（如广州北而非广州）？**
A：本版本已加入起始/到达站码一致性校验，正常情况下不再出现该问题。如仍遇到，请提交 Issue 并附日志。

**Q4：本地运行报缺少 `pyppeteer` 或 Chromium 相关错误？**
A：执行 `pip install -r requirements.txt`；首次运行 `pyppeteer` 会下载 Chromium，请保证网络连通，或直接使用已预置浏览器的 Docker 镜像。

**Q5：Docker 启动后 Web 打不开？**
A：用 `docker-compose ps` 与 `docker-compose logs -f` 排查；确认防火墙/安全组放行 `8008`；确认 `WEB_ENABLE=1`。

**Q6：如何修改默认管理员口令？**
A：编辑 `env.py` 的 `WEB_USER['password']`（或 Web 后台对应入口修改），`docker-compose restart` 生效。**默认 `admin123` 为弱口令，公网部署务必修改。**

**Q7：支持哪些通知方式？**
A：语音电话、钉钉、Telegram、ServerChan、PushBear、Bark、邮件，在 `env.py` 对应配置项开启。

**Q8：需要数据库或 Redis 吗？**
A：单机运行不需要数据库，也不需要 Redis。仅启用分布式集群（`CLUSTER_ENABLED=1`）时才需要 Redis。

**Q9：查询与登录是否绑定？**
A：查询和登录是分开的，查询不依赖用户是否登录。建议在家庭宽带等非云服务器环境运行以降低风控风险。

**Q10：本分支基于哪个版本？Python 版本要求？**
A：基于社区版 py12306 优化，针对 Python 3.14 适配（本地 3.14 验证；Docker 镜像 3.11-slim，兼容 3.11+）。
