"""
SearchEasy 余弦相似度检索引擎
基于 ResNet18 预提取的特征向量，对查询图片做余弦相似度检索。
"""
from pathlib import Path
from typing import Optional

import numpy as np


class SearchEngine:
    """余弦相似度图像检索引擎"""

    def __init__(self):
        self._features: Optional[np.ndarray] = None   # shape: (N, 512)
        self._paths: Optional[np.ndarray] = None       # shape: (N,), dtype=str
        self._image_base_dir: str = ""

    # ── 加载 ──────────────────────────────────────────────

    def load(self, npz_path: str, image_base_dir: str = "", meta_path: str = "") -> "SearchEngine":
        """从 .npz 文件加载预提取的特征库。

        Args:
            npz_path:       extract_features.py 输出的 .npz 文件路径
            image_base_dir: 图片根目录（用于转换为相对路径 / URL 拼接）
            meta_path:      商品元数据 JSON 文件路径（可选）
        """
        data = np.load(npz_path, allow_pickle=False)
        self._features = data["features"].astype(np.float32)
        self._paths = data["paths"]
        self._image_base_dir = image_base_dir

        # 加载商品描述元数据
        self._meta = {}
        if meta_path and Path(meta_path).exists():
            import json
            with open(meta_path, "r", encoding="utf-8") as f:
                self._meta = json.load(f)

        # L2 归一化，使余弦相似度 = 内积
        norms = np.linalg.norm(self._features, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._features = self._features / norms

        return self

    @property
    def is_loaded(self) -> bool:
        return self._features is not None

    @property
    def size(self) -> int:
        return len(self._features) if self._features is not None else 0

    # ── 检索 ──────────────────────────────────────────────

    def search(
        self,
        query_vec: np.ndarray,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> list[dict]:
        """余弦相似度检索，返回 top-k 相似商品。

        Args:
            query_vec:  查询图像的特征向量，shape (512,) 或 (1, 512)
            top_k:      返回结果数
            min_score:  最低相似度阈值 (0~1)

        Returns:
            [{"image_path": str, "score": float}, ...]  按相似度降序
        """
        if not self.is_loaded:
            raise RuntimeError("特征库未加载，请先调用 .load()")

        query = np.asarray(query_vec, dtype=np.float32).flatten()

        # L2 归一化查询向量
        q_norm = np.linalg.norm(query)
        if q_norm == 0:
            return []
        query = query / q_norm

        # 余弦相似度 = 归一化向量的内积
        scores = np.dot(self._features, query)  # shape: (N,)

        # 取 top-k
        top_k = min(top_k, len(scores))
        if top_k == 0:
            return []

        top_indices = np.argpartition(-scores, top_k - 1)[:top_k]
        top_indices = top_indices[np.argsort(-scores[top_indices])]

        results = []
        for idx in top_indices:
            score = float(scores[idx])
            if score < min_score:
                continue
            raw_path = str(self._paths[idx])
            image_path = self._resolve_path(raw_path)
            results.append({
                "image_path": image_path,
                "label": self._make_label(image_path),
                "score": round(score, 4),
            })

        return results

    # ── 辅助 ──────────────────────────────────────────────

    def _make_label(self, image_path: str) -> str:
        """从元数据获取商品信息，合并为描述字符串。兼容新旧格式"""
        # 统一路径分隔符为 /
        image_path = image_path.replace('\\', '/')
        meta = self._meta.get(image_path, {})
        if not meta:
            name = Path(image_path).name
            for key, val in self._meta.items():
                if key.endswith(name) or Path(key).name == name:
                    meta = val; break
        if isinstance(meta, dict):
            return f"{meta.get('name','')} · {meta.get('desc','')} · ¥{meta.get('price','暂无')}"
        if isinstance(meta, str):
            return meta  # 旧格式兼容
        return Path(image_path).stem

    def _resolve_path(self, raw_path: str) -> str:
        """将本地绝对路径转换为可访问的相对路径 (统一 / 分隔符)。"""
        raw_path = raw_path.replace('\\', '/')
        path = Path(raw_path)
        if self._image_base_dir:
            base = Path(self._image_base_dir.replace('\\', '/'))
            try:
                rel = path.relative_to(base)
                return str(rel).replace("\\", "/")
            except ValueError:
                pass
        return raw_path.split('/')[-1] if '/' in raw_path else path.name

    def get_image_url(self, image_path: str, base_url: str = "") -> str:
        """拼接完整的图片访问 URL。"""
        path = image_path.lstrip("/")
        if base_url:
            base_url = base_url.rstrip("/")
            return f"{base_url}/{path}"
        return f"/images/{path}"

    def stats(self) -> dict:
        """返回特征库统计信息"""
        return {
            "total_images": self.size,
            "feature_dim": self._features.shape[1] if self._features is not None else 0,
            "image_base_dir": self._image_base_dir or "(未设置)",
        }


# ── 全局单例 ──────────────────────────────────────────────
engine = SearchEngine()
