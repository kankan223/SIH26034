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

Real photo workflow (open-licensed sources, no manual labeling required):

1. **Fetch** — pull real package photos from Wikimedia Commons with full
   attribution (licenses recorded per file for redistribution):

   ```bash
   docker compose exec worker python /app/ml/training/fetch_real_photos.py \
       --per-query 22 --max 165
   ```

   Output: `ml/data/real/raw/*.jpg` + `manifest.json` + `CREDITS.md`.
   Append-safe: re-runs add new files, never overwrite or lose credits.
   To use your own phone photos instead, drop them into
   `ml/data/real/raw/` (any filenames) and skip step 1.

2. **Auto-annotate** — YOLO-World zero-shot (concrete vocabulary:
   box/carton/bottle/can/...) cross-checked against the current fine-tuned
   detector; QC rejects blurry/monochrome/package-less frames; multi-package
   images supported; val pool restricted to strict-confidence or
   cross-model-agreed annotations:

   ```bash
   docker compose exec worker python /app/ml/training/annotate_real_photos.py
   ```

   Output: `ml/data/real/images|labels/{train,val}` (YOLO format),
   `annotate_report.json` (per-image decisions), `contact_sheet.jpg` (visual
   QC — review this sheet before training). Raw pool images are larger than
   the training crops; annotation boxes are stored in original-photo coords.

3. **Combine** — merge synthetic (260) + real train pools; val = real strict
   pool + a small synthetic subsample for stable checkpoint selection:

   ```bash
   docker compose exec worker python /app/ml/training/build_combined_dataset.py
   ```

4. **Train** on the combined set:

   ```bash
   docker compose exec worker python /app/ml/training/train_detector.py \
       --data /app/ml/data/combined/dataset.yaml --epochs 50 --imgsz 416 --batch 8
   ```

5. **Measure on the real split** (old vs new — standalone onnxruntime
   evaluator, no ultralytics AutoBackend dependency):

   ```bash
   docker compose exec worker python /app/ml/training/eval_real.py \
       --onnx ml/models/package_label_detector.onnx --label NEW
   ```

   Keep the new model only if real-split mAP50 improves on the previous
   number (the synthetic-only baseline scored **0.611 mAP50** on the real
   split — that is the domain gap being fixed).

6. **Alternative checkpoints** (intermediate retrain attempts kept for
   reference, not replacing the production ONNX):

   - `runs/detect/train/weights/best.pt`  — **retirement checkpoint**
     (synthetic-only; **production ONNX** installed at
     `ml/models/package_label_detector.onnx`)
   - `runs/detect/train2/weights/best.pt` — noisy self-training attempt
     (all 61 auto-labeled images), mAP50 0.741 on real split
   - `runs/detect/train3/weights/best.pt` — strict-pool self-training
     (23 images), mAP50 0.789 on real split

   The production ONNX at `ml/models/package_label_detector.onnx` always
   reflects the **best-evaluated checkpoint on the real split** — replace it
   only after `eval_real.py` shows an improvement, and install with the same
   legacy TorchScript exporter + onnxslim + metadata procedure used by
   `train_detector.py`.

Model artifacts (`*.onnx`, `*.pt`, `*.joblib`) are gitignored; the training
pipeline is fully reproducible from source. Note: `ml/data/real/` includes
CC/media-licensed photos — the fetched attribution lives in
`ml/data/real/CREDITS.md` (regenerated by the fetcher; not committed).
Real photos are **not committed** — only the scripts + credits/manifest
files live in git for reproducibility.
