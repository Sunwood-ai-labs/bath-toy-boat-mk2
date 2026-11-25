"""True Z-Buffer OpenGL/VTK 3D Renderer (PyVista) for Bath Toy Boat Mk-II.
Zero polygon-clipping / zero fake occlusion — pixel-accurate depth buffer!

Outputs two crystal-clear HD MP4 videos:
1. mk2_vtk_fluid_3d.mp4 : Side-by-side True 3D Towing Tank (Water tubes) + Wind Tunnel (Air tubes)
2. mk2_vtk_stability_fea_3d.mp4 : True 3D Open-Boat Roll Stability (honest 0..22 deg safe range vs 23 deg gunwale immersion) + True 3D Solid FEA Stress Mesh
"""
import json
import pathlib
import shutil
import subprocess
import sys
import numpy as np
from scipy.interpolate import RegularGridInterpolator
import pyvista as pv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

pv.OFF_SCREEN = True

ROOT = pathlib.Path(r"C:\Users\makim\.gemini\antigravity\scratch\bath-toy-boat-mk2")
BRAIN = pathlib.Path(r"C:\Users\makim\.gemini\antigravity\brain\524fbd92-1904-448d-9085-9a1c8de17e28")
CFD_DIR = ROOT / "cae" / "cfd"
FEA_DIR = ROOT / "cae" / "fea"
HYD_DIR = ROOT / "cae" / "hydrostatics"
STL_PATH = ROOT / "cad" / "out" / "bath_boat_mk2.stl"
VID_DIR = ROOT / "cae" / "videos_vtk"
VID_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(CFD_DIR))
from run_float_sim import decode_free_surface


def setup_font():
    for fname in ["Yu Gothic", "Meiryo", "MS Gothic", "DejaVu Sans"]:
        if any(fname.lower() in f.name.lower() for f in font_manager.fontManager.ttflist):
            plt.rcParams["font.family"] = fname
            break
    plt.rcParams["axes.unicode_minus"] = False


def load_colored_boat_pv():
    """Load Mk-II STL into PyVista with actual AMS 3-color Z-band cell colors."""
    mesh = pv.read(str(STL_PATH))
    centers = mesh.cell_centers().points
    zc = centers[:, 2]
    colors = np.zeros((mesh.n_cells, 3), dtype=np.uint8)
    # Pattern B: Deep Green (#234D40), Red (#C12E1F), White (#F5F5F3)
    c_grn = np.array([0x23, 0x4D, 0x40], dtype=np.uint8)
    c_red = np.array([0xC1, 0x2E, 0x1F], dtype=np.uint8)
    c_wht = np.array([0xF5, 0xF5, 0xF3], dtype=np.uint8)
    colors[:] = c_grn
    colors[(zc >= 21.5) & (zc < 27.0)] = c_red
    colors[(zc >= 27.0) & (zc < 40.5)] = c_wht
    colors[(zc >= 40.5) & (zc < 52.5)] = c_red
    colors[(zc >= 52.5) & (zc < 55.0)] = c_grn
    colors[zc >= 55.0] = c_wht
    mesh.cell_data["RGB"] = colors
    return mesh


def trace_streamlines(fc_path: pathlib.Path, seeds: np.ndarray, dt: float, n_steps: int):
    d = decode_free_surface(fc_path)
    g = d["grid"]
    nx, ny, nz = g["cells"]
    dx_mm = float(g["spacing"]) * 1000.0
    o_mm = np.array(g["origin"]) * 1000.0
    xs = o_mm[0] + (np.arange(nx) + 0.5) * dx_mm
    ys = o_mm[1] + (np.arange(ny) + 0.5) * dx_mm
    zs = o_mm[2] + (np.arange(nz) + 0.5) * dx_mm
    vel = d["frames"][-1]["velocity"].reshape((nz, ny, nx, 3)) * 1000.0
    iu = RegularGridInterpolator((zs, ys, xs), vel[:, :, :, 0], bounds_error=False, fill_value=0.0)
    iv = RegularGridInterpolator((zs, ys, xs), vel[:, :, :, 1], bounds_error=False, fill_value=0.0)
    iw = RegularGridInterpolator((zs, ys, xs), vel[:, :, :, 2], bounds_error=False, fill_value=0.0)

    pts = seeds.copy()
    traj = [pts.copy()]
    spds = []
    for _ in range(n_steps):
        zyx = pts[:, [2, 1, 0]]
        vvec = np.column_stack([iu(zyx), iv(zyx), iw(zyx)])
        spds.append(np.linalg.norm(vvec, axis=1))
        pts = pts + vvec * dt
        traj.append(pts.copy())
    return np.stack(traj, axis=1), np.stack(spds, axis=1)


