# 聊天记录 — app.py 迭代修改

日期: 2026-05-13 ~ 2026-05-14

---

## 1. 图像特征融合

**需求**: 在 `generate_recommendation` 中增加图像特征融合能力。

**改动**:
- 函数签名增加 `image_path: str` 参数
- 用 `torchvision.models.resnet18(pretrained=True)` 去掉分类头，提取 512 维特征向量
- 取前 10 维，保留 4 位小数，格式化为 `[0.1234, -0.5678, ...]`
- 追加到 prompt: `该图片的视觉特征向量前10维为：[...]`
- 模型加载用 `@lru_cache(maxsize=1)` 缓存
- 特征提取失败时静默跳过，不影响原有推荐逻辑

**关键代码**:
```python
@lru_cache(maxsize=1)
def get_feature_extractor():
    model = models.resnet18(pretrained=True)
    model = torch.nn.Sequential(*list(model.children())[:-1])
    model.eval()
    return model

def extract_image_features(image_path: str) -> str:
    # 预处理 → 推理 → 取前10维 → 格式化
    ...
```

---

## 2. 修复 torch 导入导致容器启动崩溃

**问题**: 容器环境没有安装 `torch`，顶层 `import torch` 导致 uvicorn 启动失败。

**修复**: 将 `torch`、`torchvision`、`PIL` 从顶层导入改为函数内惰性导入:
```python
# 顶层只保留轻量依赖
import httpx
from fastapi import ...

# torch 在 get_feature_extractor() / extract_image_features() 内部按需 import
```

这样即使环境没有 torch，服务也能正常启动；特征提取时若缺依赖，`except Exception: pass` 静默跳过。

---

## 3. 搜索接口适配

**需求**: 适配 B 同学搜索接口返回的不同字段名，启用真实接口。

**改动**:
- 取消真实搜索接口注释，启用 `POST SEARCH_URL`
- Mock 数据注释掉
- 商品路径字段兼容: `image_path` → `path` → `filename` 三级 fallback
- 结果归一化为 `{"image_path": "...", "score": 0.95}`

```python
raw_results = search_data.get("results", [])
results = []
for r in raw_results:
    img_path = r.get("image_path") or r.get("path") or r.get("filename")
    results.append({"image_path": img_path, "score": r.get("score", 0)})
```

---

## 4. Bug 修复: 文件内容二次读取

**问题**: 上传图片先 `file.read()` 保存临时文件，后面搜索接口再次 `file.read()` 时指针已到末尾，读到空字节。

**修复**: 只调用一次 `file.read()`，`contents` 变量复用:
```python
contents = await file.read()          # 只读一次
tmp.write(contents)                    # 写临时文件
files={"file": (..., contents, ...)}  # 转发搜索接口
```

---

## 5. 新增 POST /api/agent/feedback 接口

**请求体**:
```json
{
  "feedback": "like",
  "last_products": [...]
}
```

**逻辑**:
- `feedback` 校验: 必须是 `"like"` 或 `"dislike"`，否则 400
- `last_products` 不能为空，否则 400
- **like**: prompt 让千问推荐更多风格相似的商品
- **dislike**: prompt 让千问换个完全不同的风格重新推荐
- 返回格式与 `/api/agent/recommend` 一致，`products` 复用 `last_products`，仅 `recommendation_note` 重新生成
- 商品字段兼容 `image_path`/`path`、`score`/`similarity_score`

---

## 当前 app.py 结构概览

| 函数/端点 | 说明 |
|---|---|
| `get_feature_extractor()` | `@lru_cache` 缓存的 ResNet18 特征提取器 |
| `extract_image_features()` | 提取图片前 10 维特征并格式化 |
| `generate_recommendation()` | 生成导购推荐语（含视觉特征融合） |
| `POST /api/agent/recommend` | 图片上传 → 搜索 → 推荐 |
| `POST /api/agent/feedback` | 用户反馈 → 重新生成推荐语 |
