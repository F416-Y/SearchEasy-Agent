# 搜-easy (SearchEasy)

多模态电商智能导购 Agent —— 上传商品图片，获取 AI 驱动的个性化购物推荐。

> [在线体验](https://huggingface.co/spaces/YunYunWaiFu/Flora-ai-shop-agent/docs)

## 项目概述

搜-easy 是一套多模态电商导购系统。用户上传一张商品图片，系统完成：

1. **图像特征提取** → 2. **向量相似检索** → 3. **大模型生成推荐语** → 4. **前端展示结果**

用户可对推荐结果进行"喜欢/不喜欢"反馈，系统据此调整后续推荐方向。

---

## 图像处理与 Agent 后端（本仓库）

核心开发者：Flora (F416-Y)

### 功能模块

| 模块 | 文件 | 说明 |
|------|------|------|
| 图像特征提取 | `extract_features.py` | 基于 ResNet18 提取 512 维特征向量，输出 `.npz` 特征库 |
| t-SNE 可视化 | `visualize_tsne.py` | 将高维特征降维至 2D，按类别着色生成散点图 |
| Agent 调度后端 | `app.py` | FastAPI 服务，串联搜索接口与千问大模型，提供推荐与反馈 API |
| Docker 部署 | `Dockerfile` | 容器化部署至 Hugging Face Spaces |

### 架构说明

```
用户上传图片
     │
     ▼
┌─────────────────────────────┐
│  app.py (FastAPI Agent)     │
│  /api/agent/recommend       │
│  /api/agent/feedback        │
└──────┬──────────┬───────────┘
       │          │
       ▼          ▼
┌──────────┐  ┌──────────────────┐
│ 搜索服务  │  │  千问大模型 (LLM)  │
│ (B 同学 / yinanliu696-blip)   │  │  生成推荐语        │
└────┬─────┘  └──────────────────┘
     │
     ▼
┌──────────────────────┐
│  视觉特征编码进提示词   │
│  (ResNet18 → 前10维)  │
└──────────────────────┘
```

### 多模态融合策略

`extract_image_features()` 将图片经 ResNet18 编码为 512 维特征向量，取前 10 维格式化后注入 LLM 提示词，使大模型在生成推荐语时同时感知图像视觉信息与搜索召回结果，实现文本+视觉的多模态融合推荐。

### 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的 LLM_API_KEY

# 3. 启动服务
uvicorn app:app --host 0.0.0.0 --port 7860

# 4. 特征提取（独立脚本）
python extract_features.py ./product_images -o features.npz

# 5. t-SNE 可视化（独立脚本）
python visualize_tsne.py features.npz -o tsne_output.png
```

### API 接口

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/agent/recommend` | POST | 上传图片，返回相似商品列表 + AI 推荐语 |
| `/api/agent/feedback` | POST | 提交 `like`/`dislike` 反馈，返回调整后的推荐 |

### Docker 部署 (Hugging Face Spaces)

在线地址：[https://huggingface.co/spaces/YunYunWaiFu/Flora-ai-shop-agent/docs](https://huggingface.co/spaces/YunYunWaiFu/Flora-ai-shop-agent/docs)

```bash
docker build -t search-easy-agent .
docker run -p 7860:7860 \
  -e LLM_API_KEY=your_key \
  -e LLM_MODEL=qwen-plus \
  -e LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1 \
  search-easy-agent
```

---

## 队友协作

| 角色 | 负责同学 | 核心职责 | 代码仓库 |
|------|---------|---------|---------|
| 图像处理 & Agent 后端 | Flora (F416-Y) | ResNet18 特征提取、t-SNE 可视化、FastAPI Agent 调度、多模态 LLM 提示词融合、Docker 部署 | 本仓库 |
| 向量检索引擎 | B 同学 (yinanliu696-blip) | 商品图片建库、向量相似度检索（FAISS/Milvus）、搜索 API 服务 | SearchEasy-Search |
| 前端展示 | C 同学 | 用户上传交互、推荐结果展示、反馈 UI、移动端适配 | SearchEasy-Frontend |

---

## 技术栈

- **模型**: ResNet18 (PyTorch), 千问 (Qwen) 系列 via 阿里百炼 DashScope
- **后端**: FastAPI, httpx, Uvicorn
- **特征处理**: NumPy, scikit-learn (t-SNE), Pillow
- **部署**: Docker, Hugging Face Spaces
- **LLM 协议**: OpenAI-compatible API