def make_tube_multiblock(traj, radius=0.9):
    blocks = pv.MultiBlock()
    for m in range(traj.shape[0]):
        pts = traj[m]
        # Skip degenerate segments
        if np.linalg.norm(pts[-1] - pts[0]) < 5.0:
            continue
        line = pv.lines_from_points(pts)
        blocks.append(line.tube(radius=radius, n_sides=8))
    return blocks.combine()


def encode_mp4(frames_dir: pathlib.Path, out_mp4: pathlib.Path, fps: int = 12):
    cmd = [
        "ffmpeg", "-y", "-framerate", str(fps),
        "-i", str(frames_dir / "frame_%04d.png"),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19",
        "-movflags", "+faststart",
        str(out_mp4),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    shutil.copy2(out_mp4, BRAIN / out_mp4.name)
    print(f"Encoded {out_mp4.name} ({out_mp4.stat().st_size} bytes)")


def composite_side_by_side(img_l, img_r, title, sub_l, sub_r, footer, out_path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.8, 7.2), dpi=100, facecolor="#0f172a")
    fig.suptitle(title, fontsize=14, fontweight="bold", color="#f8fafc", y=0.965)
    ax1.imshow(img_l); ax1.set_axis_off(); ax1.set_title(sub_l, fontsize=11, fontweight="bold", color="#38bdf8", pad=4)
    ax2.imshow(img_r); ax2.set_axis_off(); ax2.set_title(sub_r, fontsize=11, fontweight="bold", color="#fde047", pad=4)
    fig.text(
        0.5, 0.035, footer, ha="center", va="center", fontsize=10, fontweight="bold", color="#e2e8f0",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#1e293b", edgecolor="#38bdf8"),
    )
    plt.subplots_adjust(left=0.01, right=0.99, top=0.88, bottom=0.09, wspace=0.02)
    fig.savefig(out_path, dpi=100, facecolor="#0f172a")
    plt.close(fig)


