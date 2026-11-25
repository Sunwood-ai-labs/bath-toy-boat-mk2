"""FieldCraft 0.8.1 Free-Surface (Air-Water) Gravity Floating Simulation for the Bath Toy Boat.

Uses FieldCraft's VOF/Free-Surface LBM solver under Earth gravity [0, 0, -9.81] m/s^2
with bath water filling the exterior basin up to Z = 10.0 mm (equilibrium draft range)
while keeping the interior tub dry (gas). Extracts exact `fill`, `pressure`, and net upward
buoyancy force Fz [N] from results.bin (MCRSLT05), and plots cross-sectional proof.
"""
import json
import struct
import zipfile
import subprocess
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib import font_manager

FIELDCRAFT_CLI = Path(r"D:\Prj\mini4wd-cad-lab\runtime\fieldcraft-0.8.1\fieldcraft-0.8.1-windows-x64\fieldcraft-cli.exe")
ROOT = Path(__file__).resolve().parents[2]
MESH_3MF = ROOT / "cad" / "handoff" / "hull.3mf"
OUT_DIR = Path(__file__).resolve().parent


class BinReader:
    def __init__(self, b: bytes):
        self.b = memoryview(b)
        self.p = 0

    def raw(self, n: int):
        assert 0 <= n <= len(self.b) - self.p, (self.p, n, len(self.b))
        out = self.b[self.p:self.p + n]
        self.p += n
        return out

    def num(self, t: str):
        return struct.unpack("<" + t, self.raw(struct.calcsize("<" + t)))[0]

    def text(self) -> str:
        return self.raw(self.num("Q")).tobytes().decode("utf-8")

    def field(self, fn, default=None):
        present = self.num("B")
        assert present in (0, 1)
        return fn() if present else default

    def option(self, fn):
        present = self.num("B")
        assert present in (0, 1)
        return fn() if present else None

    def arr(self, dtype, cols: int = 1):
        n = self.num("Q")
        assert n <= 100_000_000
        a = np.frombuffer(self.raw(n * np.dtype(dtype).itemsize * cols), dtype=dtype)
        return a.reshape(n, cols) if cols > 1 else a


def decode_free_surface(fc_path: Path):
    with zipfile.ZipFile(fc_path) as z:
        b = z.read("results.bin")
        model = json.loads(z.read("model.json"))
    r = BinReader(b)
    assert r.raw(8) == b"MCRSLT05"
    assert r.num("I") == 1
    name = r.text()
    r.raw(32)
    assert r.num("B") == 4
    payload = r.raw(r.num("Q"))
    assert r.p == len(b)

    r = BinReader(payload)

    def props():
        density = r.field(lambda: r.num("d"))
        heat = r.field(lambda: r.option(lambda: r.num("d")))
        return dict(density=density, specific_heat=heat)

    r.field(lambda: r.option(props))
    step = r.field(r.text)
    assert name == step

    def grid():
        return dict(
            origin=r.field(lambda: [r.num("d") for _ in range(3)]),
            spacing=r.field(lambda: r.num("d")),
            cells=r.field(lambda: [r.num("Q") for _ in range(3)]),
        )

    g = r.field(grid)
    n = int(np.prod(g["cells"]))
    solid = r.field(lambda: r.arr("u1"))
    r.field(lambda: [r.num("B") for _ in range(6)])

    def frame():
        t = r.field(lambda: r.num("d"))
        s = r.field(lambda: r.num("Q"))
        vel = r.field(lambda: r.arr("<f4", 3))
        pres = r.field(lambda: r.arr("<f4"))
        temp = r.field(lambda: r.arr("<f4"))
        fill = r.field(lambda: r.arr("<f4"))
        mass = r.field(lambda: r.num("d"))
        assert len(vel) == len(pres) == n
        return dict(time=float(t), step=int(s), velocity=vel, pressure=pres, fill=fill, mass=float(mass))

    frames = r.field(lambda: [frame() for _ in range(r.num("Q"))])
    times = r.field(lambda: r.arr("<f8"))

    def force():
        fname = r.field(r.text)
        body = r.field(lambda: r.option(r.text))
        vals = r.field(lambda: r.arr("<f8", 3))
        return dict(name=fname, body=body, values=vals)

    forces = r.field(lambda: [force() for _ in range(r.num("Q"))])
    return dict(grid=g, solid=solid, frames=frames, times=times, forces=forces, model=model)


