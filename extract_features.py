import argparse
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torchvision import models, transforms
from tqdm import tqdm

# 预处理：ResNet 要求的输入
transform = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

# 支持的图片格式
IMG_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def load_model() -> torch.nn.Module:
    model = models.resnet18(weights=models.ResNet18_Weights.IMAGENET1K_V1)
    model.fc = torch.nn.Identity()  # 替换分类层为恒等映射，输出 512 维
    model.eval()
    return model


def extract_features(
    image_dir: Path,
    model: torch.nn.Module,
    device: torch.device,
) -> tuple[np.ndarray, list[str]]:
    model = model.to(device)
    image_paths = sorted(
        p for p in image_dir.iterdir() if p.suffix.lower() in IMG_EXTENSIONS
    )
    if not image_paths:
        raise ValueError(f"文件夹 {image_dir} 中没有找到图片文件")

    features_list = []
    valid_paths = []

    for img_path in tqdm(image_paths, desc="提取特征", unit="张"):
        try:
            img = Image.open(img_path).convert("RGB")
            tensor = transform(img).unsqueeze(0).to(device)
            with torch.no_grad():
                feat = model(tensor).squeeze().cpu().numpy()
            features_list.append(feat)
            valid_paths.append(str(img_path))
        except Exception as e:
            tqdm.write(f"跳过 {img_path.name}: {e}")

    return np.stack(features_list), valid_paths


def main():
    parser = argparse.ArgumentParser(description="ResNet18 图片特征提取")
    parser.add_argument("image_dir", type=str, help="商品图片文件夹路径")
    parser.add_argument("-o", "--output", type=str, default="features.npz",
                        help="输出 npz 文件路径 (默认 features.npz)")
    parser.add_argument("--device", type=str, default="cpu",
                        help="设备: cpu / cuda / mps (默认 cpu)")
    args = parser.parse_args()

    image_dir = Path(args.image_dir)
    if not image_dir.is_dir():
        raise NotADirectoryError(f"文件夹不存在: {image_dir}")

    device = torch.device(args.device)
    print(f"使用设备: {device}")

    model = load_model()
    features, paths = extract_features(image_dir, model, device)

    np.savez(args.output, features=features, paths=np.array(paths))
    print(f"完成: {len(paths)} 张图片 → {features.shape} → {args.output}")


if __name__ == "__main__":
    main()