# =============================================================================
# VIDEO A: True Z-Buffer 3D Towing Tank (Water) + Wind Tunnel (Air)
# =============================================================================
def render_vtk_fluid_video(boat_mesh):
    print("=== Rendering VTK Z-Buffer Video A: Towing Tank + Wind Tunnel ===")
    fdir = VID_DIR / "fluid"
    if fdir.exists():
        shutil.rmtree(fdir)
    fdir.mkdir(parents=True)

    ty, tz = np.meshgrid(np.linspace(-52, 52, 9), [4.0, 10.0, 16.0])
    t_seeds = np.column_stack([np.full(ty.size, 118.0), ty.ravel(), tz.ravel()])
    t_traj, _ = trace_streamlines(CFD_DIR / "mk2_towing_tank.fieldcraft", t_seeds, dt=0.65, n_steps=92)
    t_tubes = make_tube_multiblock(t_traj, radius=0.85)

    wy, wz = np.meshgrid(np.linspace(-42, 42, 7), [22.0, 34.0, 46.0, 58.0])
    w_seeds = np.column_stack([np.full(wy.size, 118.0), wy.ravel(), wz.ravel()])
    w_traj, _ = trace_streamlines(CFD_DIR / "mk2_wind_tunnel.fieldcraft", w_seeds, dt=0.045, n_steps=92)
    w_tubes = make_tube_multiblock(w_traj, radius=0.85)

    # Water surface plane at Z=11.0 mm with hole punched out by boat? No! True Z-buffer handles intersection cleanly!
    water_plane = pv.Plane(center=(0, 0, 11.0), direction=(0, 0, 1), i_size=260, j_size=150, i_resolution=20, j_resolution=12)

    n_frames = 48
    t_len = t_traj.shape[1]

    for i in range(n_frames):
        ang = np.deg2rad(-40.0 + 360.0 * (i / n_frames))
        cam_r = 250.0
        cam_pos = (cam_r * np.cos(ang), cam_r * np.sin(ang), 125.0)
        head = int((i * 2.4) % (t_len - 1))

        # --- Left: Towing Tank (Water) ---
        pl1 = pv.Plotter(off_screen=True, window_size=[640, 560])
        pl1.set_background("#0f172a")
        pl1.add_mesh(boat_mesh, scalars="RGB", rgb=True, smooth_shading=False, specular=0.25)
        pl1.add_mesh(t_tubes, color="#38bdf8", opacity=0.72, specular=0.5)
        # Moving glowing water droplets along streamlines
        drop_pts = t_traj[:, head, :]
        pl1.add_mesh(pv.PolyData(drop_pts), color="#e0f2fe", point_size=9, render_points_as_spheres=True)
        pl1.camera_position = [cam_pos, (0, 0, 18), (0, 0, 1)]
        img_l = pl1.screenshot(return_img=True)
        pl1.close()

        # --- Right: Wind Tunnel (Air) ---
        pl2 = pv.Plotter(off_screen=True, window_size=[640, 560])
        pl2.set_background("#0f172a")
        pl2.add_mesh(boat_mesh, scalars="RGB", rgb=True, smooth_shading=False, specular=0.25)
        pl2.add_mesh(water_plane, color="#0369a1", opacity=0.32)
        pl2.add_mesh(w_tubes, color="#facc15", opacity=0.72, specular=0.5)
        wdrop_pts = w_traj[:, head, :]
        pl2.add_mesh(pv.PolyData(wdrop_pts), color="#ffffff", point_size=9, render_points_as_spheres=True)
        pl2.camera_position = [cam_pos, (0, 0, 22), (0, 0, 1)]
        img_r = pl2.screenshot(return_img=True)
        pl2.close()

        fp = fdir / f"frame_{i:04d}.png"
        composite_side_by_side(
            img_l, img_r,
            "FieldCraft 本物 Z-Buffer 3D 流体シミュレーション（貫通ゼロ・360°検証）",
            "① 水中曳航テスト（水 U=4.0 mm/s → 船首で左右に綺麗に分離）",
            "② 上部構造 風洞テスト（空気 U=60.0 mm/s → ブリッジ上を滑らかに通過）",
            "VTK OpenGL Z-Buffer レンダリング（ピクセル単位の厳密奥行き判定）  |  水流 90,720セル / 風洞 121,500セル",
            fp,
        )
        if i == 8:
            shutil.copy2(fp, BRAIN / "mk2_vtk_fluid_preview.png")

    encode_mp4(fdir, VID_DIR / "mk2_vtk_fluid_3d.mp4", fps=12)


