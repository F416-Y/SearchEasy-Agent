import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from sklearn.manifold import TSNE

# 固定色板，类别多的时候自动循环
CMAP = plt.cm.tab10


def load_features(npz_path: str) -> tuple[np.ndarray, np.ndarray]:
    data = np.load(npz_path)
    return data["features"], data["paths"]


def extract_labels(paths: np.ndarray) -> list[str]:
    """从图片路径中提取父文件夹名作为类别标签"""
    labels = []
    for p in paths:
        labels.append(Path(str(p)).parent.name)
    return labels


def main():
    parser = argparse.ArgumentParser(description="t-SNE 特征可视化")
    parser.add_argument("npz_path", type=str, default="features.npz",
                        help="features.npz 文件路径")
    parser.add_argument("-o", "--output", type=str, default="tsne_visualization.png",
                        help="输出图片路径")
    parser.add_argument("--perplexity", type=float, default=30.0,
                        help="t-SNE perplexity 参数 (默认 30)")
    parser.add_argument("--seed", type=int, default=42,
                        help="随机种子 (默认 42)")
    args = parser.parse_args()

    print("加载特征...")
    features, paths = load_features(args.npz_path)
    print(f"  特征矩阵: {features.shape}")

    labels = extract_labels(paths)
    unique_labels = sorted(set(labels))
    n_classes = len(unique_labels)
    print(f"  类别数: {n_classes}  →  {unique_labels}")

    print(f"执行 t-SNE (perplexity={args.perplexity})...")
    tsne = TSNE(
        n_components=2,
        perplexity=min(args.perplexity, len(features) - 1),
        random_state=args.seed,
    )
    embedded = tsne.fit_transform(features)

    print("绘制散点图...")
    fig, ax = plt.subplots(figsize=(12, 10))

    for i, label in enumerate(unique_labels):
        mask = np.array([l == label for l in labels])
        color = CMAP(i % 10)
        ax.scatter(
            embedded[mask, 0], embedded[mask, 1],
            c=[color], label=label, s=20, alpha=0.7,
        )

    ax.set_title(f"t-SNE Visualization ({n_classes} classes, {len(features)} images)",
                 fontsize=14)
    ax.legend(markerscale=3, fontsize=8, loc="best")
    ax.set_xticks([])
    ax.set_yticks([])

    fig.tight_layout()
    fig.savefig(args.output, dpi=300)
    print(f"已保存: {args.output}")


if __name__ == "__main__":
    main()
