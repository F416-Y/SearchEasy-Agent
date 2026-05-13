import os
import tempfile
from functools import lru_cache

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile

# 阿里百炼 (DashScope) 环境变量配置
#   LLM_API_KEY    — API Key，从阿里云百炼控制台获取
#   LLM_BASE_URL   — https://dashscope.aliyuncs.com/compatible-mode/v1
#   LLM_MODEL      — 可选 qwen-turbo / qwen-plus / qwen-max / qwen3-235b-a22b

app = FastAPI()

SEARCH_URL = "https://whisper1234-ai-shop-agent-api.hf.space/search"


@lru_cache(maxsize=1)
def get_feature_extractor():
    """加载 ResNet18 并去掉分类头，返回 512 维特征提取器。（惰性导入 torch）"""
    import torch
    import torchvision.models as models

    model = models.resnet18(pretrained=True)
    model = torch.nn.Sequential(*list(model.children())[:-1])
    model.eval()
    return model


def extract_image_features(image_path: str) -> str:
    """提取图片前 10 维特征，格式化为字符串。（惰性导入依赖库）"""
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

    first_10 = features[:10].tolist()
    formatted = ", ".join(f"{v:.4f}" for v in first_10)
    return f"[{formatted}]"


async def generate_recommendation(results_list: list, image_path: str) -> str:
    products_text = "\n".join(
        f"- 商品图: {r['image_path']}, 相似度: {r['score']:.2f}"
        for r in results_list
    )

    visual_features_text = ""
    try:
        features_str = extract_image_features(image_path)
        visual_features_text = f"该图片的视觉特征向量前10维为：{features_str}\n"
    except Exception:
        pass

    prompt = (
        "你是一个友好的购物助手。用户上传了一张商品图片。\n"
        f"{visual_features_text}"
        "请结合这些视觉信息和以下相似商品列表，生成导购推荐语：\n\n"
        f"{products_text}\n\n"
        "请根据这些相似商品，帮用户做一个简短的分析推荐。"
        "用亲切、口语化的语气，像朋友推荐东西一样自然。说人话，控制在 150 字以内。"
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            url=f"{os.getenv('LLM_BASE_URL').rstrip('/')}/chat/completions",
            headers={
                "Authorization": f"Bearer {os.getenv('LLM_API_KEY')}",
                "Content-Type": "application/json",
            },
            json={
                "model": os.getenv("LLM_MODEL"),
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


@app.post("/api/agent/recommend")
async def recommend(file: UploadFile | None = File(None)):
    if file is None or file.filename == "":
        raise HTTPException(status_code=400, detail="请上传一张图片文件")

    # 保存上传图片到临时文件，供特征提取使用
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
    try:
        contents = await file.read()
        tmp.write(contents)
        tmp.close()
        image_path = tmp.name
    except Exception:
        tmp.close()
        os.unlink(tmp.name)
        raise HTTPException(status_code=500, detail="无法保存上传的图片")

    # 转发图片到搜索接口（Mock 模式）
    # try:
    #     async with httpx.AsyncClient(timeout=30.0) as client:
    #         search_resp = await client.post(
    #             SEARCH_URL,
    #             files={"file": (file.filename, await file.read(), file.content_type)},
    #         )
    #         search_resp.raise_for_status()
    #         search_data = search_resp.json()
    # except httpx.HTTPStatusError:
    #     raise HTTPException(
    #         status_code=502,
    #         detail="商品搜索服务暂时不可用，请稍后重试",
    #     )
    # except httpx.RequestError:
    #     raise HTTPException(
    #         status_code=502,
    #         detail="无法连接到商品搜索服务，请稍后重试",
    #     )
    #
    # results = search_data.get("results", [])

    mock_results = [
        {"image_path": "https://via.placeholder.com/300?text=相似商品1", "score": 0.95},
        {"image_path": "https://via.placeholder.com/300?text=相似商品2", "score": 0.88},
        {"image_path": "https://via.placeholder.com/300?text=相似商品3", "score": 0.75},
    ]
    results = mock_results

    # 调用大模型生成推荐语
    try:
        recommendation_note = await generate_recommendation(results, image_path)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"推荐语生成失败: {e}",
        )
    finally:
        if os.path.exists(image_path):
            os.unlink(image_path)

    return {
        "products": [
            {"image_path": r["image_path"], "similarity_score": r["score"]}
            for r in results
        ],
        "recommendation_note": recommendation_note,
    }