# =============================================================================
# VIDEO B: True Z-Buffer 3D Honest Open-Boat Stability (0..22 deg) + True 3D Solid FEA
# =============================================================================
def render_vtk_stability_fea_video(boat_mesh):
    print("=== Rendering VTK Z-Buffer Video B: Honest Open-Boat Roll Stability + Solid FEA ===")
    fdir = VID_DIR / "stab_fea"
    if fdir.exists():
        shutil.rmtree(fdir)
    fdir.mkdir(parents=True)

    gz_data = json.loads((HYD_DIR / "gz_stability.json").read_text(encoding="utf-8"))
    curve = gz_data["curve"]
    c_deg = np.array([r["heel_deg"] for r in curve], dtype=float)
    c_gz = np.array([r["GZ_mm"] for r in curve], dtype=float)
    c_zw = np.array([r["waterline_z_mm"] for r in curve], dtype=float)
    c_fb = np.array([r["gunwale_freeboard_mm"] for r in curve], dtype=float)

    # Load actual FieldCraft FEA VTU mesh directly into PyVista!
    fea_grid = pv.read(str(FEA_DIR / "result_static.vtu"))
    fea_surf = fea_grid.extract_surface()
    # Find displacement & von_mises array names
    disp_name = next((n for n in fea_surf.point_data.keys() if "disp" in n.lower() or n == "U"), None)
    vm_name = next((n for n in fea_surf.point_data.keys() if "mises" in n.lower()), None)
    base_pts = fea_surf.points.copy()
    disp_arr = fea_surf.point_data[disp_name] if disp_name else np.zeros_like(base_pts)
    vm_max = float(np.percentile(fea_surf.point_data[vm_name], 99.5)) if vm_name else 0.2

    water_plane = pv.Plane(center=(0, 0, 0.0), direction=(0, 0, 1), i_size=260, j_size=160, i_resolution=24, j_resolution=16)

    n_frames = 48
    # Rock strictly within HONEST safe open-boat range: -21 deg .. +21 deg (gunwale stays ABOVE water!)
    ts = np.linspace(0, 2 * np.pi, n_frames, endpoint=False)
    heel_seq = 21.0 * np.sin(ts)

    for i, deg in enumerate(heel_seq):
        adeg = abs(deg)
        zw = float(np.interp(adeg, c_deg, c_zw))
        gz = float(np.interp(adeg, c_deg, c_gz))
        fb = float(np.interp(adeg, c_deg, c_fb))

        # Transform boat mesh cleanly (rotate about X, shift waterline to Z=0)
        b_rot = boat_mesh.copy()
        b_rot.rotate_x(-deg, point=(0, 0, 0), inplace=True)
        b_rot.translate((0, 0, -zw), inplace=True)

        # --- Left: True 3D Open-Boat Roll Stability (0..±21 deg, gunwale ABOVE water!) ---
        pl1 = pv.Plotter(off_screen=True, window_size=[640, 560])
        pl1.set_background("#0f172a")
        pl1.add_mesh(b_rot, scalars="RGB", rgb=True, smooth_shading=False, specular=0.25)
        pl1.add_mesh(water_plane, color="#0284c7", opacity=0.45, show_edges=True, edge_color="#38bdf8", line_width=0.5)
        pl1.camera_position = [(245, 35, 65), (0, 0, 12), (0, 0, 1)]
        img_l = pl1.screenshot(return_img=True)
        pl1.close()

        # --- Right: True 3D Solid FEA Stress Mesh (pulsing 0 -> 20 N) ---
        load_frac = 0.5 * (1.0 - np.cos(2.0 * np.pi * i / (n_frames / 2.0)))
        fea_cur = fea_surf.copy()
        fea_cur.points = base_pts + disp_arr * (3500.0 * load_frac)
        if vm_name:
            fea_cur.point_data["Stress_MPa"] = fea_surf.point_data[vm_name] * load_frac

        pl2 = pv.Plotter(off_screen=True, window_size=[640, 560])
        pl2.set_background("#0f172a")
        pl2.add_mesh(
            fea_cur, scalars="Stress_MPa" if vm_name else None,
            cmap="turbo", clim=[0.0, vm_max], show_scalar_bar=False, smooth_shading=True,
        )
        # 3D Red load arrows on cabin roof
        if load_frac > 0.08:
            for lx in [4, 14, 24]:
                arr_mesh = pv.Arrow(start=(lx, 0, 58), direction=(0, 0, -1), scale=16.0 * load_frac, tip_radius=0.14, shaft_radius=0.05)
                pl2.add_mesh(arr_mesh, color="#f43f5e")
        ang2 = np.deg2rad(-48.0 + 35.0 * np.sin(2 * np.pi * i / n_frames))
        pl2.camera_position = [(235 * np.cos(ang2), 235 * np.sin(ang2), 115), (5, 0, 20), (0, 0, 1)]
        img_r = pl2.screenshot(return_img=True)
        pl2.close()

        fp = fdir / f"frame_{i:04d}.png"
        composite_side_by_side(
            img_l, img_r,
            "本物 Z-Buffer 3D：オープンボート安全復原テスト（0〜±21°）× FieldCraft ソリッド強度 FEA",
            f"① 安全復原レンジ（φ={deg:+5.1f}° / 舷側余裕 {fb:+.1f}mm / GZ={gz:.1f}mm）\n※23°以上でフチ没水のため安全限界は ±22°",
            f"② 屋根押下 強度FEA（荷重 {20.0*load_frac:4.1f} N / 最大応力 {0.2075*load_frac:.3f} MPa）\n実たわみ 0.00126 mm を3500倍強調表示",
            "左：オープンボートとして浸水ゼロで起き上がる正確な限界（±22°）を検証  |  右：FieldCraft 163,569要素ソリッドメッシュ実応力",
            fp,
        )
        if i == 12:
            shutil.copy2(fp, BRAIN / "mk2_vtk_stability_fea_preview.png")

    encode_mp4(fdir, VID_DIR / "mk2_vtk_stability_fea_3d.mp4", fps=12)


def main():
    setup_font()
    boat_mesh = load_colored_boat_pv()
    render_vtk_fluid_video(boat_mesh)
    render_vtk_stability_fea_video(boat_mesh)
    print("ALL VTK TRUE Z-BUFFER 3D VIDEOS COMPLETE!")


if __name__ == "__main__":
    main()
