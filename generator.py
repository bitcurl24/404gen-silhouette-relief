from __future__ import annotations

import hashlib
import io
import urllib.request
from dataclasses import dataclass

import numpy as np
from PIL import Image


@dataclass(frozen=True)
class ReliefFeatures:
    cells: list[tuple[int, int, float, str]]
    background: str
    accent: str
    density: float
    contrast: float
    seed_value: int


def _stable_int(value: str, seed: int) -> int:
    return int(hashlib.sha256(f"{value}:{seed}".encode()).hexdigest()[:12], 16)


def _hex(rgb: np.ndarray) -> str:
    r, g, b = [int(max(0, min(255, x))) for x in rgb]
    return f"0x{r:02x}{g:02x}{b:02x}"


def _download(url: str) -> Image.Image:
    req = urllib.request.Request(url, headers={"User-Agent": "404gen-silhouette-relief/1.0"})
    with urllib.request.urlopen(req, timeout=20) as response:
        return Image.open(io.BytesIO(response.read(8 * 1024 * 1024))).convert("RGB")


def _fallback(stem: str, seed: int) -> ReliefFeatures:
    base = _stable_int(stem, seed)
    cells = []
    for y in range(6):
        for x in range(6):
            v = _stable_int(f"{stem}:{x}:{y}", seed)
            if v % 10 < 5:
                color = f"0x{(v >> 16) & 255:02x}{(v >> 8) & 255:02x}{v & 255:02x}"
                cells.append((x, y, 0.35 + (v % 100) / 200, color))
    return ReliefFeatures(cells[:22], "0x30343b", "0xd8d4c8", 0.45, 0.25, base)


def extract_features(stem: str, image_url: str, seed: int) -> ReliefFeatures:
    try:
        image = _download(image_url)
    except Exception:
        return _fallback(stem, seed)

    small = image.resize((10, 10), Image.Resampling.BILINEAR)
    arr = np.asarray(small, dtype=np.float32)
    lum = (arr[:, :, 0] * 0.2126 + arr[:, :, 1] * 0.7152 + arr[:, :, 2] * 0.0722) / 255.0
    gy, gx = np.gradient(lum)
    salience = np.abs(gx) + np.abs(gy) + np.abs(lum - float(np.mean(lum))) * 0.7
    threshold = float(np.quantile(salience, 0.54 + min(0.12, float(np.std(lum)) * 0.35)))
    cells: list[tuple[int, int, float, str]] = []
    for y in range(10):
        for x in range(10):
            if salience[y, x] >= threshold:
                local = float(salience[y, x])
                height = 0.16 + min(0.76, local * (1.7 + float(np.std(lum)) * 1.2))
                cells.append((x, y, height, _hex(arr[y, x])))
    cells.sort(key=lambda item: item[2], reverse=True)
    flat = arr.reshape(-1, 3)
    return ReliefFeatures(
        cells=cells[:36],
        background=_hex(np.percentile(flat, 20, axis=0)),
        accent=_hex(np.percentile(flat, 82, axis=0)),
        density=min(1.0, len(cells) / 100.0),
        contrast=float(np.std(lum)),
        seed_value=_stable_int(stem, seed),
    )


def build_module(stem: str, image_url: str, seed: int) -> str:
    f = extract_features(stem, image_url, seed)
    cell_lines = []
    for x, y, height, color in f.cells:
        px = (x - 4) * 0.09
        py = (4 - y) * 0.09
        depth = 0.035 + height * 0.075
        scale = 0.040 + min(0.020, height * (0.016 + f.contrast * 0.020))
        cell_lines.append(
            f"  addCell({px:.4f}, {py:.4f}, {depth:.4f}, {scale:.4f}, {color});"
        )
    cells_js = "\n".join(cell_lines) or "  addCell(0, 0, 0.08, 0.12, 0xcccccc);"
    ring = 0.42 + f.density * 0.035
    return f"""export default function generate(THREE) {{
  const group = new THREE.Group();
  const backMat = new THREE.MeshStandardMaterial({{ color: {f.background}, roughness: 0.86, metalness: 0.01 }});
  const accentMat = new THREE.MeshStandardMaterial({{ color: {f.accent}, roughness: 0.55, metalness: 0.02 }});
  const panel = new THREE.Mesh(new THREE.BoxGeometry(0.88, 0.88, 0.025), backMat);
  panel.position.z = -0.055;
  group.add(panel);
  function addCell(x, y, z, s, color) {{
    const mat = new THREE.MeshStandardMaterial({{ color: color, roughness: 0.68, metalness: 0.01 }});
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(s, s, z), mat);
    mesh.position.set(x, y, z * 0.5 - 0.04);
    group.add(mesh);
  }}
{cells_js}
  const frameGeoH = new THREE.BoxGeometry(0.92, 0.025, 0.035);
  const frameGeoV = new THREE.BoxGeometry(0.025, 0.92, 0.035);
  for (let i = -1; i <= 1; i += 2) {{
    const h = new THREE.Mesh(frameGeoH, accentMat);
    h.position.y = i * {ring:.4f};
    group.add(h);
    const v = new THREE.Mesh(frameGeoV, accentMat);
    v.position.x = i * {ring:.4f};
    group.add(v);
  }}
  group.rotation.x = -0.18;
  return group;
}}
"""
