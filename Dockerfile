FROM python:3.11-slim

LABEL maintainer="py12306"
ENV TZ=Asia/Shanghai \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# 设置时区
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# 安装 Chromium 运行依赖（pyppeteer 滑块验证需要）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# 先安装依赖（利用 Docker 缓存）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 预下载 pyppeteer Chromium 浏览器（避免首次运行时下载）
RUN python -c "import pyppeteer; pyppeteer.chromium_downloader.download_chromium()" 2>/dev/null || \
    python -c "from pyppeteer.command import install; install()" 2>/dev/null || true

# 创建数据和配置目录
RUN mkdir -p /data/query /data/user /config

# 复制项目文件
COPY . .

# 默认配置文件（可通过 docker-compose 卷挂载覆盖）
RUN cp env.py /config/env.py

VOLUME ["/data"]

EXPOSE 8008

CMD ["python", "main.py", "-c", "/config/env.py"]
