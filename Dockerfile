FROM python:3.10-slim

WORKDIR /code

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo-dev libpng-dev \
    && rm -rf /var/lib/apt/lists/*

# PyTorch CPU 版 (独立层，利用缓存)
RUN pip install --no-cache-dir \
    torch>=2.0.0 \
    torchvision>=0.15.0 \
    --index-url https://download.pytorch.org/whl/cpu

# 其余依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 代码 + 数据
COPY . .

# 特征库和图片目录 (预构建，提交到仓库或 volume 挂载)
# COPY features.npz .
# COPY product_images/ ./product_images/

# 强制绕过 HF 代理
ENV HF_HUB_DISABLE_PROGRESS_BARS=1
ENV HTTP_PROXY=""
ENV HTTPS_PROXY=""
ENV NO_PROXY="*"

# SearchEasy 配置
ENV FEATURES_NPZ=features.npz
ENV IMAGE_DIR=product_images
ENV TOP_K=5
ENV LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
ENV LLM_MODEL=qwen-plus

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:7860/api/health')" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
