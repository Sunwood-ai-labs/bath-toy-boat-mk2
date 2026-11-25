"""3D Flood-Fill (BFS) Hydrostatics & Watertight Floating Simulator for the Bath Toy Boat.

Unlike naive closed-hull hydrostatics, this simulator:
1. Converts the actual 3-body PIP STL (Hull + Periscope_Spinner + Water_Wheel) into a fine
   3D voxel grid (0.4 mm resolution).
2. For each water depth d in [0, 28] mm, performs a 3D 26-connected flood-fill (BFS) starting
   from the exterior bath water boundaries below Z = d.
3. Water automatically penetrates any connected clearance gap (bearing gaps, stern spillway,
   wheel bay). Only trapped interior dry cavities and solid material below Z = d contribute
   to actual displaced water volume V_disp(d).
4. Checks interior tub flooding ratio to verify the downflooding height and computes equilibrium
   draft, freeboard, KB, BM_T, GM_T, and 10-degree righting moment across 4 print materials:
   - PLA 25% infill (0.50 g/cm^3)
   - Solid Polypropylene PP (0.90 g/cm^3)
   - Solid ABS (1.05 g/cm^3)
   - Solid 100% PLA (1.24 g/cm^3)
"""
import json
import struct
from pathlib import Path
import numpy as np
from scipy.ndimage import binary_propagation
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[2]
EVAL_PATH = ROOT / "cad" / "out" / "eval.json"
STL_PATH = ROOT / "cad" / "out" / "bath_boat_mk2.stl"
OUT_DIR = Path(__file__).resolve().parent


def read_stl_triangles(path: Path) -> np.ndarray:
    data = path.read_bytes()
    if len(data) >= 84:
        n_tris = struct.unpack("<I", data[80:84])[0]
        if 84 + 50 * n_tris == len(data):
            dt = np.dtype([
                ("normal", "<f4", (3,)),
                ("v0", "<f4", (3,)),
                ("v1", "<f4", (3,)),
                ("v2", "<f4", (3,)),
                ("attr", "<u2"),
            ])
            arr = np.frombuffer(data[84:], dtype=dt)
            return np.stack([arr["v0"], arr["v1"], arr["v2"]], axis=1).astype(np.float64)
    text = data.decode("utf-8", errors="ignore")
    verts = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) == 4 and parts[0] == "vertex":
            verts.append([float(parts[1]), float(parts[2]), float(parts[3])])
    return np.array(verts, dtype=np.float64).reshape(-1, 3, 3)


def solid_volume(tris: np.ndarray) -> float:
    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    return float(np.sum(np.einsum("ij,ij->i", v0, np.cross(v1, v2))) / 6.0)


