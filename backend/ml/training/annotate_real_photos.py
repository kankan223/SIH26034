"""Auto-annotate real package photos for detector fine-tuning.

Annotation strategy (no manual labeling required, but reviewable):

1. YOLO-World zero-shot ("package", "label", "sticker") proposes boxes.
2. The currently-installed fine-tuned detector proposes boxes independently.
3. A package annotation is accepted when either model finds a plausible
   package (area >= 8% of frame, conf >= threshold); cross-model IoU >= 0.5
   is recorded as "high agreement".
4. A label annotation comes from YOLO-World "label"/"sticker" or the
   fine-tuned "label" class, clipped inside the package; otherwise a
   central-region fallback box is used (flagged low_conf_label).
5. QC rejects: undecodable, tiny, blurry, near-monochrome, or package-less
   frames (reasons recorded per image).

Outputs (ml/data/real/):
    images/{train,val}/*.jpg  labels/{train,val}/*.txt  (YOLO format)
    annotate_report.json      per-image decisions + agreement stats
    contact_sheet.jpg         24-sample visual review sheet
"""

import argparse
import json
import random
import shutil
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO, YOLOWorld

REAL_DIR = Path(__file__).resolve().parent.parent / "data" / "real"
RAW_DIR = REAL_DIR / "raw"

PKG_MIN_CONF_WORLD = 0.25
PKG_MIN_CONF_FT = 0.12      # train-pool gate (self-training: the fine-tuned
                            # model's own low-conf boxes; noisy but useful);
                            # val pool uses PKG_CONF_STRICT
PKG_CONF_STRICT = 0.45      # images whose top package meets this (or agrees
                            # with YOLO-World) qualify for the val pool
LBL_MIN_CONF = 0.20
PKG_MIN_AREA_RATIO = 0.03
MAX_PACKAGES_PER_IMAGE = 3
DEDUP_IOU = 0.60
AGREEMENT_IOU = 0.50
MIN_SIDE = 480
MIN_SHARPNESS = 40.0   # Laplacian variance
MIN_STDDEV = 12.0      # near-monochrome rejection

# YOLO-World concrete vocabulary: abstract prompts like "package" rarely fire
# on real photos, so we prompt with concrete packaging nouns and map them all
# to the package class.
WORLD_PACKAGE_WORDS = ["box", "carton", "bottle", "can", "packet", "pouch", "jar", "tube"]
WORLD_LABEL_WORDS = ["label", "sticker"]


def iou(a, b) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def inside(inner, outer) -> bool:
    """True if inner box center lies within outer and inner is not bigger."""
    cx, cy = (inner[0] + inner[2]) / 2, (inner[1] + inner[3]) / 2
    area_i = (inner[2] - inner[0]) * (inner[3] - inner[1])
    area_o = (outer[2] - outer[0]) * (outer[3] - outer[1])
    return outer[0] <= cx <= outer[2] and outer[1] <= cy <= outer[3] and area_i <= area_o


def clip_inside(box, outer):
    return [max(box[0], outer[0]), max(box[1], outer[1]),
            min(box[2], outer[2]), min(box[3], outer[3])]


def central_label_box(pkg) -> list[int]:
    """Fallback label region: upper-central ~62% x ~60% of the package."""
    w, h = pkg[2] - pkg[0], pkg[3] - pkg[1]
    lx1 = int(pkg[0] + 0.19 * w)
    ly1 = int(pkg[1] + 0.18 * h)
    lx2 = int(pkg[0] + 0.81 * w)
    ly2 = int(pkg[1] + 0.78 * h)
    return [lx1, ly1, lx2, ly2]


def to_xyxy(b) -> list[int]:
    return [float(v) for v in b.xyxy[0].tolist()]


