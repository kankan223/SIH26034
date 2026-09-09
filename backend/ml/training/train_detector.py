"""Fine-tune YOLOv8n on the package/label dataset (Task 3.1.1).

Trains from the pretrained yolov8n.pt backbone on the synthetic labeled
package photos produced by generate_dataset.py, then:

1. Evaluates the best checkpoint on the val split (mAP50, precision, recall)
2. Sanity-checks live inference on a val image (both classes detected ≥0.5)
3. Exports ONNX (legacy TorchScript exporter + onnxslim + class-name
   metadata) and installs it as the runtime model:
       ml/models/package_label_detector.onnx

Usage (inside the backend container, which has ultralytics):
    python ml/training/train_detector.py            # defaults below
    python ml/training/train_detector.py --epochs 40 --imgsz 416

GPU is not required: yolov8n @ imgsz 416 on 260 images trains in ~1h on a
2-core CPU per prd.md §10.2 (CPU-only inference/deployment).
"""

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

REPO_BACKEND = Path(__file__).resolve().parent.parent.parent  # backend/
DEFAULT_DATA = Path(__file__).resolve().parent.parent / "data" / "package_label" / "dataset.yaml"
MODELS_DIR = REPO_BACKEND / "ml" / "models"


def main() -> None:
    parser = argparse.ArgumentParser(description="Fine-tune YOLOv8n package/label detector")
    parser.add_argument("--data", default=str(DEFAULT_DATA))
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--imgsz", type=int, default=416)
    parser.add_argument("--batch", type=int, default=8)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--base-weights", default=str(REPO_BACKEND / "yolov8n.pt"))
    args = parser.parse_args()

    model = YOLO(args.base_weights)

    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device,
        seed=args.seed,
        deterministic=True,
        # Small-dataset settings: light augmentation (the generator already
        # varies exposure/blur/rotation), early patience to avoid overfit.
        patience=12,
        hsv_h=0.008,
        hsv_s=0.35,
        hsv_v=0.35,
        degrees=4.0,
        translate=0.08,
        scale=0.35,
        fliplr=0.3,
        mosaic=0.6,
        erasing=0.0,
        val=True,
        plots=False,
        verbose=True,
    )

    # ── Validate the best checkpoint ────────────────────────────────────────
    best = YOLO(str(Path(results.save_dir) / "weights" / "best.pt"))
    metrics = best.val(data=args.data, imgsz=args.imgsz, device=args.device, verbose=False)
    map50 = float(metrics.box.map50)
    precision = float(metrics.box.mp)
    recall = float(metrics.box.mr)
    print("\n════════ Evaluation (val split) ════════")
    print(f"mAP50:      {map50:.3f}")
    print(f"Precision:  {precision:.3f}")
    print(f"Recall:     {recall:.3f}")

    # ── Live inference sanity check on a val image ─────────────────────────
    val_img = Path(args.data).parent / "images" / "val"
    sample = sorted(val_img.glob("*.jpg"))[0]
    det = best.predict(source=str(sample), imgsz=args.imgsz, conf=0.5, device=args.device, verbose=False)[0]
    names = det.names
    classes = {names[int(c)] for c in det.boxes.cls.tolist()}
    print(f"Sanity check on {sample.name}: classes detected = {classes or 'NONE'}")
    assert {"package", "label"} <= classes, (
        f"Fine-tuned detector failed sanity check: expected both 'package' "
        f"and 'label' at conf>=0.5 on {sample.name}, got {classes or 'NONE'}"
    )

    # ── Export to ONNX and install as the runtime model ────────────────────
    # Uses the legacy TorchScript exporter (dynamo=False): torch 2.14's
    # default dynamo exporter requires onnxscript versions incompatible with
    # the pinned numpy<2 runtime, and ultralytics' AutoUpdate otherwise
    # mutates the environment (numpy 2.x) breaking cv2/paddleocr.
    import onnx
    import torch

    dest = MODELS_DIR / "package_label_detector.onnx"
    dest.parent.mkdir(parents=True, exist_ok=True)
    net = best.model
    net.eval()
    dummy = torch.zeros(1, 3, args.imgsz, args.imgsz)
    with torch.no_grad():
        torch.onnx.export(
            net,
            dummy,
            str(dest),
            opset_version=12,
            input_names=["images"],
            output_names=["output0"],
            dynamo=False,
            do_constant_folding=True,
        )

    # Slim the graph, then embed class names so runtime loaders see
    # {0: package, 1: label} (metadata must be written after slimming).
    try:
        import onnxslim

        slimmed = onnxslim.slim(onnx.load(str(dest)))
    except Exception as e:  # pragma: no cover - onnxslim is optional
        print(f"onnxslim unavailable ({e}); shipping unslimmed graph")
        slimmed = onnx.load(str(dest))
    del slimmed.metadata_props[:]
    entry = slimmed.metadata_props.add()
    entry.key = "names"
    entry.value = str(net.names)
    onnx.save(slimmed, str(dest))
    print(f"\nRuntime model installed: {dest} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")

    # Acceptance criteria (prd.md §10.2 / FR-004)
    assert map50 >= 0.85, f"mAP50 {map50:.3f} below acceptance threshold 0.85"
    print("Acceptance criteria met: mAP50 >= 0.85 with both classes detected.")


if __name__ == "__main__":
    main()
