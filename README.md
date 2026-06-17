# SearchEasy — 多模态 AI 导购系统

> 📸 拍照即搜 · AI 智能推荐 · 全链路独立

[🛍️ 在线体验](https://yunyunwaifu-flora-ai-shop-agent.hf.space/docs)

---

## 项目概述

独立全栈实现的「拍照即搜」多模态电商导购系统。用户上传商品照片，系统完成：

```
拍照上传 → ResNet18 特征提取 → 余弦相似度检索 → LLM 生成推荐语 → 前端展示
```

**全链路闭环，无外部服务依赖。**

---

## 项目结构

```
字跳AI/
├── app.py                         ← FastAPI 推理服务 (核心)
├── search_engine.py               ← 余弦相似度检索引擎
├── extract_features.py            ← 工具: ResNet18 批量特征提取
├── visualize_tsne.py              ← 工具: t-SNE 降维可视化
├── Dockerfile                     ← 容器化部署
├── requirements.txt               ← Python 依赖
├── .env.example                   ← 环境变量模板
├── .gitignore
├── features.npz                   ← 预提取的特征库 (需构建)
├── product_images/                ← 商品图片目录 (需准备)
│   ├── category_a/
│   ├── category_b/
│   └── ...
├── SearchEasy-Frontend/           ← Streamlit 前端子项目
│   ├── app.py / requirements.txt / README.md
└── docs/chat-logs/                ← 开发聊天记录
```

---

## 技术架构

| 模块 | 技术 | 说明 |
|------|------|------|
| **特征提取** | ResNet18 (PyTorch) | 512 维特征向量，@lru_cache 优化加载 |
| **向量检索** | 自建 SearchEngine | 余弦相似度 + L2 归一化，argpartition 快速 top-k |
| **多模态融合** | Prompt Engineering | 视觉特征摘要注入 LLM，实现 RAG 闭环 |
| **LLM 推理** | 千问 (Qwen) via 阿里百炼 | OpenAI 兼容 API，重试 + 401 友好报错 |
| **推理服务** | FastAPI + Uvicorn | 异步非阻塞，/images 静态文件挂载 |
| **可视化验证** | scikit-learn t-SNE | 降维验证 CNN 语义聚类效应 |
| **部署** | Docker + HF Spaces | CPU 镜像，HEALTHCHECK，代理绕过 |

---

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 准备数据 & 构建特征库

```bash
# 将商品图片按类别放入 product_images/
# 示例结构:
#   product_images/服装/001.jpg
#   product_images/服装/002.jpg
#   product_images/数码/001.jpg

# 提取特征
python extract_features.py product_images -o features.npz
```

### 3. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，至少填入 LLM_API_KEY
```

### 4. 启动服务

```bash
uvicorn app:app --host 0.0.0.0 --port 7860 --reload
```

### 5. 验证

```bash
# 健康检查
curl http://localhost:7860/api/health

# 交互文档
open http://localhost:7860/docs

# 搜索测试
curl -X POST http://localhost:7860/api/search \
  -F "file=@your_test_image.jpg"
```

---

## API 接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 + 特征库统计 |
| `/api/search` | POST | 纯图像检索 (不调用 LLM) |
| `/api/agent/recommend` | POST | 全链路推荐 (检索 + LLM) |
| `/api/agent/feedback` | POST | 反馈驱动推荐 (like/dislike) |
| `/images/{path}` | GET | 商品图片访问 |
| `/docs` | GET | Swagger UI |

### `/api/search` 响应示例

```json
{
  "query": "test.jpg",
  "total_indexed": 200,
  "results_count": 5,
  "results": [
    {
      "image_path": "服装/001.jpg",
      "image_url": "/images/服装/001.jpg",
      "score": 0.9532
    }
  ]
}
```

### `/api/agent/recommend` 响应示例

```json
{
  "products": [
    {
      "image_path": "服装/001.jpg",
      "image_url": "http://localhost:7860/images/服装/001.jpg",
      "similarity_score": 0.9532
    }
  ],
  "recommendation_note": "嘿，这件上衣的纹理跟..."
}
```

---

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `LLM_API_KEY` | ✅ | — | 阿里百炼 API Key |
| `LLM_MODEL` | 否 | `qwen-plus` | 模型选择 |
| `LLM_BASE_URL` | 否 | 国内主域名 | API 地址 |
| `FEATURES_NPZ` | 否 | `features.npz` | 特征库路径 |
| `IMAGE_DIR` | 否 | `product_images` | 图片目录 |
| `TOP_K` | 否 | `5` | 返回结果数 |
| `MIN_SIMILARITY` | 否 | `0.0` | 最低相似度 |
| `IMAGE_BASE_URL` | 否 | — | 图片 URL 前缀 |

---

## Docker 部署

```bash
# 1. 先在本地构建特征库
python extract_features.py product_images -o features.npz

# 2. 构建镜像 (需取消 Dockerfile 中 COPY features.npz 和 product_images 的注释)
docker build -t search-easy .

# 3. 运行
docker run -p 7860:7860 \
  -e LLM_API_KEY=your_key \
  search-easy
```

在线地址：[https://yunyunwaifu-flora-ai-shop-agent.hf.space/docs](https://yunyunwaifu-flora-ai-shop-agent.hf.space/docs)

---

## 命令行工具

```bash
# 批量特征提取
python extract_features.py product_images -o features.npz --device cpu

# t-SNE 可视化 (验证特征语义聚类)
python visualize_tsne.py features.npz -o tsne_output.png --perplexity 30
```

---

## 技术亮点

- **独立全栈**：从图像输入到推荐输出，不依赖第三方搜索服务
- **RAG 闭环**：检索召回 + 视觉特征共同注入 LLM Prompt
- **快速检索**：L2 归一化 + `argpartition` 实现 O(n) top-k
- **生产就绪**：HEALTHCHECK、分级错误处理、LLM 重试机制
- **可视化验证**：t-SNE 降维验证 ResNet18 特征空间的类别聚类
