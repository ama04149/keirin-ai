import random
import shutil
from pathlib import Path
import sys
from datetime import datetime

import numpy as np
import cv2
from PIL import Image, ExifTags

EXTS = {".jpg", ".jpeg", ".png", ".webp"}
EXIF_NAME_TO_ID = {v: k for k, v in ExifTags.TAGS.items()}


# ---------- 時刻取得 ----------
def get_taken_datetime(path: Path) -> datetime:
    """撮影日時（DateTimeOriginal優先）。無ければファイル更新時刻。"""
    try:
        with Image.open(path) as img:
            exif = img.getexif()
            if exif:
                dto_id = EXIF_NAME_TO_ID.get("DateTimeOriginal")
                dt_id = EXIF_NAME_TO_ID.get("DateTime")
                for key in (dto_id, dt_id):
                    if key and key in exif:
                        s = str(exif.get(key))
                        try:
                            return datetime.strptime(s, "%Y:%m:%d %H:%M:%S")
                        except Exception:
                            pass
    except Exception:
        pass
    return datetime.fromtimestamp(path.stat().st_mtime)


# ---------- 顔hash（軽量） ----------
def dhash_gray(img_gray: np.ndarray, hash_size: int = 8) -> int:
    """dHash（差分ハッシュ）: 8x8 => 64bit"""
    resized = cv2.resize(img_gray, (hash_size + 1, hash_size), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]
    bits = diff.flatten()
    h = 0
    for b in bits:
        h = (h << 1) | int(b)
    return h


def hamming(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def get_largest_face_hash(path: Path, face_cascade: cv2.CascadeClassifier) -> int | None:
    """
    画像から最大顔を検出し、その領域のdHashを返す。
    顔が取れなければ None。
    """
    try:
        pil = Image.open(path).convert("RGB")
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),  # 小さい顔も拾いたいなら (50,50) に
        )
        if len(faces) == 0:
            return None

        x, y, w, h = max(faces, key=lambda r: r[2] * r[3])
        face = gray[y : y + h, x : x + w]
        return dhash_gray(face, hash_size=8)
    except Exception:
        return None


# ---------- 候補の間引き（時系列の偏りを抑えて144枚を選ぶ） ----------
def downselect_to_144(files: list[Path], seed=None, chunk_size: int = 5) -> list[Path]:
    """
    144枚以上ある候補から、時系列の偏りが少ないように144枚に間引く。
    - 時系列ソート
    - chunk_size枚ごとの塊を作る
    - 各塊から1枚ずつ選ぶ（足りなければ追加で選ぶ）
    """
    if seed is not None:
        random.seed(str(seed))

    files = sorted(files, key=get_taken_datetime)
    chunks = [files[i:i + chunk_size] for i in range(0, len(files), chunk_size)]

    picked = []
    for c in chunks:
        if not c:
            continue
        picked.append(random.choice(c))
        if len(picked) >= 144:
            break

    if len(picked) < 144:
        rest = list(set(files) - set(picked))
        # 残りからランダム補充
        if len(rest) < (144 - len(picked)):
            # 念のため
            picked += rest
        else:
            picked += random.sample(rest, 144 - len(picked))

    return picked[:144]


# ---------- 時系列ブロック崩し（候補順生成） ----------
def make_time_blocks(paths, block_size: int, seed=None):
    if seed is not None:
        random.seed(str(seed))

    paths = sorted(paths, key=get_taken_datetime)
    blocks = [paths[i : i + block_size] for i in range(0, len(paths), block_size)]

    for b in blocks:
        random.shuffle(b)

    out = []
    idx = 0
    while True:
        progressed = False
        for b in blocks:
            if idx < len(b):
                out.append(b[idx])
                progressed = True
        if not progressed:
            break
        idx += 1
    return out


# ---------- 似顔連続回避（greedy） ----------
def reorder_avoid_similar_face(candidate_order, face_hash_map, min_hamming: int, seed=None):
    if seed is not None:
        random.seed(str(seed))

    pool = candidate_order[:]
    out = []
    last_hash = None
    thresholds = [min_hamming, max(min_hamming - 4, 0), max(min_hamming - 8, 0), 0]

    while pool:
        picked_idx = None
        for th in thresholds:
            for i, p in enumerate(pool):
                h = face_hash_map.get(p)
                # 顔が無い写真は「中立」扱いで通す
                if last_hash is None or h is None:
                    picked_idx = i
                    break
                if hamming(h, last_hash) >= th:
                    picked_idx = i
                    break
            if picked_idx is not None:
                break

        if picked_idx is None:
            picked_idx = 0

        chosen = pool.pop(picked_idx)
        out.append(chosen)

        ch = face_hash_map.get(chosen)
        if ch is not None:
            last_hash = ch

    return out


def main():
    if len(sys.argv) < 3:
        print("Usage: python shuffle_time_face.py <input_dir> <output_dir> [seed] [block_size] [min_hamming]")
        print("  block_size default=8 (おすすめ: 6〜12)")
        print("  min_hamming default=12 (おすすめ: 10〜14)")
        sys.exit(1)

    input_dir = Path(sys.argv[1])
    output_dir = Path(sys.argv[2])
    seed = sys.argv[3] if len(sys.argv) >= 4 else None
    block_size = int(sys.argv[4]) if len(sys.argv) >= 5 else 8
    min_hamming = int(sys.argv[5]) if len(sys.argv) >= 6 else 12

    if not input_dir.exists():
        raise FileNotFoundError(f"Input dir not found: {input_dir}")

    files = [p for p in input_dir.iterdir() if p.is_file() and p.suffix.lower() in EXTS]
    if len(files) < 144:
        raise ValueError(f"Need at least 144 images, but found {len(files)} in {input_dir}")

    # まず144枚に間引く（候補が多い場合）
    base_144 = files if len(files) == 144 else downselect_to_144(files, seed=seed, chunk_size=5)

    # 顔検出器ロード
    cascade_path = str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    face_cascade = cv2.CascadeClassifier(cascade_path)
    if face_cascade.empty():
        raise RuntimeError("Failed to load Haar cascade. Check your OpenCV installation.")

    # 顔hash前計算（144枚だけに対して実施＝速い）
    face_hash_map = {}
    for p in base_144:
        face_hash_map[p] = get_largest_face_hash(p, face_cascade)

    # 1) 時系列ブロック崩し
    candidate = make_time_blocks(base_144, block_size=block_size, seed=seed)

    # 2) 似顔連続回避
    final_order = reorder_avoid_similar_face(candidate, face_hash_map, min_hamming=min_hamming, seed=seed)

    # 出力（既存ファイルがあっても上書きできるように一旦掃除しない。名前が衝突しないので安全）
    output_dir.mkdir(parents=True, exist_ok=True)
    for i, src in enumerate(final_order[:144]):
        dst = output_dir / f"{i:03d}{src.suffix.lower()}"
        shutil.copy2(src, dst)

    print(f"Done. Selected & reordered 144 images -> {output_dir}")
    print(f"Input={len(files)} images, seed={seed}, block_size={block_size}, min_hamming={min_hamming}")


if __name__ == "__main__":
    main()
