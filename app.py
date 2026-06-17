"""
SearchEasy — 多模态 AI 导购系统 (全链路独立版)
拍照即搜：ResNet18 特征提取 → 余弦检索 → LLM 推荐
"""
import os
import tempfile
from functools import lru_cache
from pathlib import Path

import httpx
import numpy as np
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from search_engine import engine as search_engine

# ═══════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════
FEATURES_NPZ = os.getenv("FEATURES_NPZ", "features.npz")
IMAGE_DIR = os.getenv("IMAGE_DIR", "product_images")
TOP_K = int(os.getenv("TOP_K", "5"))
MIN_SIMILARITY = float(os.getenv("MIN_SIMILARITY", "0.0"))

# LLM 配置
DEFAULT_LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
DEFAULT_LLM_MODEL = "qwen-plus"
LLM_TIMEOUT = 30.0
LLM_MAX_RETRIES = 1


def get_llm_config() -> dict:
    """获取并校验 LLM 配置。"""
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        raise RuntimeError(
            "缺少 LLM_API_KEY 环境变量！\n"
            "请设置: export LLM_API_KEY=your-dashscope-api-key\n"
            "或复制 .env.example 为 .env 并填入密钥。"
        )
    return {
        "api_key": api_key,
        "base_url": os.getenv("LLM_BASE_URL", DEFAULT_LLM_BASE_URL).rstrip("/"),
        "model": os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL),
    }


# ═══════════════════════════════════════════════════════════════
# FastAPI 初始化
# ═══════════════════════════════════════════════════════════════
app = FastAPI(
    title="SearchEasy Agent",
    description="多模态 AI 导购系统 — 拍照即搜，智能推荐",
    version="2.0.0",
)


@app.on_event("startup")
def startup():
    """启动时加载特征库 + 挂载图片静态目录"""
    # 加载特征库
    npz_path = Path(FEATURES_NPZ)
    if npz_path.exists():
        search_engine.load(str(npz_path), image_base_dir=IMAGE_DIR)
        print(f"[SearchEasy] 特征库已加载: {search_engine.size} 张图片, "
              f"维度={search_engine.stats()['feature_dim']}")
    else:
        print(f"[SearchEasy] ⚠ 特征库未找到: {npz_path.absolute()}")
        print(f"  请先运行: python extract_features.py {IMAGE_DIR} -o {FEATURES_NPZ}")

    # 挂载图片目录
    img_dir = Path(IMAGE_DIR)
    if img_dir.is_dir():
        app.mount("/images", StaticFiles(directory=str(img_dir)), name="images")
        print(f"[SearchEasy] 图片目录已挂载: /images → {img_dir.absolute()}")
    else:
        print(f"[SearchEasy] ⚠ 图片目录不存在: {img_dir.absolute()}")


@app.get("/api/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "version": app.version,
        "engine": {
            "loaded": search_engine.is_loaded,
            **search_engine.stats(),
        },
    }


# ═══════════════════════════════════════════════════════════════
# ResNet18 特征提取
# ═══════════════════════════════════════════════════════════════

@lru_cache(maxsize=1)
def get_feature_extractor():
    """惰性加载 ResNet18 (去分类头，输出512维)"""
    import torch
    import torchvision.models as models

    model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
    model = torch.nn.Sequential(*list(model.children())[:-1])
    model.eval()
    return model


def extract_features(image_path: str) -> np.ndarray:
    """提取图像的 512 维特征向量"""
    import torch
    import torchvision.transforms as transforms
    from PIL import Image

    model = get_feature_extractor()
    transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])

    img = Image.open(image_path).convert("RGB")
    img_tensor = transform(img).unsqueeze(0)

    with torch.no_grad():
        features = model(img_tensor).squeeze()

    return features.numpy()


def describe_features(vec: np.ndarray) -> str:
    """将 512 维特征编码为 LLM 可读的文本描述"""
    v = vec.flatten().tolist()
    n = len(v)
    sorted_v = sorted(v)
    mean_val = sum(v) / n
    std_val = (sum((x - mean_val) ** 2 for x in v) / n) ** 0.5

    # 最强激活通道
    indexed = sorted(enumerate(v), key=lambda x: abs(x[1]), reverse=True)
    top8 = indexed[:8]

    lines = [
        f"📊 ResNet18 512维特征摘要",
        f"- 分布: 均值={mean_val:.4f}  标准差={std_val:.4f}  范围=[{sorted_v[0]:.4f}, {sorted_v[-1]:.4f}]",
        f"- 分位数: P10={sorted_v[int(n*0.10)]:.4f}  P50={sorted_v[int(n*0.50)]:.4f}  P90={sorted_v[int(n*0.90)]:.4f}",
        f"- 首部通道: [{', '.join(f'{v[i]:.4f}' for i in range(5))}]",
        f"- 尾部通道: [{', '.join(f'{v[i]:.4f}' for i in range(n-5, n))}]",
        f"- 最强激活: {', '.join(f'ch{ch}={val:+.4f}' for ch, val in top8)}",
    ]
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════
# LLM 调用
# ═══════════════════════════════════════════════════════════════

async def call_llm(prompt: str) -> str:
    """调用 LLM，含重试和友好报错"""
    cfg = get_llm_config()
    last_error = None

    for attempt in range(LLM_MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=LLM_TIMEOUT) as client:
                resp = await client.post(
                    url=f"{cfg['base_url']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {cfg['api_key']}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": cfg["model"],
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.7,
                        "max_tokens": 300,
                    },
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]

        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code == 401:
                raise HTTPException(
                    status_code=500,
                    detail="LLM API Key 无效 (401)，请检查 LLM_API_KEY 是否正确",
                )
            if attempt < LLM_MAX_RETRIES:
                continue
        except httpx.TimeoutException:
            last_error = Exception("LLM 请求超时")
        except Exception as e:
            last_error = e

    raise HTTPException(
        status_code=500,
        detail=f"LLM 调用失败（已重试 {LLM_MAX_RETRIES} 次）: {last_error}",
    )