def main():
    fc_path = OUT_DIR / "boat_float_free_surface.fieldcraft"
    # Bath basin from [-96, -56, -12] to [96, 56, 32], spacing = 2.0 mm (96x56x22 = 118,272 cells)
    # Start water strictly OUTSIDE hull bounding box [-74..74, -41..41, 0..11.5]
    # so corner voids fill naturally to ~10.0 mm equilibrium waterline
    water_d = 11.5
    liquid_boxes = [
        {"min": [-100, -58, -12], "max": [108, 58, 0.0]},
        {"min": [-100, -58, 0.0], "max": [-78, 58, water_d]},
        {"min": [88, -58, 0.0], "max": [108, 58, water_d]},
        {"min": [-78, -58, 0.0], "max": [88, -44, water_d]},
        {"min": [-78, 44, 0.0], "max": [88, 58, water_d]},
    ]
    script = [
        {"command": "model.units", "params": {"system": "mm-t-s-N-MPa"}},
        {"command": "geometry.import.mesh", "params": {"path": MESH_3MF.as_posix()}},
        {
            "command": "model.material.create",
            "params": {
                "name": "BathWater",
                "density": 1.0e-9,
                "fluid": {"type": "newtonian", "viscosity": 1.0e-6},
            },
        },
        {
            "command": "model.fluid_domain.create",
            "params": {
                "name": "BathBasin",
                "material": "BathWater",
                "min": [-100, -58, -12],
                "max": [108, 58, 32],
                "spacing": 2.0,
                "obstacles": ["Hull"],
                "acceleration": [0.0, 0.0, -9810.0],
                "free_surface": {"liquid": liquid_boxes},
            },
        },
        {
            "command": "model.step.create",
            "params": {
                "name": "FloatCheck",
                "procedure": {
                    "type": "fluid",
                    "domain": "BathBasin",
                    "collision": "hrr",
                    "steps": 1200,
                    "frames": 24,
                },
            },
        },
        {"command": "solve.fluid", "params": {"step": "FloatCheck", "backend": "cpu", "threads": 4}},
        {"command": "file.save_as", "params": {"path": fc_path.as_posix(), "results": True}},
    ]
    spath = OUT_DIR / "script_float_sim.json"
    spath.write_text(json.dumps(script, indent=1), encoding="utf-8")
    r = subprocess.run([str(FIELDCRAFT_CLI), "run", str(spath)], capture_output=True, text=True, timeout=300)
    (OUT_DIR / "stdout_float.txt").write_text(r.stdout, encoding="utf-8")
    (OUT_DIR / "stderr_float.txt").write_text(r.stderr, encoding="utf-8")
    print(f"[FloatSim] exit={r.returncode} stderr={r.stderr.strip()[:300]}")
    if r.returncode != 0:
        raise RuntimeError(f"FloatSim failed: {r.stderr}")

    d = decode_free_surface(fc_path)
    g = d["grid"]
    nx, ny, nz = g["cells"]
    dx_m = float(g["spacing"])
    dx_mm = dx_m * 1000.0
    cell_area_m2 = dx_m ** 2
    o_mm = np.array(g["origin"]) * 1000.0
    shape = (nz, ny, nx)
    solid3 = d["solid"].reshape(shape) > 0

    def compute_gauge_buoyancy_N(pres_arr, fill_arr):
        up_mask = solid3[1:, :, :] & (~solid3[:-1, :, :]) & (fill_arr[:-1, :, :] > 0.5)
        dn_mask = solid3[:-1, :, :] & (~solid3[1:, :, :]) & (fill_arr[1:, :, :] > 0.5)
        f_up = float(np.sum(pres_arr[:-1, :, :][up_mask]) * cell_area_m2)
        f_dn = float(np.sum(pres_arr[1:, :, :][dn_mask]) * cell_area_m2)
        return f_up - f_dn

    frame_times_ms = []
    fz_gauge_series = []
    for fr in d["frames"]:
        f3 = fr["fill"].reshape(shape)
        p3 = fr["pressure"].reshape(shape)
        frame_times_ms.append(fr["time"] * 1000.0)
        fz_gauge_series.append(compute_gauge_buoyancy_N(p3, f3))
    fz_gauge_series = np.array(fz_gauge_series, dtype=float)
    frame_times_ms = np.array(frame_times_ms, dtype=float)

    last = d["frames"][-1]
    fill3 = last["fill"].reshape(shape)
    pres3 = last["pressure"].reshape(shape)

    fz_final_N = float(fz_gauge_series[-1])
    fz_tail_N = float(np.mean(fz_gauge_series[-5:]))

    # Check interior tub dryness (Z in [5..24] mm, X in [24..56], |Y| <= 24)
    xs = o_mm[0] + (np.arange(nx) + 0.5) * dx_mm
    ys = o_mm[1] + (np.arange(ny) + 0.5) * dx_mm
    zs = o_mm[2] + (np.arange(nz) + 0.5) * dx_mm
    Z3, Y3, X3 = np.meshgrid(zs, ys, xs, indexing="ij")
    tub_mask = (~solid3) & (Z3 >= 5.0) & (Z3 <= 24.0) & (X3 >= 36.0) & (X3 <= 66.0) & (np.abs(Y3) <= 18.0)
    tub_max_fill = float(fill3[tub_mask].max()) if np.any(tub_mask) else 0.0
    tub_mean_fill = float(fill3[tub_mask].mean()) if np.any(tub_mask) else 0.0

    # Check stern bay dryness (Z in [17.5..26], X in [-60..-36], |Y| <= 13)
    bay_mask = (~solid3) & (Z3 >= 18.0) & (Z3 <= 26.0) & (X3 >= -62.0) & (X3 <= -38.0) & (np.abs(Y3) <= 13.0)
    bay_max_fill = float(fill3[bay_mask].max()) if np.any(bay_mask) else 0.0

    # Check exterior hydrostatic pressure gradient dp/dz in bath water (X <= -80 mm, fill > 0.99)
    ext_col_mask = (~solid3) & (X3 <= -84.0) & (np.abs(Y3) <= 10.0) & (fill3 > 0.99)
    z_col = Z3[ext_col_mask] / 1000.0
    p_col = pres3[ext_col_mask]
    dp_dz_measured = float(-np.polyfit(z_col, p_col, 1)[0]) if len(z_col) >= 10 else 0.0

    # Measure settled exterior water level by integrating fill vertically at X <= -80 mm, |Y| <= 10 mm
    ext_xy = (X3[0] <= -80.0) & (np.abs(Y3[0]) <= 10.0)
    water_z_meas = float(o_mm[2] + np.mean(np.sum(fill3[:, ext_xy], axis=0)) * dx_mm)

    # Actual CAD v4 material weights (V_cad = 174,353.92 mm^3 = 174.354 cm^3)
    w_pla25_N = 87.18e-3 * 9.81
    w_pla50_N = 130.77e-3 * 9.81
    w_pla100_N = 216.20e-3 * 9.81

    summary = {
        "initial_outer_water_z_mm": water_d,
        "settled_water_surface_z_mm": round(water_z_meas, 2),
        "gravity_mm_s2": -9810.0,
        "gravity_m_s2": -9.81,
        "grid_cells": [int(nx), int(ny), int(nz)],
        "steps": last["step"],
        "num_frames": len(d["frames"]),
        "final_time_s": round(last["time"], 6),
        "theoretical_dp_dz_Pa_per_m": 9810.0,
        "measured_hydrostatic_dp_dz_Pa_per_m": round(dp_dz_measured, 1),
        "final_gauge_buoyancy_Fz_N": round(fz_final_N, 4),
        "mean_last5_frames_buoyancy_Fz_N": round(fz_tail_N, 4),
        "supported_mass_equivalent_g": round(fz_tail_N / 9.81 * 1000.0, 2),
        "pla_25pct_weight_N": round(w_pla25_N, 4),
        "pla_50pct_weight_N": round(w_pla50_N, 4),
        "pla_100pct_weight_N": round(w_pla100_N, 4),
        "tub_interior_max_fill": round(tub_max_fill, 6),
        "tub_interior_mean_fill": round(tub_mean_fill, 6),
        "stern_bay_max_fill": round(bay_max_fill, 6),
    }
    (OUT_DIR / "float_sim_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    # Plot free-surface and hydrostatic pressure slices
    font_path = Path("C:/Windows/Fonts/YuGothM.ttc")
    if font_path.exists():
        font_manager.fontManager.addfont(str(font_path))
        plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font_path)).get_name()
    plt.rcParams["axes.unicode_minus"] = False

    paper = "#f7f5ef"
    ink = "#1d2d35"
    muted = "#5e6e75"
    cmap_fill = LinearSegmentedColormap.from_list("water", ["#f1efe6", "#8ecae6", "#219ebc", "#023047"])
    cmap_fill.set_bad("#d8572a")

    fig = plt.figure(figsize=(15.0, 8.0), dpi=135, facecolor=paper)
    fig.text(0.04, 0.945, "FIELDCRAFT 0.8.1 自由表面 LBM 浮力・浸水シミュレーション (重力 g = 9.81 m/s2)", fontsize=14.5, fontweight="bold", color=ink)
    fig.text(0.04, 0.905, f"平衡水面 Z = {water_z_meas:.1f} mm  |  ゲージ静水圧積分の浮力 Fz = +{fz_tail_N:.3f} N ({summary['supported_mass_equivalent_g']:.1f} gf相当)  |  実測 dp/dz = {dp_dz_measured:.0f} Pa/m  |  船内浸水 = {tub_max_fill:.4f}", fontsize=10.2, color=muted)

    k_y0 = int(np.clip(round((0.0 - o_mm[1]) / dx_mm - 0.5), 0, ny - 1))
    k_x12 = int(np.clip(round((12.0 - o_mm[0]) / dx_mm - 0.5), 0, nx - 1))

    # Left: Y=0 centerline water fill slice
    ax1 = fig.add_axes([0.05, 0.50, 0.44, 0.34])
    ext_xz = [o_mm[0], o_mm[0] + nx * dx_mm, o_mm[2], o_mm[2] + nz * dx_mm]
    im1 = ax1.imshow(np.ma.array(fill3[:, k_y0, :], mask=solid3[:, k_y0, :]), origin="lower", extent=ext_xz, cmap=cmap_fill, norm=Normalize(0, 1), aspect="auto")
    ax1.axhline(water_z_meas, color="#023047", ls="--", lw=1.0, alpha=0.7)
    ax1.set_title("縦断面 Y = 0 mm：液相充填率 (青=お湯 / 白=乾いた空気 / 橙=船体)", fontsize=10.5, color=ink, loc="left")
    ax1.set_xlabel("X [mm]", fontsize=9, color=muted)
    ax1.set_ylabel("Z [mm]", fontsize=9, color=muted)
    ax1.tick_params(labelsize=8, colors=muted)
    ax1.spines[["top", "right"]].set_visible(False)

    # Right: X=12 cross section (standpipe + dry tub)
    ax2 = fig.add_axes([0.55, 0.50, 0.40, 0.34])
    ext_yz = [o_mm[1], o_mm[1] + ny * dx_mm, o_mm[2], o_mm[2] + nz * dx_mm]
    ax2.imshow(np.ma.array(fill3[:, :, k_x12], mask=solid3[:, :, k_x12]), origin="lower", extent=ext_yz, cmap=cmap_fill, norm=Normalize(0, 1), aspect="auto")
    ax2.axhline(water_z_meas, color="#023047", ls="--", lw=1.0, alpha=0.7)
    ax2.set_title("横断面 X = +12 mm (スタンドパイプ部)：船内乾燥の証明", fontsize=10.5, color=ink, loc="left")
    ax2.set_xlabel("Y [mm]", fontsize=9, color=muted)
    ax2.set_ylabel("Z [mm]", fontsize=9, color=muted)
    ax2.tick_params(labelsize=8, colors=muted)
    ax2.spines[["top", "right"]].set_visible(False)

    # Bottom left: Hydrostatic pressure under hull at Y=0
    ax3 = fig.add_axes([0.05, 0.13, 0.44, 0.28])
    p_y0 = pres3[:, k_y0, :]
    p_show = np.ma.array(p_y0, mask=solid3[:, k_y0, :] | (fill3[:, k_y0, :] < 0.1))
    im3 = ax3.imshow(p_show, origin="lower", extent=ext_xz, cmap="YlGnBu", norm=Normalize(0, max(float(p_show.max()), 1.0)), aspect="auto")
    ax3.set_title("縦断面 Y = 0 mm：お湯の静水圧分布 [Pa] (船底を上向きに押す圧力)", fontsize=10.5, color=ink, loc="left")
    ax3.set_xlabel("X [mm]", fontsize=9, color=muted)
    ax3.set_ylabel("Z [mm]", fontsize=9, color=muted)
    ax3.tick_params(labelsize=8, colors=muted)
    ax3.spines[["top", "right"]].set_visible(False)
    cb3 = fig.colorbar(im3, cax=fig.add_axes([0.05, 0.055, 0.44, 0.015]), orientation="horizontal")
    cb3.set_label("静水圧 [Pa] (大気圧差ゲージ圧)", fontsize=8.5, color=muted)

    # Bottom right: Buoyancy Fz time history + weight comparison
    ax4 = fig.add_axes([0.57, 0.13, 0.38, 0.28])
    ax4.set_facecolor(paper)
    ax4.spines[["top", "right"]].set_visible(False)
    ax4.plot(frame_times_ms, fz_gauge_series, "-o", ms=3.5, color="#0077b6", lw=2.0, label="ゲージ静水圧積分 浮力 Fz [N]")
    ax4.axhline(w_pla25_N, color="#2a9d8f", ls="--", lw=1.4, label=f"PLA 25%インフィル 自重 ({w_pla25_N:.3f} N / 87.2 g)")
    ax4.axhline(w_pla50_N, color="#457b9d", ls="-.", lw=1.3, label=f"PLA 50%インフィル 自重 ({w_pla50_N:.3f} N / 130.8 g)")
    ax4.axhline(w_pla100_N, color="#6a4c93", ls=":", lw=1.4, label=f"PLA 100%中実 自重 ({w_pla100_N:.3f} N / 216.2 g)")
    y_top = max(float(np.max(fz_gauge_series)), w_pla100_N) * 1.65
    ax4.set_ylim(0.0, y_top)
    ax4.set_title(f"平衡喫水 Z={water_z_meas:.1f} mm 保持時の上向き浮力 Fz 推移と自重比較", fontsize=10.5, fontweight="bold", color=ink, loc="left")
    ax4.set_xlabel("時刻 t [ms]", fontsize=9, color=muted)
    ax4.set_ylabel("鉛直浮力 / 重力 [N]", fontsize=9, color=muted)
    ax4.tick_params(labelsize=8, colors=muted)
    ax4.grid(alpha=0.2, ls="--")
    ax4.legend(fontsize=7.8, frameon=False, loc="upper right", ncol=1)

    fig.savefig(OUT_DIR / "float_sim_plot.png", facecolor=paper)
    plt.close(fig)
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
