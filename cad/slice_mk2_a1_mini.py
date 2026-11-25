"""Bambu Lab A1 mini real CLI slicer & single-assembly 3MF packager for Bath Toy Boat Mk-II."""
import json
import pathlib
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

ROOT = pathlib.Path(r"C:\Users\makim\.gemini\antigravity\scratch\bath-toy-boat-mk2")
CAD_OUT = ROOT / "cad" / "out"
SLICER_DIR = ROOT / "cad" / "slicer"
SLICER_DIR.mkdir(parents=True, exist_ok=True)

THREEMF_SRC = CAD_OUT / "bath_boat_mk2_pip.3mf"
THREEMF_ZBAND = CAD_OUT / "bath_boat_mk2_pip_4color_zband.3mf"
BAMBU_EXE = pathlib.Path(r"C:\Users\makim\AppData\Local\Programs\Bambu Studio\bambu-studio.exe")
BAMBU_RES = BAMBU_EXE.parent / "resources" / "profiles" / "BBL"

NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
MNS = "http://schemas.microsoft.com/3dmanufacturing/material/2015/02"
ET.register_namespace("", NS)
ET.register_namespace("m", MNS)


def setup_font():
    for fname in ["Yu Gothic", "Meiryo", "MS Gothic", "DejaVu Sans"]:
        if any(fname.lower() in f.name.lower() for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = fname
            break
    plt.rcParams["axes.unicode_minus"] = False


def wrap_3mf_as_single_assembly(src: pathlib.Path, dst: pathlib.Path):
    with zipfile.ZipFile(src, "r") as zin:
        items = {n: zin.read(n) for n in zin.namelist()}
    root = ET.fromstring(items["3D/3dmodel.model"])
    res = root.find(f"{{{NS}}}resources")
    build = root.find(f"{{{NS}}}build")
    existing = build.findall(f"{{{NS}}}item")
    if len(existing) > 1:
        parent = ET.SubElement(res, f"{{{NS}}}object", {"id": "99", "type": "model", "name": "BathBoatMk2_PIP"})
        comps = ET.SubElement(parent, f"{{{NS}}}components")
        for it in existing:
            ET.SubElement(comps, f"{{{NS}}}component", {"objectid": it.attrib["objectid"]})
            build.remove(it)
        ET.SubElement(build, f"{{{NS}}}item", {"objectid": "99"})
    items["3D/3dmodel.model"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    tmp = dst.with_suffix(".3mf.tmp")
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for n, data in items.items():
            zout.writestr(n, data)
    shutil.move(str(tmp), str(dst))


def make_zband_4color_3mf(src: pathlib.Path, dst: pathlib.Path):
    """Assign 4 Z-band colors (Cobalt Blue / White / Vermilion / Yellow) at triangle level."""
    with zipfile.ZipFile(src, "r") as zin:
        items = {n: zin.read(n) for n in zin.namelist()}
    root = ET.fromstring(items["3D/3dmodel.model"])
    res = root.find(f"{{{NS}}}resources")

    # Remove old colorgroups
    for cg in list(res.findall(f"{{{MNS}}}colorgroup")):
        res.remove(cg)
    cg = ET.Element(f"{{{MNS}}}colorgroup", {"id": "100"})
    for hex_c in ["#22579AFF", "#F8F9FAFF", "#FF5A36FF", "#FFD13BFF"]:
        ET.SubElement(cg, f"{{{MNS}}}color", {"color": hex_c})
    res.insert(0, cg)

    for obj in res.findall(f"{{{NS}}}object"):
        mesh = obj.find(f"{{{NS}}}mesh")
        if mesh is None:
            continue
        verts = []
        for v in mesh.find(f"{{{NS}}}vertices").findall(f"{{{NS}}}vertex"):
            verts.append((float(v.attrib["x"]), float(v.attrib["y"]), float(v.attrib["z"])))
        for tri in mesh.find(f"{{{NS}}}triangles").findall(f"{{{NS}}}triangle"):
            v1, v2, v3 = int(tri.attrib["v1"]), int(tri.attrib["v2"]), int(tri.attrib["v3"])
            zc = (verts[v1][2] + verts[v2][2] + verts[v3][2]) / 3.0
            if zc < 27.0:
                idx = "0"
            elif zc < 40.5:
                idx = "1"
            elif zc < 52.5:
                idx = "2"
            else:
                idx = "3"
            tri.attrib["pid"] = "100"
            tri.attrib["p1"] = idx
            tri.attrib["p2"] = idx
            tri.attrib["p3"] = idx

    items["3D/3dmodel.model"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for n, data in items.items():
            zout.writestr(n, data)


def load_flat_profile(subdir: str, name: str) -> dict:
    p = BAMBU_RES / subdir / f"{name}.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    if "inherits" in d:
        parent = load_flat_profile(subdir, d["inherits"])
        parent.update(d)
        d = parent
    return d


def slice_case(case_id: str, proc_name: str, overrides: dict) -> dict:
    cdir = SLICER_DIR / case_id
    cdir.mkdir(parents=True, exist_ok=True)
    mach = load_flat_profile("machine", "Bambu Lab A1 mini 0.4 nozzle")
    proc = load_flat_profile("process", proc_name)
    fila = load_flat_profile("filament", "Bambu PLA Basic @BBL A1M")
    proc.update(overrides)
    proc["enable_support"] = "0"
    proc["enable_arc_fitting"] = "0"

    f_m = cdir / "machine.json"
    f_p = cdir / "process.json"
    f_f = cdir / "filament.json"
    f_m.write_text(json.dumps(mach, indent=1), encoding="utf-8")
    f_p.write_text(json.dumps(proc, indent=1), encoding="utf-8")
    f_f.write_text(json.dumps(fila, indent=1), encoding="utf-8")

    out_3mf = cdir / f"{case_id}.gcode.3mf"
    cmd = [
        str(BAMBU_EXE),
        "--load-settings", f"{f_m};{f_p}",
        "--load-filaments", str(f_f),
        "--arrange", "1",
        "--slice", "0",
        "--export-3mf", str(out_3mf),
        str(THREEMF_SRC),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0 or not out_3mf.exists():
        raise RuntimeError(f"Slice {case_id} failed: rc={r.returncode} {r.stderr[:400]}")

    gcode_text = ""
    with zipfile.ZipFile(out_3mf, "r") as z:
        for n in z.namelist():
            if n.endswith(".gcode"):
                gcode_text = z.read(n).decode("utf-8", errors="ignore")
                (cdir / "plate_1.gcode").write_text(gcode_text, encoding="utf-8")
                break

    def _m(pat, default=None):
        m = re.search(pat, gcode_text)
        return m.group(1).strip() if m else default

    time_str = _m(r";\s*model printing time:\s*([^;\n]+)") or _m(r";\s*total estimated time:\s*([^;\n]+)") or "N/A"
    total_time_str = _m(r";\s*total estimated time:\s*([^;\n]+)") or time_str
    wt_g = float(_m(r";\s*total filament weight \[g\]\s*:\s*([0-9.]+)", "0"))
    len_m = float(_m(r";\s*total filament length \[mm\]\s*:\s*([0-9.]+)", "0")) / 1000.0
    layers = int(_m(r";\s*total layer number:\s*(\d+)", "0"))
    vol_cm3 = 190.69
    eff_rho = wt_g / vol_cm3 if wt_g > 0 else 0.0
    return {
        "case_id": case_id,
        "process": proc_name,
        "layers": layers,
        "filament_weight_g": round(wt_g, 2),
        "filament_length_m": round(len_m, 2),
        "effective_density_g_cm3": round(eff_rho, 3),
        "model_time": time_str,
        "total_time": total_time_str,
        "gcode_path": str(cdir / "plate_1.gcode"),
    }


def parse_gcode_xy_at_z(gcode_path: pathlib.Path, target_zs: list):
    """Extract extruded XY segments at layers closest to target_zs."""
    layers = {}
    cur_z = None
    cur_x = cur_y = 0.0
    cur_e = 0.0
    segs = []
    with gcode_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("; Z_HEIGHT:") or line.startswith(";Z:"):
                if cur_z is not None and segs:
                    layers[cur_z] = segs
                cur_z = float(line.split(":", 1)[1].strip())
                segs = []
            elif line.startswith("G1 ") and cur_z is not None:
                xm = re.search(r"X([-\d.]+)", line)
                ym = re.search(r"Y([-\d.]+)", line)
                em = re.search(r"E([-\d.]+)", line)
                nx = float(xm.group(1)) if xm else cur_x
                ny = float(ym.group(1)) if ym else cur_y
                if em and float(em.group(1)) > 0 and (xm or ym):
                    segs.append((cur_x, cur_y, nx, ny))
                cur_x, cur_y = nx, ny
        if cur_z is not None and segs:
            layers[cur_z] = segs

    avail_zs = sorted(layers.keys())
    out = {}
    for tz in target_zs:
        best_z = min(avail_zs, key=lambda z: abs(z - tz))
        out[tz] = (best_z, layers[best_z])
    return out, avail_zs


def plot_slicer_review(summary: list, gcode_path: pathlib.Path):
    setup_font()
    target_zs = [5.0, 17.0, 22.0, 38.0]
    layer_map, avail_zs = parse_gcode_xy_at_z(gcode_path, target_zs)

    fig, axes = plt.subplots(2, 2, figsize=(13, 9.5), facecolor="#f7f5f0")
    fig.suptitle("Bambu Lab A1 mini 実Gコード 4層断面レビュー（おふろレスキュー艇 Mk-II / サポートなしPIP）", fontsize=14, fontweight="bold")
    titles = {
        5.0: "Z ≈ 5.0 mm（船底バスタブ＆前後PIP軸受ネック）",
        17.0: "Z ≈ 17.0 mm（スタンドパイプ上端＆高床タービンベイ）",
        22.0: "Z ≈ 22.0 mm（ジェットノズル→6枚羽根タービン＆キャビン）",
        38.0: "Z ≈ 38.0 mm（バイザー屋根＆レーダー軸＆エアロファネル）",
    }
    colors = ["#22579a", "#1d7a8a", "#d95d39", "#c99700"]

    for ax, tz, col in zip(axes.flat, target_zs, colors):
        az, segs = layer_map[tz]
        ax.set_facecolor("#ffffff")
        if segs:
            arr = np.array(segs)
            # Center around mean
            cx = 0.5 * (arr[:, 0].min() + arr[:, 0].max())
            cy = 0.5 * (arr[:, 1].min() + arr[:, 1].max())
            xs = np.column_stack([arr[:, 0] - cx, arr[:, 2] - cx, np.full(len(arr), np.nan)]).ravel()
            ys = np.column_stack([arr[:, 1] - cy, arr[:, 3] - cy, np.full(len(arr), np.nan)]).ravel()
            ax.plot(xs, ys, color=col, linewidth=0.55, alpha=0.88)
        ax.set_aspect("equal", "box")
        ax.set_title(f"{titles[tz]} [実測 Z={az:.2f} mm]", fontsize=10.5, fontweight="bold")
        ax.set_xlabel("X [mm]")
        ax.set_ylabel("Y [mm]")
        ax.grid(True, linestyle="--", alpha=0.35)

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    footer = "  |  ".join(
        f"{s['case_id']}: {s['layers']}層 / {s['filament_weight_g']}g (実効密度 {s['effective_density_g_cm3']} g/cm³) / 所要 {s['total_time']}"
        for s in summary
    )
    fig.text(0.5, 0.01, footer, ha="center", fontsize=9.5, color="#333333", fontweight="bold")
    out_png = SLICER_DIR / "mk2_slicer_layers.png"
    fig.savefig(out_png, dpi=160)
    plt.close(fig)
    print(f"Saved {out_png}")


def main():
    wrap_3mf_as_single_assembly(THREEMF_SRC, THREEMF_SRC)
    make_zband_4color_3mf(THREEMF_SRC, THREEMF_ZBAND)
    print(f"Wrapped single assembly: {THREEMF_SRC}")
    print(f"Created 4-color Z-band 3MF: {THREEMF_ZBAND}")

    s1 = slice_case("draft_024_watertight", "0.24mm Draft @BBL A1M", {
        "wall_loops": "3",
        "sparse_infill_density": "15%",
        "sparse_infill_pattern": "gyroid",
    })
    s2 = slice_case("std_020_watertight", "0.20mm Standard @BBL A1M", {
        "wall_loops": "3",
        "sparse_infill_density": "20%",
        "sparse_infill_pattern": "gyroid",
    })
    summary = [s1, s2]
    (SLICER_DIR / "slicer_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    plot_slicer_review(summary, pathlib.Path(s2["gcode_path"]))


if __name__ == "__main__":
    main()
