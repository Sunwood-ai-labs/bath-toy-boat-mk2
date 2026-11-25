"""Naval-Architecture 3D Large-Angle Roll Stability (GZ Righting Arm Curve) Test for Bath Toy Boat Mk-II.

Computes exact 3D equilibrium waterline z_w(phi), center of buoyancy B(phi), righting arm GZ(phi),
and righting moment M_r(phi) across heel angles phi = 0..65 deg using 3D voxelized hull envelope
for the recommended PLA 25% infill weight (95.34 g -> required displacement 95,345 mm^3).
"""
import json
import struct
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_fill_holes

ROOT = Path(r"C:\Users\makim\.gemini\antigravity\scratch\bath-toy-boat-mk2")
STL_PATH = ROOT / "cad" / "out" / "bath_boat_mk2.stl"
OUT_DIR = ROOT / "cae" / "hydrostatics"


def load_solid_voxels(stl_path: Path, step: float = 1.5):
    """Build 3D watertight hull + dry-interior buoyancy point cloud at resolution `step` mm."""
    data = stl_path.read_bytes()
    dt = np.dtype([("n", "<f4", (3,)), ("v0", "<f4", (3,)), ("v1", "<f4", (3,)), ("v2", "<f4", (3,)), ("a", "<u2")])
    arr = np.frombuffer(data[84:], dtype=dt)
    tris = np.stack([arr["v0"], arr["v1"], arr["v2"]], axis=1).astype(np.float64)

    xs = np.arange(-78.0 + step * 0.5, 88.0, step)
    ys = np.arange(-45.0 + step * 0.5, 45.0, step)
    zs = np.arange(0.0 + step * 0.5, 61.0, step)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    nx, ny, nz = len(xs), len(ys), len(zs)
    crossings = [[] for _ in range(nx * ny)]

    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    txmin = tris[:, :, 0].min(axis=1)
    txmax = tris[:, :, 0].max(axis=1)
    tymin = tris[:, :, 1].min(axis=1)
    tymax = tris[:, :, 1].max(axis=1)

    for i in range(len(tris)):
        x0, y0, z0 = v0[i]
        x1, y1, z1 = v1[i]
        x2, y2, z2 = v2[i]
        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denom) < 1e-12:
            continue
        ix0 = max(0, int(np.floor((txmin[i] + 78.0) / step)))
        ix1 = min(nx - 1, int(np.ceil((txmax[i] + 78.0) / step)))
        iy0 = max(0, int(np.floor((tymin[i] + 45.0) / step)))
        iy1 = min(ny - 1, int(np.ceil((tymax[i] + 45.0) / step)))
        if ix1 < ix0 or iy1 < iy0:
            continue
        sx = X[ix0:ix1 + 1, iy0:iy1 + 1] + 1.37e-5
        sy = Y[ix0:ix1 + 1, iy0:iy1 + 1] + 2.71e-5
        w0 = ((y1 - y2) * (sx - x2) + (x2 - x1) * (sy - y2)) / denom
        w1 = ((y2 - y0) * (sx - x2) + (x0 - x2) * (sy - y2)) / denom
        w2 = 1.0 - w0 - w1
        hit = (w0 >= 0.0) & (w1 >= 0.0) & (w2 >= 0.0)
        if not np.any(hit):
            continue
        zh = w0[hit] * z0 + w1[hit] * z1 + w2[hit] * z2
        ii, jj = np.nonzero(hit)
        for k, zv in zip((ix0 + ii) * ny + (iy0 + jj), zh):
            crossings[k].append(float(zv))

    solid = np.zeros((nx, ny, nz), dtype=bool)
    for k, cz in enumerate(crossings):
        if len(cz) >= 2:
            cz.sort()
            ix, iy = k // ny, k % ny
            for m in range(len(cz) // 2):
                k0 = max(0, int(np.ceil((cz[2 * m] - zs[0]) / step)))
                k1 = min(nz, int(np.floor((cz[2 * m + 1] - zs[0]) / step)) + 1)
                if k1 > k0:
                    solid[ix, iy, k0:k1] = True

    # Fill watertight hull cavity below gunwale (Z <= 27 mm) per horizontal slice to get buoyant volume
    buoyant = solid.copy()
    for kz, zv in enumerate(zs):
        if zv <= 27.0:
            buoyant[:, :, kz] = binary_fill_holes(solid[:, :, kz])

    X3, Y3, Z3 = np.meshgrid(xs, ys, zs, indexing="ij")
    pts = np.column_stack([X3[buoyant], Y3[buoyant], Z3[buoyant]])
    return pts, step ** 3


def main():
    pts, dV = load_solid_voxels(STL_PATH, step=1.5)
    # PLA 25% infill mass = 95.34 g -> target displaced volume = 95,345 mm^3
    # Center of mass from CAD eval.json: [-7.724, 0.0, 17.478]
    mass_g = 95.34
    target_V = mass_g * 1000.0
    com = np.array([-7.724, 0.0, 17.478])

    angles = list(range(0, 70, 5))
    records = []
    for deg in angles:
        rad = np.deg2rad(deg)
        c, s = np.cos(rad), np.sin(rad)
        # Roll about X-axis: y' = y*cos - z*sin, z' = y*sin + z*cos
        # Positive roll dips starboard (y < 0? Let's rotate so +y dips down: z' = -y*sin + z*cos, y' = y*cos + z*sin)
        yp = pts[:, 1] * c + pts[:, 2] * s
        zp = -pts[:, 1] * s + pts[:, 2] * c
        yg = com[1] * c + com[2] * s
        zg = -com[1] * s + com[2] * c

        # Binary search equilibrium waterline z_w such that submerged volume == target_V
        lo, hi = float(zp.min()), float(zp.max())
        for _ in range(36):
            mid = 0.5 * (lo + hi)
            vol = float(np.sum(zp <= mid)) * dV
            if vol < target_V:
                lo = mid
            else:
                hi = mid
        zw = 0.5 * (lo + hi)
        sub = zp <= zw
        yb = float(np.mean(yp[sub]))
        zb = float(np.mean(zp[sub]))
        # Righting arm GZ: positive when buoyancy B is further to the dipped (+y) side than G
        gz = yb - yg
        righting_moment_Nmm = mass_g * 9.81e-3 * gz
        # Check gunwale immersion (starboard gunwale point at y=+42, z=27)
        gunwale_z = -42.0 * s + 27.0 * c
        records.append({
            "heel_deg": deg,
            "waterline_z_mm": round(zw, 2),
            "By_mm": round(yb, 2),
            "Bz_mm": round(zb, 2),
            "Gy_mm": round(yg, 2),
            "Gz_mm": round(zg, 2),
            "GZ_mm": round(gz, 2),
            "righting_moment_Nmm": round(righting_moment_Nmm, 3),
            "gunwale_freeboard_mm": round(gunwale_z - zw, 2),
        })

    max_rec = max(records, key=lambda r: r["GZ_mm"])
    # First angle where gunwale dips below waterline
    imm_angles = [r["heel_deg"] for r in records if r["gunwale_freeboard_mm"] <= 0]
    gunwale_imm_deg = imm_angles[0] if imm_angles else None
    summary = {
        "mass_g": mass_g,
        "center_of_mass_mm": com.tolist(),
        "max_GZ_mm": max_rec["GZ_mm"],
        "angle_of_max_GZ_deg": max_rec["heel_deg"],
        "max_righting_moment_Nmm": max_rec["righting_moment_Nmm"],
        "gunwale_immersion_deg": gunwale_imm_deg,
        "positive_stability_up_to_deg": max(r["heel_deg"] for r in records if r["GZ_mm"] > 0),
        "curve": records,
    }
    out_json = OUT_DIR / "gz_stability.json"
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "curve"}, indent=2, ensure_ascii=False))
    for r in records:
        print(f"  heel={r['heel_deg']:2d} deg | GZ={r['GZ_mm']:+6.2f} mm | M={r['righting_moment_Nmm']:+6.2f} N·mm | gunwale_fb={r['gunwale_freeboard_mm']:+5.1f} mm")


if __name__ == "__main__":
    main()
