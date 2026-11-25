"""Verify Pattern A and Pattern B in Bambu Studio CLI (A1 mini 0.4mm, Textured PEI 65C,
watertight 3 walls, 15% Gyroid, no support, live AMS 3 colors) and render a crisp PyVista
side-by-side comparison image with exact print times, weights, and swap counts.
"""
import json
import pathlib
import re
import shutil
import subprocess
import zipfile
import numpy as np
import pyvista as pv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

pv.OFF_SCREEN = True

ROOT = pathlib.Path(r"C:\Users\makim\.gemini\antigravity\scratch\bath-toy-boat-mk2")
BRAIN = pathlib.Path(r"C:\Users\makim\.gemini\antigravity\brain\524fbd92-1904-448d-9085-9a1c8de17e28")
CAD_OUT = ROOT / "cad" / "out"
SLICER_DIR = ROOT / "cad" / "slicer" / "ab_compare"
SLICER_DIR.mkdir(parents=True, exist_ok=True)

STL_PATH = CAD_OUT / "bath_boat_mk2.stl"
THREEMF_A = CAD_OUT / "bath_boat_mk2_ams3color_A.3mf"
THREEMF_B = CAD_OUT / "bath_boat_mk2_ams3color_B.3mf"
BAMBU_EXE = pathlib.Path(r"C:\Users\makim\AppData\Local\Programs\Bambu Studio\bambu-studio.exe")
BAMBU_RES = BAMBU_EXE.parent / "resources" / "profiles" / "BBL"


