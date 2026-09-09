"""Evaluate a detector ONNX on the real-photo val split (no AutoBackend).

Loads the ONNX directly with onnxruntime, decodes (1, 4+nc, N) predictions
with letterbox preprocessing, and computes per-class mAP50 the same way
Ultralytics validation does (greedy matching at IoU 0.50, predictions
sorted by confidence, per-image NMS first).

Usage (inside the backend container):
    python ml/training/eval_real.py --onnx <path> [--iou 0.5]
"""

import argparse
import ast
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

REAL_VAL = Path(__file__).resolve().parent.parent / "data" / "real" / "images" / "val"
REAL_VAL_LBL = Path(__file__).resolve().parent.parent / "data" / "real" / "labels" / "val"
NAMES = {0: "package", 1: "label"}
IMGSZ = 416
CONF = 0.25   # evaluation operating point (>= 0.5 runtime requirement is separate)
IOU_MATCH = 0.50
IOU_NMS = 0.45


def letterbox(img: np.ndarray, size: int):
    h, w = img.shape[:2]
    scale = min(size / w, size / h)
    nw, nh = int(round(w * scale)), int(round(h * scale))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    px, py = (size - nw) // 2, (size - nh) // 2
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    canvas[py:py + nh, px:px + nw] = resized
    return canvas, scale, px, py


def nms(boxes: list[tuple[float, float, float, float]], scores: list[float], iou_th: float) -> list[int]:
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    keep = []
    for i in order:
        ok = True
        for j in keep:
            a, b = boxes[i], boxes[j]
            ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
            ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            area_a = (a[2] - a[0]) * (a[3] - a[1])
            area_b = (b[2] - b[0]) * (b[3] - b[1])
            union = area_a + area_b - inter
            if union > 0 and inter / union > iou_th:
                ok = False
                break
        if ok:
            keep.append(i)
    return keep


def detect(session, img: np.ndarray):
    """Run one image through the ONNX. Returns {cls: [(conf, xyxy), ...]}."""
    h, w = img.shape[:2]
    canvas, scale, px, py = letterbox(img, IMGSZ)
    blob = canvas[:, :, ::-1].transpose(2, 0, 1).astype(np.float32) / 255.0
    blob = np.ascontiguousarray(blob[None])
    preds = session.run(None, {session.get_inputs()[0].name: blob})[0]
    if preds.ndim == 3:
        preds = preds[0]
    if preds.shape[0] < preds.shape[1]:
        preds = preds.T

    boxes_all = preds[:, :4]
    scores_all = preds[:, 4:]
    class_ids = scores_all.argmax(axis=1)
    confidences = scores_all.max(axis=1)

    out = {c: [] for c in NAMES.values()}
    for i in np.where(confidences >= CONF)[0]:
        cx, cy, bw, bh = boxes_all[i]
        x1 = (cx - bw / 2 - px) / scale
        y1 = (cy - bh / 2 - py) / scale
        x2 = (cx + bw / 2 - px) / scale
        y2 = (cy + bh / 2 - py) / scale
        out[NAMES[int(class_ids[i])]].append(
            (float(confidences[i]), (x1, y1, x2, y2))
        )
    # per-image NMS per class
    for cls in out:
        boxes = [b for _, b in out[cls]]
        scores = [c for c, _ in out[cls]]
        keep = nms(boxes, scores, IOU_NMS)
        out[cls] = [out[cls][i] for i in keep]
    return out


def load_gt(label_path: Path, w: int, h: int):
    gt = {c: [] for c in NAMES.values()}
    if not label_path.is_file():
        return gt
    for line in label_path.read_text().splitlines():
        parts = line.split()
        if len(parts) != 5:
            continue
        c = NAMES[int(parts[0])]
        xc, yc, bw, bh = (float(v) for v in parts[1:])
        x1 = (xc - bw / 2) * w
        y1 = (yc - bh / 2) * h
        x2 = (xc + bw / 2) * w
        y2 = (yc + bh / 2) * h
        gt[c].append((x1, y1, x2, y2))
    return gt