# ═══════════════════════════════════════════════════════════════
# API 端点
# ═══════════════════════════════════════════════════════════════

@app.post("/api/search")
async def search_image(file: UploadFile = File(...)):
    """纯图像检索：上传图片 → 余弦相似度搜索 → 返回 top-k 相似商品"""
    if not search_engine.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="特征库未加载，请先准备 features.npz。运行: python extract_features.py <图片目录> -o features.npz",
        )

    # 保存上传图片
    contents = await file.read()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    try:
        tmp.write(contents)
        tmp.close()
        image_path = tmp.name
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        raise HTTPException(status_code=500, detail="无法保存上传的图片")

    try:
        # 提取特征 → 检索
        query_vec = extract_features(image_path)
        results = search_engine.search(query_vec, top_k=TOP_K, min_score=MIN_SIMILARITY)

        # 拼接图片 URL
        base_url = os.getenv("IMAGE_BASE_URL", "").rstrip("/")
        for r in results:
            r["image_url"] = search_engine.get_image_url(r["image_path"], base_url)

        return {
            "query": file.filename,
            "total_indexed": search_engine.size,
            "results_count": len(results),
            "results": results,
        }
    finally:
        if os.path.exists(image_path):
            os.unlink(image_path)


@app.post("/api/agent/recommend")
async def recommend(file: UploadFile = File(...)):
    """全链路推荐：上传图片 → 图像检索 + LLM 生成推荐语"""
    if file.filename == "":
        raise HTTPException(status_code=400, detail="请上传一张图片文件")

    if not search_engine.is_loaded:
        raise HTTPException(
            status_code=503,
            detail="特征库未加载，请先准备 features.npz",
        )

    contents = await file.read()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    try:
        tmp.write(contents)
        tmp.close()
        image_path = tmp.name
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        raise HTTPException(status_code=500, detail="无法保存上传的图片")

    try:
        # 1. 提取特征
        query_vec = extract_features(image_path)

        # 2. 余弦检索
        results = search_engine.search(query_vec, top_k=TOP_K, min_score=MIN_SIMILARITY)
        if not results:
            return {
                "products": [],
                "recommendation_note": "抱歉，没有找到相似的商品。试试换个角度拍照？📸",
            }

        # 3. 拼接图片 URL
        image_base_url = os.getenv("IMAGE_BASE_URL", "").rstrip("/")
        for r in results:
            r["image_url"] = search_engine.get_image_url(r["image_path"], image_base_url)

        # 4. 构建 Prompt
        products_text = "\n".join(
            f"- 商品: {r['image_path']}, 相似度: {r['score']:.2%}"
            for r in results
        )

        visual_desc = describe_features(query_vec)

        prompt = (
            "你是一个专业的时尚购物助手。用户上传了一张商品图片。\n\n"
            f"{visual_desc}\n\n"
            "以下是检索到的相似商品列表：\n"
            f"{products_text}\n\n"
            "请根据视觉特征和检索结果，帮用户做简短的分析推荐。"
            "用亲切、口语化的语气，像朋友推荐东西一样自然。说人话，控制在 150 字以内。"
        )

        recommendation_note = await call_llm(prompt)

        return {
            "products": [
                {
                    "image_path": r["image_path"],
                    "image_url": r.get("image_url", ""),
                    "similarity_score": r["score"],
                }
                for r in results
            ],
            "recommendation_note": recommendation_note,
        }
    finally:
        if os.path.exists(image_path):
            os.unlink(image_path)


# ═══════════════════════════════════════════════════════════════
# 反馈端点
# ═══════════════════════════════════════════════════════════════

class FeedbackRequest(BaseModel):
    feedback: str
    last_products: list


@app.post("/api/agent/feedback")
async def feedback(req: FeedbackRequest):
    """用户反馈：like 继续推荐同风格 / dislike 换风格"""
    if req.feedback not in ("like", "dislike"):
        raise HTTPException(status_code=400, detail="feedback 必须为 like 或 dislike")
    if not req.last_products:
        raise HTTPException(status_code=400, detail="last_products 不能为空")

    products_text = "\n".join(
        f"- 商品: {r.get('image_path', '')}, 相似度: {r.get('similarity_score', r.get('score', 0)):.2%}"
        for r in req.last_products
    )

    if req.feedback == "like":
        prompt = (
            "你是一个友好的购物助手。用户对你刚才的推荐很满意！\n"
            f"以下是之前推荐的相似商品列表：\n\n{products_text}\n\n"
            "请基于这些商品，继续推荐更多风格相似的商品。"
            "用亲切、口语化的语气，像朋友推荐东西一样自然。说人话，控制在 150 字以内。"
        )
    else:
        prompt = (
            "你是一个友好的购物助手。用户对你刚才的推荐不太满意，希望换一种风格。\n"
            f"以下是之前推荐的相似商品列表：\n\n{products_text}\n\n"
            "请换个完全不同的风格重新推荐，给用户一些新的选择方向。"
            "用亲切、口语化的语气，像朋友推荐东西一样自然。说人话，控制在 150 字以内。"
        )

    recommendation_note = await call_llm(prompt)

    return {
        "products": [
            {
                "image_path": r.get("image_path", r.get("path", "")),
                "similarity_score": r.get("similarity_score", r.get("score", 0)),
            }
            for r in req.last_products
        ],
        "recommendation_note": recommendation_note,
    }
