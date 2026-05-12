import os

import httpx
from fastapi import FastAPI, File, HTTPException, UploadFile
from openai import OpenAI

# 阿里百炼 (DashScope) 环境变量配置
#   LLM_API_KEY    — API Key，从阿里云百炼控制台获取
#   LLM_BASE_URL   — https://dashscope.aliyuncs.com/compatible-mode/v1
#   LLM_MODEL      — 可选 qwen-turbo / qwen-plus / qwen-max / qwen3-235b-a22b

app = FastAPI()

SEARCH_URL = "https://whisper1234-ai-shop-agent-api.hf.space/search"


def generate_recommendation(results_list: list) -> str:
    products_text = "\n".join(
        f"- {r}" for r in results_list[:10]
    )

    prompt = (
        "你是一个友好的购物助手。用户上传了一张商品图片，以下是根据图片找到的相似商品列表：\n\n"
        f"{products_text}\n\n"
        "请根据这些相似商品，帮用户做一个简短的分析推荐。"
        "用亲切、口语化的语气，像朋友推荐东西一样自然。说人话，控制在 150 字以内。"
    )

    client = OpenAI(
        api_key=os.environ["LLM_API_KEY"],
        base_url=os.environ["LLM_BASE_URL"],
    )

    response = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        messages=[{"role": "user", "content": prompt}],
        timeout=30.0,
    )

    return response.choices[0].message.content.strip()


@app.post("/api/agent/recommend")
async def recommend(file: UploadFile | None = File(None)):
    if file is None or file.filename == "":
        raise HTTPException(status_code=400, detail="请上传一张图片文件")

    # 转发图片到搜索接口
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            search_resp = await client.post(
                SEARCH_URL,
                files={"file": (file.filename, await file.read(), file.content_type)},
            )
            search_resp.raise_for_status()
            search_data = search_resp.json()
    except httpx.HTTPStatusError:
        raise HTTPException(
            status_code=502,
            detail="商品搜索服务暂时不可用，请稍后重试",
        )
    except httpx.RequestError:
        raise HTTPException(
            status_code=502,
            detail="无法连接到商品搜索服务，请稍后重试",
        )

    results = search_data.get("results", [])

    # 调用大模型生成推荐语
    try:
        recommendation_note = generate_recommendation(results)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"推荐语生成失败: {e}",
        )

    return {
        "products": [
            {"image_path": r["image_path"], "similarity_score": r["score"]}
            for r in results
        ],
        "recommendation_note": recommendation_note,
    }
