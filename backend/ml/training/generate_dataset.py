"""Labeled dataset generator for the package/label detector (Task 3.1.1).

Renders synthetic "photographs" of retail packages with printed principal
display panels (PDP labels) and writes them in YOLO training format:

    backend/ml/data/package_label/
        images/train/*.jpg, images/val/*.jpg
        labels/train/*.txt, labels/val/*.txt   (class x_center y_center w h, normalized)
        dataset.yaml

Each photo contains exactly one package (class 0) and one printed label
(class 1) so the fine-tuned YOLOv8n learns both the package boundary and the
label region — replacing the pretrained-COCO/mock pipeline with a detector
whose classes match FR-004/FR-005.

Images are augmented with realistic variance (position, scale, rotation,
brightness/contrast, blur, JPEG noise, background clutter) so the model
transfers to real label photos. Deterministic via --seed.
"""

import argparse
import random
from pathlib import Path

import cv2
import numpy as np

IMG_W, IMG_H = 640, 480
CLASS_PACKAGE = 0
CLASS_LABEL = 1

PRODUCT_NAMES = [
    "REAL JUICE", "GOLD TEA", "AMUL BUTTER", "HALDIRAM NAMKEEN",
    "DABUR HONEY", "TATA SALT", "BRITANNIA MARIE", "NESCAFE CLASSIC",
    "MAGGI NOODLES", "LAYS CHIPS", "BOROPLUS CREAM", "COLGATE MAXFRESH",
    "LUX SOAP", "SURF EXCEL", "VIM BAR", "CHAIP POINT MASALA",
    "KISSAN JAM", "HERSHEYS COCOA", "PARLE-G", "MDH CHICKEN MASALA",
]

BRANDS = ["FreshMart", "DocketFoods", "AgroPure", "DailyBest", "NutriCo", "SpiceKing"]
UNITS = ["g", "kg", "ml", "L"]
MANUFACTURERS = [
    "Zenith Foods Pvt Ltd", "Shree Balaji Enterprises", "Metro Consumer Products",
    "Sunrise Agro Industries", "Annapurna Beverages Ltd",
]


def _random_background(rng: random.Random) -> np.ndarray:
    """Create a cluttered photo-like background (table / counter / gradient)."""
    bg_type = rng.choice(["texture", "gradient", "plaid"])
    img = np.zeros((IMG_H, IMG_W, 3), dtype=np.uint8)

    if bg_type == "texture":
        base = rng.randint(70, 190)
        img[:] = base
        noise = rng.randint(4, 14)
        img = cv2.add(img, np.random.default_rng(rng.getrandbits(32)).integers(
            -noise, noise + 1, img.shape, dtype=np.int16).astype(np.uint8))
    elif bg_type == "gradient":
        c1 = rng.randint(40, 120)
        c2 = rng.randint(130, 220)
        grad = np.linspace(c1, c2, IMG_H, dtype=np.uint8)
        img[:] = grad[:, None, None] * np.array([1.0, 0.95, 0.9])
    else:  # plaid tablecloth
        c = (rng.randint(60, 200), rng.randint(60, 200), rng.randint(60, 200))
        img[:] = c
        for y in range(0, IMG_H, 40):
            cv2.line(img, (0, y), (IMG_W, y), tuple(min(255, x + 25) for x in c), 3)
        for x in range(0, IMG_W, 40):
            cv2.line(img, (x, 0), (x, IMG_H), tuple(min(255, x2 + 25) for x2 in c), 3)

    # Scattered background clutter rectangles (other objects on the table)
    for _ in range(rng.randint(2, 6)):
        x, y = rng.randint(0, IMG_W - 80), rng.randint(0, IMG_H - 80)
        w, h = rng.randint(40, 160), rng.randint(30, 120)
        col = tuple(rng.randint(30, 230) for _ in range(3))
        cv2.rectangle(img, (x, y), (x + w, y + h), col, -1)
    return img


