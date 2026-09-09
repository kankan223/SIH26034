"""Build the combined synthetic+real training dataset.

Layout produced (ml/data/combined/):
    images/train/  = synthetic train (260) + real train pool
    images/val/    = real val pool (strict-annotation) + synthetic val subsample
    labels/...     = matching YOLO annotation files
    dataset.yaml   (names: 0=package, 1=label)

The real val images come only from the strict annotation pool (see
annotate_real_photos.py), so real-split mAP is measured against the most
reliable auto-annotations. A seeded synthetic val subsample is mixed into
val purely to stabilize checkpoint selection.
"""

import argparse
import random
import shutil
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
SYN = BACKEND / "data" / "package_label"
REAL = BACKEND / "data" / "real"
OUT = BACKEND / "data" / "combined"


def copy_split(src_img_dir: Path, src_lbl_dir: Path, dst_img_dir: Path, dst_lbl_dir: Path, files=None) -> int:
    n = 0
    it = files if files is not None else list(src_img_dir.glob("*.jpg")) + list(src_img_dir.glob("*.png"))
    for img in it:
        lbl = src_lbl_dir / (img.stem + ".txt")
        if not lbl.is_file():
            continue
        shutil.copy2(img, dst_img_dir / img.name)
        shutil.copy2(lbl, dst_lbl_dir / lbl.name)
        n += 1
    return n


def main() -> None:
    parser = argparse.ArgumentParser(description="Build combined synthetic+real dataset")
    parser.add_argument("--syn-val-sample", type=int, default=20,
                        help="synthetic val images mixed into val for stable selection")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--strict-real-only", action="store_true",
                        help="train on only strict-pool real images (drops noisy low-conf annotations)")
    args = parser.parse_args()

    if OUT.exists():
        shutil.rmtree(OUT)
    for split in ("train", "val"):
        (OUT / "images" / split).mkdir(parents=True)
        (OUT / "labels" / split).mkdir(parents=True)

    import json

    strict_files = None
    if args.strict_real_only:
        report = json.loads((REAL / "annotate_report.json").read_text())
        strict_files = {
            e["file"] for e in report["images"]
            if isinstance(e, dict) and e.get("strict_pool")
        }

    n_syn_train = copy_split(SYN / "images" / "train", SYN / "labels" / "train",
                             OUT / "images" / "train", OUT / "labels" / "train")
    real_train_filter = strict_files
    n_real_train = copy_split(REAL / "images" / "train", REAL / "labels" / "train",
                              OUT / "images" / "train", OUT / "labels" / "train",
                              files=([p for p in (list((REAL / "images" / "train").glob("*.jpg"))
                                                    + list((REAL / "images" / "train").glob("*.png")))
                                      if p.name in strict_files] if real_train_filter else None))

    n_real_val = copy_split(REAL / "images" / "val", REAL / "labels" / "val",
                            OUT / "images" / "val", OUT / "labels" / "val")

    rng = random.Random(args.seed)
    syn_val_imgs = sorted((SYN / "images" / "val").glob("*.jpg"))
    sample = rng.sample(syn_val_imgs, min(args.syn_val_sample, len(syn_val_imgs)))
    n_syn_val = copy_split(SYN / "images" / "val", SYN / "labels" / "val",
                           OUT / "images" / "val", OUT / "labels" / "val", files=sample)

    (OUT / "dataset.yaml").write_text(
        f"path: {OUT}\n"
        "train: images/train\n"
        "val: images/val\n"
        "names:\n"
        "  0: package\n"
        "  1: label\n"
    )
    print(f"train: {n_syn_train} synthetic + {n_real_train} real = {n_syn_train + n_real_train}")
    print(f"val:   {n_real_val} real (strict) + {n_syn_val} synthetic = {n_real_val + n_syn_val}")
    print(f"dataset.yaml -> {OUT / 'dataset.yaml'}")


if __name__ == "__main__":
    main()