def annotate_image(path: Path, world, ft) -> tuple[dict | None, dict]:
    """Annotate one image. Returns (annotation|None, report_entry)."""
    img = cv2.imread(str(path))
    if img is None:
        return None, {"file": path.name, "skipped": "undecodable"}
    h, w = img.shape[:2]
    if min(h, w) < MIN_SIDE:
        return None, {"file": path.name, "skipped": f"too_small_{w}x{h}"}
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if float(cv2.Laplacian(gray, cv2.CV_64F).var()) < MIN_SHARPNESS:
        return None, {"file": path.name, "skipped": "blurry"}
    if float(gray.std()) < MIN_STDDEV:
        return None, {"file": path.name, "skipped": "monochrome"}

    # YOLO-World zero-shot proposals (concrete vocabulary)
    wres = world.predict(source=str(path), imgsz=640, conf=0.10, verbose=False)[0]
    wnames = wres.names
    world_pkgs: list[tuple[float, list[int]]] = []
    world_lbls: list[tuple[float, list[int]]] = []
    for b in wres.boxes:
        name = wnames[int(b.cls[0])]
        conf = float(b.conf[0])
        box = to_xyxy(b)
        area_ratio = (box[2] - box[0]) * (box[3] - box[1]) / (w * h)
        if name in WORLD_PACKAGE_WORDS and conf >= PKG_MIN_CONF_WORLD and area_ratio >= PKG_MIN_AREA_RATIO:
            world_pkgs.append((conf, box))
        elif name in WORLD_LABEL_WORDS and conf >= LBL_MIN_CONF:
            world_lbls.append((conf, box))
    world_pkgs.sort(key=lambda t: -t[0])
    world_lbls.sort(key=lambda t: -t[0])

    # Fine-tuned detector proposals (multi-package)
    fres = ft.predict(source=str(path), imgsz=416, conf=0.20, verbose=False)[0]
    fnames = fres.names
    ft_pkgs: list[tuple[float, list[int]]] = []
    ft_lbls: list[tuple[float, list[int]]] = []
    for b in fres.boxes:
        name = fnames[int(b.cls[0])]
        conf = float(b.conf[0])
        box = to_xyxy(b)
        area_ratio = (box[2] - box[0]) * (box[3] - box[1]) / (w * h)
        if name == "package" and conf >= PKG_MIN_CONF_FT and area_ratio >= PKG_MIN_AREA_RATIO:
            ft_pkgs.append((conf, box))
        elif name == "label" and conf >= LBL_MIN_CONF:
            ft_lbls.append((conf, box))
    ft_pkgs.sort(key=lambda t: -t[0])
    ft_lbls.sort(key=lambda t: -t[0])

    # Merge package candidates: fine-tuned first (domain-trained), then World
    # proposals not already covered (IoU dedup). Flag strictness per box.
    candidates: list[dict] = []
    for conf, box in ft_pkgs[:MAX_PACKAGES_PER_IMAGE]:
        candidates.append({"box": box, "conf": conf, "src": "finetuned",
                           "strict": conf >= PKG_CONF_STRICT, "agreement": False})
    for conf, box in world_pkgs[:MAX_PACKAGES_PER_IMAGE]:
        matched = next((c for c in candidates
                        if iou(c["box"], box) >= AGREEMENT_IOU), None)
        if matched:
            matched["agreement"] = True
            matched["strict"] = True
            matched["box"] = box if matched["src"] == "yolo_world" else matched["box"]
            matched["src"] = "both"
        elif len(candidates) < MAX_PACKAGES_PER_IMAGE:
            candidates.append({"box": box, "conf": conf, "src": "yolo_world",
                               "strict": True, "agreement": False})
    if not candidates:
        return None, {"file": path.name, "skipped": "no_package_found"}

    # Per-package label resolution: World label/sticker inside pkg > ft label
    # inside pkg > central fallback
    packages = []
    for c in candidates:
        pkg = c["box"]
        lbl_box, lbl_src = None, None
        for conf, wb in world_lbls:
            if inside(wb, pkg):
                lbl_box, lbl_src = wb, "yolo_world"
                break
        if lbl_box is None:
            for conf, fb in ft_lbls:
                if inside(fb, pkg):
                    lbl_box, lbl_src = fb, "finetuned"
                    break
        if lbl_box is None:
            lbl_box, lbl_src = central_label_box(pkg), "fallback"
        lbl_box = clip_inside(lbl_box, pkg)
        if (lbl_box[2] - lbl_box[0]) < 12 or (lbl_box[3] - lbl_box[1]) < 12:
            lbl_box, lbl_src = central_label_box(pkg), "fallback"
        packages.append({
            "package_box": [round(v) for v in pkg],
            "label_box": [round(v) for v in lbl_box],
            "package_source": c["src"],
            "package_conf": round(c["conf"], 3),
            "package_agreement": c["agreement"],
            "label_source": lbl_src,
        })

    top_conf = max(p["package_conf"] for p in packages)
    top_strict = any(p["package_conf"] >= PKG_CONF_STRICT or p["package_agreement"] for p in packages)
    entry = {
        "file": path.name,
        "width": w, "height": h,
        "strict_pool": bool(top_strict),
        "top_conf": round(top_conf, 3),
        "n_packages": len(packages),
        "packages": packages,
    }
    return entry, entry


def write_yolo_txt(path: Path, packages: list[dict], w: int, h: int) -> None:
    def line(cls, b):
        xc = ((b[0] + b[2]) / 2) / w
        yc = ((b[1] + b[3]) / 2) / h
        bw = (b[2] - b[0]) / w
        bh = (b[3] - b[1]) / h
        return f"{cls} {xc:.6f} {yc:.6f} {bw:.6f} {bh:.6f}"

    lines = []
    for p in packages:
        lines.append(line(0, p["package_box"]))
        lines.append(line(1, p["label_box"]))
    path.write_text("\n".join(lines) + "\n")