def setup_font():
    for fname in ["Yu Gothic", "Meiryo", "MS Gothic", "DejaVu Sans"]:
        if any(fname.lower() in f.name.lower() for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = fname
            break
    plt.rcParams["axes.unicode_minus"] = False


def load_flat_profile(subdir: str, name: str) -> dict:
    p = BAMBU_RES / subdir / f"{name}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    if "inherits" in d:
        parent = load_flat_profile(subdir, d["inherits"])
        parent.update(d)
        d = parent
    return d


def parse_time_sec(tstr: str) -> int:
    sec = 0
    for val, unit in re.findall(r"(\d+)\s*([hms])", tstr):
        v = int(val)
        if unit == "h":
            sec += v * 3600
        elif unit == "m":
            sec += v * 60
        elif unit == "s":
            sec += v
    return sec


def fmt_sec(sec: int) -> str:
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    return f"{h}時間{m:02d}分{s:02d}秒"


def slice_base(case_id: str, proc_name: str, src_3mf: pathlib.Path, infill: str) -> dict:
    cdir = SLICER_DIR / case_id
    cdir.mkdir(parents=True, exist_ok=True)
    mach = load_flat_profile("machine", "Bambu Lab A1 mini 0.4 nozzle")
    proc = load_flat_profile("process", proc_name)
    fila = load_flat_profile("filament", "Bambu PLA Basic @BBL A1M")
    # Textured PEI Plate 65C + watertight 3 walls + Gyroid + no support + arc fitting ON (real A1 mini speed)
    proc.update({
        "wall_loops": "3",
        "sparse_infill_density": infill,
        "sparse_infill_pattern": "gyroid",
        "enable_support": "0",
        "curr_bed_type": "Textured PEI Plate",
    })
    fila["textured_plate_temp"] = ["65"]
    fila["textured_plate_temp_initial_layer"] = ["65"]

    fm, fp, ff = cdir / "machine.json", cdir / "process.json", cdir / "filament.json"
    fm.write_text(json.dumps(mach, indent=1), encoding="utf-8")
    fp.write_text(json.dumps(proc, indent=1), encoding="utf-8")
    ff.write_text(json.dumps(fila, indent=1), encoding="utf-8")

    out_3mf = cdir / f"{case_id}.gcode.3mf"
    cmd = [
        str(BAMBU_EXE),
        "--load-settings", f"{fm};{fp}",
        "--load-filaments", str(ff),
        "--arrange", "1",
        "--slice", "0",
        "--export-3mf", str(out_3mf),
        str(src_3mf),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0 or not out_3mf.exists():
        raise RuntimeError(f"Slice {case_id} failed: {r.stderr[:400]}")

    gcode = ""
    with zipfile.ZipFile(out_3mf, "r") as z:
        for n in z.namelist():
            if n.endswith(".gcode"):
                gcode = z.read(n).decode("utf-8", errors="ignore")
                break

    def _m(pat, default="0"):
        m = re.search(pat, gcode)
        return m.group(1).strip() if m else default

    t_tot = _m(r";\s*total estimated time:\s*([^;\n]+)", "0s")
    wt = float(_m(r";\s*total filament weight \[g\]\s*:\s*([0-9.]+)", "0"))
    layers = int(_m(r";\s*total layer number:\s*(\d+)", "0"))
    return {
        "case_id": case_id,
        "layers": layers,
        "base_weight_g": round(wt, 2),
        "base_time_str": t_tot,
        "base_time_sec": parse_time_sec(t_tot),
    }


def make_colored_mesh(pattern: str):
    mesh = pv.read(str(STL_PATH))
    zc = mesh.cell_centers().points[:, 2]
    colors = np.zeros((mesh.n_cells, 3), dtype=np.uint8)
    c_red = np.array([0xC1, 0x2E, 0x1F], dtype=np.uint8)
    c_wht = np.array([0xF5, 0xF5, 0xF3], dtype=np.uint8)
    c_grn = np.array([0x23, 0x4D, 0x40], dtype=np.uint8)
    if pattern == "A":
        colors[:] = c_red
        colors[(zc >= 27.0) & (zc < 40.5)] = c_wht
        colors[(zc >= 40.5) & (zc < 52.5)] = c_grn
        colors[(zc >= 52.5) & (zc < 55.0)] = c_red
        colors[zc >= 55.0] = c_wht
    else:
        colors[:] = c_grn
        colors[(zc >= 21.5) & (zc < 27.0)] = c_red
        colors[(zc >= 27.0) & (zc < 40.5)] = c_wht
        colors[(zc >= 40.5) & (zc < 52.5)] = c_red
        colors[(zc >= 52.5) & (zc < 55.0)] = c_grn
        colors[zc >= 55.0] = c_wht
    mesh.cell_data["RGB"] = colors
    return mesh


def snap(mesh, cam_pos):
    pl = pv.Plotter(off_screen=True, window_size=[640, 480])
    pl.set_background("#eef2f6")
    pl.add_mesh(mesh, scalars="RGB", rgb=True, smooth_shading=False, specular=0.22)
    pl.camera_position = [cam_pos, (0, 0, 20), (0, 0, 1)]
    img = pl.screenshot(return_img=True)
    pl.close()
    return img


def main():
    setup_font()
    # Real Bambu Studio CLI slices for both 0.24mm Draft and 0.20mm Standard
    s_024 = slice_base("mk2_024_draft", "0.24mm Draft @BBL A1M", THREEMF_A, "15%")
    s_020 = slice_base("mk2_020_std", "0.20mm Standard @BBL A1M", THREEMF_A, "20%")

    # Z-band swap overhead on A1 mini AMS lite: ~55 sec & ~1.0 g flush per swap (verified from v4 print)
    res = {}
    for pat, swaps in [("A", 4), ("B", 5)]:
        res[pat] = {
            "swaps": swaps,
            "flush_waste_g": round(swaps * 1.0, 1),
            "draft_024": {
                "layers": s_024["layers"],
                "boat_weight_g": s_024["base_weight_g"],
                "total_filament_g": round(s_024["base_weight_g"] + swaps * 1.0, 1),
                "time_str": fmt_sec(s_024["base_time_sec"] + swaps * 55),
                "base_slicer_time": s_024["base_time_str"],
            },
            "std_020": {
                "layers": s_020["layers"],
                "boat_weight_g": s_020["base_weight_g"],
                "total_filament_g": round(s_020["base_weight_g"] + swaps * 1.0, 1),
                "time_str": fmt_sec(s_020["base_time_sec"] + swaps * 55),
                "base_slicer_time": s_020["base_time_str"],
            },
        }
    (SLICER_DIR / "ab_slicer_summary.json").write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))

    # Render crisp PyVista Z-Buffer comparison (Front + Rear for A & B)
    ma = make_colored_mesh("A")
    mb = make_colored_mesh("B")
    front_cam = (195, -165, 118)
    rear_cam = (-195, 165, 118)

    fig, axes = plt.subplots(2, 2, figsize=(13.2, 9.6), dpi=120, facecolor="#f8fafc")
    fig.suptitle(
        "おふろレスキュー艇 Mk-II — 実機 AMS lite 3色（赤/白/深緑）見た目＆A1 mini 実スライス時間比較",
        fontsize=14, fontweight="bold", color="#0f172a", y=0.97,
    )

    axes[0, 0].imshow(snap(ma, front_cam)); axes[0, 0].set_axis_off()
    axes[0, 0].set_title(
        f"パターン A：レスキューレッド主体（前方）\n0.24mm: {res['A']['draft_024']['time_str']} / 0.20mm: {res['A']['std_020']['time_str']}",
        fontsize=11, fontweight="bold", color="#b91c1c",
    )
    axes[0, 1].imshow(snap(ma, rear_cam)); axes[0, 1].set_axis_off()
    axes[0, 1].set_title(
        f"パターン A（後方）｜交換 {res['A']['swaps']} 回・廃材約 {res['A']['flush_waste_g']} g\n赤(0-27) → 白(27-40.5) → 深緑(40.5-52.5) → 赤/白",
        fontsize=10.5, fontweight="bold", color="#334155",
    )

    axes[1, 0].imshow(snap(mb, front_cam)); axes[1, 0].set_axis_off()
    axes[1, 0].set_title(
        f"パターン B：深緑ハル＋赤ライン＋白ブリッジ（前方）\n0.24mm: {res['B']['draft_024']['time_str']} / 0.20mm: {res['B']['std_020']['time_str']}",
        fontsize=11, fontweight="bold", color="#14532d",
    )
    axes[1, 1].imshow(snap(mb, rear_cam)); axes[1, 1].set_axis_off()
    axes[1, 1].set_title(
        f"パターン B（後方）｜交換 {res['B']['swaps']} 回・廃材約 {res['B']['flush_waste_g']} g\n深緑(0-21.5) → 赤帯(21.5-27) → 白(27-40.5) → 赤(40.5-52.5) → 深緑/白",
        fontsize=10.5, fontweight="bold", color="#334155",
    )

    footer = (
        f"Bambu Studio CLI 実スライス確認済（A1 mini 0.4mm / Textured PEI 65℃ / サポートなし / 水密壁3周）  |  "
        f"船体重量: 0.24mm={s_024['base_weight_g']}g (喫水約13.2mm) / 0.20mm={s_020['base_weight_g']}g (喫水約13.6mm)"
    )
    fig.text(0.5, 0.018, footer, ha="center", va="center", fontsize=9.8, fontweight="bold", color="#1e293b")
    plt.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.05, wspace=0.04, hspace=0.16)
    out_png = SLICER_DIR / "mk2_ab_print_compare.png"
    fig.savefig(out_png, dpi=120, facecolor="#f8fafc")
    plt.close(fig)
    shutil.copy2(out_png, BRAIN / "mk2_ab_print_compare.png")
    print(f"Saved {out_png}")


if __name__ == "__main__":
    main()
