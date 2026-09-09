# Package/Label Detector — Training Pipeline

Fine-tunes a **YOLOv8n** detector on labeled package photos so the runtime
detector matches the domain (FR-004/FR-005) instead of relying on pretrained
COCO weights or a mock stub. Runtime model:
`backend/ml/models/package_label_detector.onnx` (classes `0: package`,
`1: label`), loaded by `backend/app/services/cv_detection.py`.

## 1. Generate the labeled dataset

Synthetic "photos" of retail packages with printed principal display panels
(PDP labels), augmented with realistic camera variance (exposure, blur,
noise, tilt, cluttered backgrounds). Deterministic via `--seed`.

```bash
docker compose exec worker python /app/ml/training/generate_dataset.py \
    --train 260 --val 60 --seed 42
```

Output (YOLO format, gitignored under `backend/ml/data/`):

```
backend/ml/data/package_label/
├── images/{train,val}/*.jpg
├── labels/{train,val}/*.txt      # "class x_c y_c w h" normalized
└── dataset.yaml                  # names: 0=package, 1=label
```

## 2. Fine-tune YOLOv8n

```bash
docker compose exec worker python /app/ml/training/train_detector.py \
    --epochs 40 --imgsz 416 --batch 8
```

The script trains from the pretrained `yolov8n.pt` backbone (small-dataset
settings: patience=12, light augmentation), then:

1. Evaluates the best checkpoint on the val split — prints mAP50,
   precision, recall (acceptance: mAP50 ≥ 0.85)
2. Sanity-checks live inference: both `package` and `label` must be
   detected at conf ≥ 0.5 on a val image
3. Exports ONNX (opset 12 via the legacy TorchScript exporter, slimmed
   with onnxslim, class names embedded as metadata — no onnxscript /
   numpy-2.x dependency churn) and installs it at
   `ml/models/package_label_detector.onnx`

## 3. Runtime behavior

`backend/app/services/cv_detection.py` loads the ONNX via onnxruntime
(letterbox preprocessing, class-aware NMS, conf ≥ 0.5 per prd.md §10.4):

| Situation | `model_used` | Behavior |
|---|---|---|
| Fine-tuned ONNX loaded | `yolo_v8n_finetuned` | Real detections |
| Only Ultralytics available (dev) | `yolo_v8n` | Real detections |
| No model file | `contour_fallback` | Contour heuristic |

If nothing is detected (out-of-domain frame), the FR-004 fallback applies:
full-image box with `manual_crop_used=True` so the pipeline continues.

CPU latency: inference at the model's native 416px letterboxed input runs
well under the 300ms target (prd.md §10.2).

## 4. Retraining with real photos

To improve real-world accuracy, add genuine labeled photos:

1. Capture ≥ 100–200 photos of packages (varied lighting/angles/backgrounds)
2. Annotate with a YOLO-format tool (e.g. Label Studio, CVAT, Roboflow —
   one `.txt` per image, classes 0=package, 1=label)
3. Merge into `backend/ml/data/package_label/images|labels/{train,val}`
4. Re-run step 2

Model artifacts (`*.onnx`, `*.pt`, `*.joblib`) are gitignored; the training
pipeline is fully reproducible from source.