def _draw_barcode(img: np.ndarray, x: int, y: int, w: int, h: int, rng: random.Random) -> None:
    """Render a simple UPC-style barcode."""
    cv2.rectangle(img, (x, y), (x + w, y + h), (250, 250, 250), -1)
    cx = x + 4
    while cx < x + w - 4:
        bar_w = rng.choice([1, 1, 2, 2, 3])
        cv2.rectangle(img, (cx, y + 3), (min(cx + bar_w, x + w - 4), y + h - 3), (10, 10, 10), -1)
        cx += bar_w + rng.choice([1, 2, 2, 3])


def _render_package(
    img: np.ndarray,
    px: int, py: int, pw: int, ph: int,
    rng: random.Random,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]]:
    """Draw a shaded box-shaped package with a printed PDP label.

    Returns (package_xyxy, label_xyxy) in pixel coordinates.
    """
    pkg_color = tuple(rng.randint(25, 230) for _ in range(3))
    dark = tuple(int(c * 0.55) for c in pkg_color)

    # Package body with vertical shading for a 3D look
    for i in range(ph):
        t = i / max(ph - 1, 1)
        shade = tuple(int(c * (0.75 + 0.45 * t)) for c in pkg_color)
        row_x2 = px + pw + int(8 * t)  # slight perspective widening at base
        cv2.line(img, (px, py + i), (row_x2, py + i), shade, 1)
    # Side panel (right) + top flap to suggest box depth
    cv2.rectangle(img, (px + pw, py + 6), (px + pw + 10, py + ph), dark, -1)
    cv2.rectangle(img, (px, py - 6), (px + pw, py), dark, -1)

    # Printed label = principal display panel, centered on package front
    lab_w = int(pw * rng.uniform(0.62, 0.86))
    lab_h = int(ph * rng.uniform(0.55, 0.80))
    lx = px + (pw - lab_w) // 2
    ly = py + int((ph - lab_h) * rng.uniform(0.25, 0.45))

    lab_bg = rng.choice([(250, 250, 250), (245, 240, 225), (235, 245, 250), (250, 245, 235)])
    cv2.rectangle(img, (lx, ly), (lx + lab_w, ly + lab_h), lab_bg, -1)
    cv2.rectangle(img, (lx, ly), (lx + lab_w, ly + lab_h), (30, 30, 30), 2)

    # Label content: brand, product, declarations, barcode — like a real PDP
    pad = max(6, lab_w // 22)
    tx, ty = lx + pad, ly + pad
    line = max(12, int(lab_h * 0.11))

    cv2.putText(img, rng.choice(BRANDS).upper(), (tx, ty + line),
                cv2.FONT_HERSHEY_SIMPLEX, max(0.35, lab_w / 420), (40, 40, 40), 1)
    cv2.putText(img, rng.choice(PRODUCT_NAMES), (tx, ty + int(2.4 * line)),
                cv2.FONT_HERSHEY_SIMPLEX, max(0.42, lab_w / 300), (15, 15, 15), 2)

    qty = f"Net Qty. {rng.randint(50, 995)}{rng.choice(UNITS)}"
    cv2.putText(img, qty, (tx, ty + int(3.7 * line)),
                cv2.FONT_HERSHEY_SIMPLEX, max(0.30, lab_w / 500), (50, 50, 50), 1)
    cv2.putText(img, f"MRP Rs. {rng.randint(10, 499)}.00", (tx, ty + int(4.6 * line)),
                cv2.FONT_HERSHEY_SIMPLEX, max(0.30, lab_w / 520), (50, 50, 50), 1)
    cv2.putText(img, f"Mfg: {rng.choice(MANUFACTURERS)[:22]}", (tx, ty + int(5.5 * line)),
                cv2.FONT_HERSHEY_SIMPLEX, max(0.24, lab_w / 640), (70, 70, 70), 1)

    bc_w, bc_h = int(lab_w * 0.42), max(10, int(lab_h * 0.13))
    _draw_barcode(img, lx + pad, ly + lab_h - bc_h - pad, bc_w, bc_h, rng)

    # Batch/date block
    cv2.putText(img, f"Batch {rng.randint(100, 999)}", (tx, ty + int(6.3 * line)),
                cv2.FONT_HERSHEY_SIMPLEX, max(0.24, lab_w / 680), (70, 70, 70), 1)

    return (px, py, px + pw + 10, py + ph), (lx, ly, lx + lab_w, ly + lab_h)


def _augment(img: np.ndarray, rng: random.Random) -> np.ndarray:
    """Apply photo-realistic augmentations: exposure, blur, noise, rotation."""
    if rng.random() < 0.5:  # brightness/contrast (phone-camera exposure variance)
        alpha = rng.uniform(0.75, 1.25)
        beta = rng.randint(-28, 28)
        img = cv2.convertScaleAbs(img, alpha=alpha, beta=beta)
    if rng.random() < 0.35:  # slight defocus
        k = rng.choice([3, 3, 5])
        img = cv2.GaussianBlur(img, (k, k), rng.uniform(0.4, 1.2))
    if rng.random() < 0.30:  # sensor noise
        sigma = rng.uniform(3, 9)
        noise = np.random.default_rng(rng.getrandbits(32)).normal(0, sigma, img.shape)
        img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    if rng.random() < 0.40:  # small camera tilt
        angle = rng.uniform(-5.0, 5.0)
        h, w = img.shape[:2]
        M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
        img = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
    return img


def _write_yolo_label(path: Path, boxes: list[tuple[int, int, int, int]]) -> None:
    """Write normalized YOLO annotations: package then label."""
    lines = []
    for cls, (x1, y1, x2, y2) in zip([CLASS_PACKAGE, CLASS_LABEL], boxes):
        xc = ((x1 + x2) / 2) / IMG_W
        yc = ((y1 + y2) / 2) / IMG_H
        bw = (x2 - x1) / IMG_W
        bh = (y2 - y1) / IMG_H
        lines.append(f"{cls} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}")
    path.write_text("\n".join(lines) + "\n")


def generate_split(out_dir: Path, split: str, count: int, seed: int) -> None:
    rng = random.Random(seed)
    img_dir = out_dir / "images" / split
    lbl_dir = out_dir / "labels" / split
    img_dir.mkdir(parents=True, exist_ok=True)
    lbl_dir.mkdir(parents=True, exist_ok=True)

    for i in range(count):
        img = _random_background(rng)

        # Package occupies a plausible fraction of the frame
        pw = rng.randint(int(IMG_W * 0.28), int(IMG_W * 0.62))
        ph = rng.randint(int(IMG_H * 0.30), int(IMG_H * 0.62))
        px = rng.randint(10, max(11, IMG_W - pw - 40))
        py = rng.randint(20, max(21, IMG_H - ph - 12))

        pkg_box, lab_box = _render_package(img, px, py, pw, ph, rng)
        img = _augment(img, rng)

        jpeg_q = rng.randint(72, 95)
        cv2.imwrite(str(img_dir / f"{split}_{i:04d}.jpg"), img,
                    [cv2.IMWRITE_JPEG_QUALITY, jpeg_q])
        _write_yolo_label(lbl_dir / f"{split}_{i:04d}.txt", [pkg_box, lab_box])

    print(f"[{split}] wrote {count} images -> {img_dir}")


def write_dataset_yaml(out_dir: Path) -> None:
    yaml_path = out_dir / "dataset.yaml"
    yaml_path.write_text(
        f"path: {out_dir}\n"
        "train: images/train\n"
        "val: images/val\n"
        "names:\n"
        "  0: package\n"
        "  1: label\n"
    )
    print(f"dataset.yaml -> {yaml_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate package/label detection dataset")
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent / "data" / "package_label"))
    parser.add_argument("--train", type=int, default=260)
    parser.add_argument("--val", type=int, default=60)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    out_dir = Path(args.out)
    generate_split(out_dir, "train", args.train, args.seed)
    generate_split(out_dir, "val", args.val, args.seed + 1000)
    write_dataset_yaml(out_dir)


if __name__ == "__main__":
    main()