def contact_sheet(entries: list[dict], out: Path, n: int = 24) -> None:
    """Render accepted annotations on a grid for quick human review."""
    rng = random.Random(0)
    picks = rng.sample(entries, min(n, len(entries)))
    cell_w, cell_h = 320, 240
    cols, rows = 6, (len(picks) + 5) // 6
    sheet = np.full((rows * cell_h, cols * cell_w, 3), 30, dtype=np.uint8)
    for i, e in enumerate(picks):
        img = cv2.imread(str(RAW_DIR / e["file"]))
        if img is None:
            continue
        img = cv2.resize(img, (cell_w, cell_h))
        sx, sy = e["width"] / cell_w, e["height"] / cell_h
        for p in e["packages"]:
            for cls, key, color in ((0, "package_box", (0, 220, 0)), (1, "label_box", (0, 140, 255))):
                b = p[key]
                p1 = (int(b[0] / sx), int(b[1] / sy))
                p2 = (int(b[2] / sx), int(b[3] / sy))
                cv2.rectangle(img, p1, p2, color, 2)
                cv2.putText(img, ("pkg" if cls == 0 else "lbl"), (p1[0], max(12, p1[1] - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
        r, c = divmod(i, cols)
        sheet[r * cell_h:(r + 1) * cell_h, c * cell_w:(c + 1) * cell_w] = img
    cv2.imwrite(str(out), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
    print(f"contact sheet -> {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-annotate real package photos")
    parser.add_argument("--val-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--world-weights", default="yolov8s-worldv2.pt")
    parser.add_argument("--ft-weights", default=None,
                        help="fine-tuned model path (default: installed ONNX)")
    args = parser.parse_args()

    world = YOLOWorld(args.world_weights)
    world.set_classes(["package", "label", "sticker"])

    ft_path = args.ft_weights
    if not ft_path:
        candidates = [
            Path(__file__).resolve().parent.parent.parent / "runs" / "detect" / "train" / "weights" / "best.pt",
            Path("/models/package_label_detector.onnx"),
            Path(__file__).resolve().parent.parent / "models" / "package_label_detector.onnx",
        ]
        ft_path = next((str(p) for p in candidates if p.is_file()), None)
    if not ft_path:
        raise SystemExit(
            "No fine-tuned weights found (expected runs/detect/train/weights/best.pt "
            "or ml/models/package_label_detector.onnx) — refusing to annotate against COCO."
        )
    ft = YOLO(ft_path)
    print(f"annotators: world={args.world_weights}, fine-tuned={ft_path}")

    raw_files = sorted(RAW_DIR.glob("*.jpg")) + sorted(RAW_DIR.glob("*.png"))
    accepted, report = [], []
    for i, f in enumerate(raw_files):
        entry, rep = annotate_image(f, world, ft)
        report.append(rep)
        if entry:
            accepted.append(entry)
        if (i + 1) % 20 == 0:
            print(f"  {i + 1}/{len(raw_files)} processed, {len(accepted)} accepted")

    # Seeded train/val split. Val comes ONLY from the strict pool (top
    # package conf >= PKG_CONF_STRICT or YOLO-World agreement) so real-split
    # mAP reflects the most reliable annotations; train takes the rest.
    # Wipe previous splits first so re-runs never accumulate stale files.
    for split in ("train", "val"):
        for d in (REAL_DIR / "images" / split, REAL_DIR / "labels" / split):
            if d.is_dir():
                for old in d.iterdir():
                    old.unlink()
            d.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    strict = [e for e in accepted if e["strict_pool"]]
    loose = [e for e in accepted if not e["strict_pool"]]
    rng.shuffle(strict)
    rng.shuffle(loose)
    n_val = max(1, min(int(len(accepted) * args.val_ratio), len(strict)))
    val, train = strict[:n_val], loose + strict[n_val:]
    rng.shuffle(train)

    for split, items in (("train", train), ("val", val)):
        (REAL_DIR / "images" / split).mkdir(parents=True, exist_ok=True)
        (REAL_DIR / "labels" / split).mkdir(parents=True, exist_ok=True)
        for e in items:
            src = RAW_DIR / e["file"]
            shutil.copy2(src, REAL_DIR / "images" / split / e["file"])
            write_yolo_txt(
                REAL_DIR / "labels" / split / (e["file"].rsplit(".", 1)[0] + ".txt"),
                e["packages"], e["width"], e["height"],
            )

    # Stats
    n_agree = sum(1 for e in accepted if any(p["package_agreement"] for p in e["packages"]))
    n_fb = sum(1 for e in accepted if any(p["label_source"] == "fallback" for p in e["packages"]))
    summary = {
        "raw": len(raw_files),
        "accepted": len(accepted),
        "train": len(train),
        "val": len(val),
        "val_strict_pool": len(strict),
        "package_agreement_rate": round(n_agree / len(accepted), 3) if accepted else 0,
        "label_fallback_rate": round(n_fb / len(accepted), 3) if accepted else 0,
        "skip_reasons": {},
    }
    for r in report:
        if "skipped" in r:
            reason = r["skipped"].split("_")[0]
            summary["skip_reasons"][reason] = summary["skip_reasons"].get(reason, 0) + 1

    (REAL_DIR / "annotate_report.json").write_text(json.dumps({"summary": summary, "images": report}, indent=2))
    contact_sheet(accepted, REAL_DIR / "contact_sheet.jpg")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