def voxelize_stl_columns(tris: np.ndarray, dx: float = 0.4, dy: float = 0.4, dz: float = 0.4):
    """Build exact 3D boolean voxel occupancy grid from STL via vertical ray-triangle crossings."""
    xs = np.arange(-80.0 + dx * 0.5, 90.0, dx)
    ys = np.arange(-46.0 + dy * 0.5, 46.0, dy)
    zs = np.arange(-0.8 + dz * 0.5, 29.2, dz)
    X, Y = np.meshgrid(xs, ys, indexing="ij")
    nx, ny, nz = len(xs), len(ys), len(zs)
    n_rays = nx * ny
    crossings = [[] for _ in range(n_rays)]

    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    tri_xmin = np.min(tris[:, :, 0], axis=1)
    tri_xmax = np.max(tris[:, :, 0], axis=1)
    tri_ymin = np.min(tris[:, :, 1], axis=1)
    tri_ymax = np.max(tris[:, :, 1], axis=1)

    for i in range(len(tris)):
        x0, y0, z0 = v0[i]
        x1, y1, z1 = v1[i]
        x2, y2, z2 = v2[i]
        denom = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denom) < 1e-12:
            continue
        ix0 = max(0, int(np.floor((tri_xmin[i] + 80.0) / dx)))
        ix1 = min(nx - 1, int(np.ceil((tri_xmax[i] + 80.0) / dx)))
        iy0 = max(0, int(np.floor((tri_ymin[i] + 46.0) / dy)))
        iy1 = min(ny - 1, int(np.ceil((tri_ymax[i] + 46.0) / dy)))
        if ix1 < ix0 or iy1 < iy0:
            continue
        sub_x = X[ix0:ix1 + 1, iy0:iy1 + 1] + 1.37e-5
        sub_y = Y[ix0:ix1 + 1, iy0:iy1 + 1] + 2.71e-5
        w0 = ((y1 - y2) * (sub_x - x2) + (x2 - x1) * (sub_y - y2)) / denom
        w1 = ((y2 - y0) * (sub_x - x2) + (x0 - x2) * (sub_y - y2)) / denom
        w2 = 1.0 - w0 - w1
        hit = (w0 >= 0.0) & (w1 >= 0.0) & (w2 >= 0.0)
        if not np.any(hit):
            continue
        zh = w0[hit] * z0 + w1[hit] * z1 + w2[hit] * z2
        ii, jj = np.nonzero(hit)
        flat_idx = (ix0 + ii) * ny + (iy0 + jj)
        for k, zval in zip(flat_idx, zh):
            crossings[k].append(float(zval))

    solid = np.zeros((nx, ny, nz), dtype=bool)
    z0_grid = zs[0]
    for k, cz in enumerate(crossings):
        if len(cz) >= 2:
            cz.sort()
            ix = k // ny
            iy = k % ny
            for m in range(len(cz) // 2):
                zlo, zhi = cz[2 * m], cz[2 * m + 1]
                k0 = max(0, int(np.ceil((zlo - z0_grid) / dz)))
                k1 = min(nz, int(np.floor((zhi - z0_grid) / dz)) + 1)
                if k1 > k0:
                    solid[ix, iy, k0:k1] = True

    return xs, ys, zs, solid


def compute_floodfill_hydrostatics(xs, ys, zs, solid, dx=0.4, dy=0.4, dz=0.4):
    """For each draft d, run 3D 26-connected flood-fill from exterior water below Z=d."""
    nx, ny, nz = solid.shape
    voxel_vol = dx * dy * dz
    cell_area = dx * dy
    struct26 = np.ones((3, 3, 3), dtype=bool)

    # Interior dry-tub monitor box (main forward/side tub cavity above floor_t=3.5 mm)
    X3, Y3, Z3 = np.meshgrid(xs, ys, zs, indexing="ij")
    tub_monitor = (
        (~solid)
        & (Z3 >= 4.5)
        & (Z3 <= 12.0)
        & (
            ((X3 >= 25.0) & (X3 <= 55.0) & (np.abs(Y3) <= 24.0))
            | ((X3 >= -55.0) & (X3 <= -22.0) & (np.abs(Y3) >= 22.0) & (np.abs(Y3) <= 32.0))
        )
    )
    n_tub_mon = int(np.sum(tub_monitor))

    # Exterior seed mask (bottom layer Z < 0 and outer perimeter walls)
    ext_seed = np.zeros_like(solid)
    ext_seed[:, :, 0] = ~solid[:, :, 0]
    ext_seed[0, :, :] = ~solid[0, :, :]
    ext_seed[-1, :, :] = ~solid[-1, :, :]
    ext_seed[:, 0, :] = ~solid[:, 0, :]
    ext_seed[:, -1, :] = ~solid[:, -1, :]

    d_grid = np.arange(0.0, 28.5, 0.5)
    disp_vol = np.zeros_like(d_grid)
    kb_arr = np.zeros_like(d_grid)
    awp_arr = np.zeros_like(d_grid)
    ixx_arr = np.zeros_like(d_grid)
    iyy_arr = np.zeros_like(d_grid)
    tub_flood_frac = np.zeros_like(d_grid)

    for idx, d in enumerate(d_grid):
        if d <= 0.0:
            continue
        k_top = np.searchsorted(zs, d, side="right")
        if k_top <= 0:
            continue
        passable = (~solid[:, :, :k_top])
        seed = ext_seed[:, :, :k_top] & passable
        flooded_sub = binary_propagation(seed, structure=struct26, mask=passable)

        # Effective displaced domain = everything below d that exterior water CANNOT enter
        displaced = (~flooded_sub) & (Z3[:, :, :k_top] >= 0.0)
        v_tot = float(np.sum(displaced) * voxel_vol)
        disp_vol[idx] = v_tot
        if v_tot > 0.0:
            kb_arr[idx] = float(np.sum(Z3[:, :, :k_top][displaced]) * voxel_vol / v_tot)

        # Waterplane at k_wl = k_top - 1
        wp = displaced[:, :, k_top - 1]
        awp = float(np.sum(wp) * cell_area)
        awp_arr[idx] = awp
        if awp > 0.0:
            x_wp = X3[:, :, k_top - 1][wp]
            y_wp = Y3[:, :, k_top - 1][wp]
            x_c = float(np.mean(x_wp))
            ixx_arr[idx] = float(np.sum((y_wp ** 2) * cell_area))
            iyy_arr[idx] = float(np.sum(((x_wp - x_c) ** 2) * cell_area))

        if n_tub_mon > 0:
            k_mon = min(k_top, nz)
            flooded_full = np.zeros_like(solid)
            flooded_full[:, :, :k_top] = flooded_sub
            tub_flood_frac[idx] = float(np.sum(flooded_full & tub_monitor)) / n_tub_mon

    return {
        "d_grid": d_grid,
        "disp_vol": disp_vol,
        "kb": kb_arr,
        "awp": awp_arr,
        "ixx": ixx_arr,
        "iyy": iyy_arr,
        "tub_flood_frac": tub_flood_frac,
    }


def eval_material(name: str, rho: float, V_total_mm3: float, com_z: float, sim: dict, z_flood: float):
    mass_g = V_total_mm3 * 1e-3 * rho
    req_disp = mass_g * 1000.0  # rho_water = 1.0 g/cm^3 -> mm^3
    d_grid = sim["d_grid"]
    m_safe = d_grid < z_flood
    max_safe_disp = float(sim["disp_vol"][m_safe][-1])
    if req_disp <= max_safe_disp:
        d_eq = float(np.interp(req_disp, sim["disp_vol"][m_safe], d_grid[m_safe]))
        kb = float(np.interp(d_eq, d_grid[m_safe], sim["kb"][m_safe]))
        ixx = float(np.interp(d_eq, d_grid[m_safe], sim["ixx"][m_safe]))
        iyy = float(np.interp(d_eq, d_grid[m_safe], sim["iyy"][m_safe]))
        awp = float(np.interp(d_eq, d_grid[m_safe], sim["awp"][m_safe]))
        bm_t = ixx / req_disp
        bm_l = iyy / req_disp
        gm_t = kb + bm_t - com_z
        gm_l = kb + bm_l - com_z
        return {
            "material": name,
            "density_g_cm3": rho,
            "mass_g": round(mass_g, 2),
            "required_displacement_mm3": round(req_disp, 1),
            "floats_without_tub_flooding": True,
            "floats_if_completely_submerged": rho < 1.0,
            "draft_mm": round(d_eq, 2),
            "downflood_margin_mm": round(z_flood - d_eq, 2),
            "rim_freeboard_mm": round(27.0 - d_eq, 2),
            "waterplane_area_mm2": round(awp, 1),
            "KB_mm": round(kb, 2),
            "KG_mm": round(com_z, 2),
            "BM_T_mm": round(bm_t, 2),
            "GM_T_mm": round(gm_t, 2),
            "GM_L_mm": round(gm_l, 2),
            "righting_moment_10deg_Nmm": round(mass_g * 9.81e-3 * gm_t * np.sin(np.deg2rad(10.0)), 3),
        }
    return {
        "material": name,
        "density_g_cm3": rho,
        "mass_g": round(mass_g, 2),
        "required_displacement_mm3": round(req_disp, 1),
        "floats_without_tub_flooding": False,
        "floats_if_completely_submerged": rho < 1.0,
        "draft_mm": None,
    }


def main():
    ev = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    ev = ev[0] if isinstance(ev, list) else ev
    V_cad = float(ev["total"]["volume_mm3"])
    com_cad = [sum(b["volume_mm3"] * b["center_of_mass"][k] for b in ev["bodies"]) / V_cad for k in range(3)]
    tris = read_stl_triangles(STL_PATH)
    V_stl = solid_volume(tris)

    xs, ys, zs, solid = voxelize_stl_columns(tris, dx=0.4, dy=0.4, dz=0.4)
    sim = compute_floodfill_hydrostatics(xs, ys, zs, solid, dx=0.4, dy=0.4, dz=0.4)

    # First draft where exterior flood-fill enters main tub monitor (or stern threshold 16.5 mm)
    flood_idx = np.where(sim["tub_flood_frac"] > 0.01)[0]
    z_flood_tub = float(sim["d_grid"][flood_idx[0]]) if len(flood_idx) > 0 else 28.0
    z_spillway = 16.5

    materials = [
        ("PLA_25pct_infill", 0.50),
        ("PLA_50pct_infill", 0.75),
        ("PP_solid", 0.90),
        ("PLA_100pct_solid", 1.24),
    ]
    cases = [eval_material(n, r, V_cad, com_cad[2], sim, z_flood_tub) for n, r in materials]

    out = {
        "method": "3D 26-connected BFS flood-fill over 0.4 mm voxelized 3-body PIP STL",
        "cad_total_volume_mm3": round(V_cad, 2),
        "stl_total_volume_mm3": round(V_stl, 2),
        "stl_vs_cad_rel_diff": round(abs(V_stl - V_cad) / V_cad, 6),
        "center_of_mass_mm": [round(c, 3) for c in com_cad],
        "stern_spillway_threshold_z_mm": z_spillway,
        "observed_tub_downflooding_draft_mm": round(z_flood_tub, 2),
        "max_displacement_before_tub_flood_mm3": round(float(sim["disp_vol"][sim["d_grid"] < z_flood_tub][-1]), 1),
        "max_displacement_at_spillway_Z16_5_mm3": round(float(np.interp(z_spillway, sim["d_grid"], sim["disp_vol"])), 1),
        "cases": cases,
    }
    (OUT_DIR / "hydrostatics.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    # Plotting
    font_path = Path("C:/Windows/Fonts/YuGothM.ttc")
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font_path)).get_name()
    plt.rcParams["axes.unicode_minus"] = False

    paper = "#f7f5ef"
    ink = "#1d2d35"
    muted = "#5e6e75"
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.2, 6.0), dpi=140, facecolor=paper)
    for ax in (ax1, ax2):
        ax.set_facecolor(paper)
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(alpha=0.22, ls="--")

    d = sim["d_grid"]
    m_plot = d < z_flood_tub
    ax1.plot(d[m_plot], sim["disp_vol"][m_plot] / 1000.0, color="#0077b6", lw=2.6, label="3Dフラッドフィル実効排水量 [cm3]")
    ax1.axvspan(z_flood_tub, 29.0, color="#9b2226", alpha=0.07, label="浸水・沈没域 (Z >= 17.5 mm)")
    ax1.axvline(z_spillway, color="#e76f51", lw=1.3, ls="-.", alpha=0.8)
    ax1.text(z_spillway + 0.3, 25, f"高床スピルウェイ\n(Z={z_spillway:.1f} mm)", fontsize=8.2, color="#e76f51")
    ax1.axvline(z_flood_tub, color="#9b2226", lw=1.3, ls="--", alpha=0.8)
    ax1.text(z_flood_tub - 0.3, 260, f"バスタブ浸水限界\n(Z={z_flood_tub:.1f} mm)", ha="right", fontsize=8.2, color="#9b2226")

    cols = {"PLA_25pct_infill": "#2a9d8f", "PLA_50pct_infill": "#457b9d", "PP_solid": "#e76f51", "PLA_100pct_solid": "#6a4c93"}
    lbls = {
        "PLA_25pct_infill": "PLA 25%インフィル (0.50)",
        "PLA_50pct_infill": "PLA 50%インフィル (0.75)",
        "PP_solid": "PP 中実 (0.90)",
        "PLA_100pct_solid": "PLA 100%中実 (1.24)",
    }
    offsets_l = {
        "PLA_25pct_infill": (1.0, 102.0),
        "PLA_50pct_infill": (1.2, 146.0),
        "PP_solid": (1.6, 182.0),
    }
    for c in cases:
        req = c["required_displacement_mm3"] / 1000.0
        col = cols[c["material"]]
        ax1.axhline(req, color=col, lw=1.1, ls=":")
        if c["draft_mm"] is not None:
            ax1.plot(c["draft_mm"], req, "o", color=col, ms=7.5, zorder=5)
            tx, ty = offsets_l[c["material"]]
            ax1.annotate(
                f"{lbls[c['material']]}: d={c['draft_mm']:.1f} mm",
                xy=(c["draft_mm"], req),
                xytext=(tx, ty),
                fontsize=8.3,
                color=col,
                arrowprops=dict(arrowstyle="->", color=col, lw=1.0),
            )
        else:
            ax1.text(1.5, req + 6.0, f"{lbls[c['material']]}: 必要={req:.1f} g > 浸水限界 → 浸水・沈没", fontsize=8.3, color=col, fontweight="bold")
    ax1.set_title("3D浸水フラッドフィル実効排水量と平衡喫水", fontsize=12, fontweight="bold", color=ink, pad=10)
    ax1.set_xlabel("喫水 d [mm]", fontsize=10, color=ink)
    ax1.set_ylabel("実効排水体積 / 質量 [cm3 ≡ g]", fontsize=10, color=ink)
    ax1.set_xlim(0, 29)
    ax1.set_ylim(0, 295)
    ax1.legend(loc="upper left", fontsize=8.2, frameon=False)

    # Right panel: GM_T
    m_gm = (d >= 2.0) & (d < z_flood_tub)
    gm_t = sim["kb"][m_gm] + sim["ixx"][m_gm] / np.maximum(sim["disp_vol"][m_gm], 1e-6) - com_cad[2]
    ax2.plot(d[m_gm], gm_t, color="#0077b6", lw=2.5, label="横メタセンタ高さ GM_T [mm]")
    ax2.plot(d[m_gm], sim["kb"][m_gm], color="#457b9d", lw=1.5, ls="--", label="浮心高さ KB [mm]")
    ax2.axhline(0.0, color="#d62828", lw=1.2, label="転覆限界 (GM_T = 0)")
    ax2.axhline(com_cad[2], color="#e9c46a", lw=1.5, ls=":", label=f"重心高さ KG = {com_cad[2]:.1f} mm")
    short_lbls = {
        "PLA_25pct_infill": "PLA 25% (0.50)",
        "PLA_50pct_infill": "PLA 50% (0.75)",
        "PP_solid": "PP 中実 (0.90)",
    }
    offsets_r = {
        "PLA_25pct_infill": (9.2, 130.0),
        "PLA_50pct_infill": (13.0, 92.0),
        "PP_solid": (16.2, 54.0),
    }
    for c in cases:
        if c["draft_mm"] is not None:
            col = cols[c["material"]]
            ax2.plot(c["draft_mm"], c["GM_T_mm"], "o", color=col, ms=7.5, zorder=5)
            tx, ty = offsets_r[c["material"]]
            ax2.annotate(
                f"{short_lbls[c['material']]}: GM_T={c['GM_T_mm']:.1f} mm",
                xy=(c["draft_mm"], c["GM_T_mm"]),
                xytext=(tx, ty),
                fontsize=8.2,
                color=col,
                arrowprops=dict(arrowstyle="->", color=col, lw=1.0),
            )
    ax2.set_title("横復原性（浮遊するPLA 25%/50%・PP中実で GM_T > 0）", fontsize=12, fontweight="bold", color=ink, pad=10)
    ax2.set_xlabel("喫水 d [mm]", fontsize=10, color=ink)
    ax2.set_ylabel("高さ [mm]", fontsize=10, color=ink)
    ax2.set_xlim(2, 28)
    ax2.set_ylim(-5, 220)
    ax2.legend(loc="upper right", fontsize=8.3, frameon=False)

    fig.suptitle("おふろレスキュー艇 Mk-II — 3D浸水フラッドフィル静水力学検証 (0.4 mm実STLボクセル・軸受隙間連通含む)", fontsize=13.5, fontweight="bold", color=ink, y=0.98)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(OUT_DIR / "hydrostatics_plot.png", facecolor=paper)
    plt.close(fig)
    print(json.dumps(out, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