def ap_at_iou(matched_flags_sorted: list[bool], n_gt: int) -> float:
    """AP from a confidence-sorted list of TP flags (VOC-style continuous)."""
    if n_gt == 0:
        return float("nan")
    tp_cum, fp_cum = 0, 0
    precisions, recalls = [], []
    for flag in matched_flags_sorted:
        if flag:
            tp_cum += 1
        else:
            fp_cum += 1
        precisions.append(tp_cum / (tp_cum + fp_cum))
        recalls.append(tp_cum / n_gt)
    # envelope + integration
    mrec = np.concatenate(([0.0], np.array(recalls), [1.0]))
    mpre = np.concatenate(([0.0], np.array(precisions), [0.0]))
    for i in range(len(mpre) - 2, -1, -1):
        mpre[i] = max(mpre[i], mpre[i + 1])
    idx = np.where(mrec[1:] != mrec[:-1])[0]
    return float(np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1]))


def evaluate(session) -> dict:
    per_cls = {c: {"n_gt": 0, "preds": []} for c in NAMES.values()}  # preds: (conf, img, flag_tp)
    image_files = sorted(REAL_VAL.glob("*.jpg")) + sorted(REAL_VAL.glob("*.png"))

    for img_path in image_files:
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        h, w = img.shape[:2]
        dets = detect(session, img)
        gt = load_gt(REAL_VAL_LBL / (img_path.stem + ".txt"), w, h)

        for cls in NAMES.values():
            per_cls[cls]["n_gt"] += len(gt[cls])
            gt_used = [False] * len(gt[cls])
            for conf, box in sorted(dets[cls], key=lambda t: -t[0]):
                best_iou, best_j = 0.0, -1
                for j, g in enumerate(gt[cls]):
                    if gt_used[j]:
                        continue
                    ix1, iy1 = max(box[0], g[0]), max(box[1], g[1])
                    ix2, iy2 = min(box[2], g[2]), min(box[3], g[3])
                    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                    area_a = (box[2] - box[0]) * (box[3] - box[1])
                    area_b = (g[2] - g[0]) * (g[3] - g[1])
                    union = area_a + area_b - inter
                    iou = inter / union if union > 0 else 0.0
                    if iou > best_iou:
                        best_iou, best_j = iou, j
                tp = best_iou >= IOU_MATCH and best_j >= 0
                if tp:
                    gt_used[best_j] = True
                per_cls[cls]["preds"].append((conf, img_path.name, tp))

    results = {}
    for cls in NAMES.values():
        preds = sorted(per_cls[cls]["preds"], key=lambda t: -t[0])
        flags = [tp for _, _, tp in preds]
        ap = ap_at_iou(flags, per_cls[cls]["n_gt"])
        results[cls] = {
            "n_gt": per_cls[cls]["n_gt"],
            "n_preds": len(preds),
            "ap50": None if np.isnan(ap) else round(ap, 3),
        }
    vals = [r["ap50"] for r in results.values() if r["ap50"] is not None]
    results["mAP50"] = round(float(np.mean(vals)), 3) if vals else None
    results["n_images"] = len(image_files)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate ONNX on the real val split")
    parser.add_argument("--onnx", required=True)
    parser.add_argument("--label", default="model")
    args = parser.parse_args()

    session = ort.InferenceSession(args.onnx, providers=["CPUExecutionProvider"])
    meta = session.get_modelmeta().custom_metadata_map.get("names")
    if meta:
        parsed = ast.literal_eval(meta)
        names = {int(k): v for k, v in parsed.items()}
        assert names == NAMES, f"unexpected class set: {names}"

    results = evaluate(session)
    print(f"\n══ {args.label}: {Path(args.onnx).name} ══")
    print(f"images: {results['n_images']}  conf>={CONF}  IoU match {IOU_MATCH}")
    for cls in NAMES.values():
        r = results[cls]
        ap = "n/a (no GT)" if r["ap50"] is None else f"{r['ap50']:.3f}"
        print(f"  {cls:8s} AP50={ap}  (GT boxes: {r['n_gt']}, predictions: {r['n_preds']})")
    print(f"  mAP50 = {results['mAP50']}")


if __name__ == "__main__":
    main()
