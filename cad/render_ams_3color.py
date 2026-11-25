import pathlib
import shutil
import struct
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

ROOT = pathlib.Path(r"C:\Users\makim\.gemini\antigravity\scratch\bath-toy-boat-mk2")
BRAIN = pathlib.Path(r"C:\Users\makim\.gemini\antigravity\brain\524fbd92-1904-448d-9085-9a1c8de17e28")
STL_PATH = ROOT / "cad/out/bath_boat_mk2.stl"
SRC_3MF = ROOT / "cad/out/bath_boat_mk2_pip.3mf"

NS = "http://schemas.microsoft.com/3dmanufacturing/core/2015/02"
MNS = "http://schemas.microsoft.com/3dmanufacturing/material/2015/02"
ET.register_namespace("", NS)
ET.register_namespace("m", MNS)

for fname in ["Yu Gothic", "Meiryo", "MS Gothic", "DejaVu Sans"]:
    if any(fname.lower() in f.name.lower() for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = fname
        break

# Read binary STL
data = STL_PATH.read_bytes()
dt = np.dtype([("n", "<f4", (3,)), ("v0", "<f4", (3,)), ("v1", "<f4", (3,)), ("v2", "<f4", (3,)), ("a", "<u2")])
arr = np.frombuffer(data[84:], dtype=dt)
verts = np.stack([arr["v0"], arr["v1"], arr["v2"]], axis=1).astype(np.float64)
normals = arr["n"].astype(np.float64)
zc = verts[:, :, 2].mean(axis=1)

# Lighting
light1 = np.array([0.55, -0.50, 0.67]); light1 /= np.linalg.norm(light1)
light2 = np.array([-0.40, 0.60, 0.50]); light2 /= np.linalg.norm(light2)
nd = np.linalg.norm(normals, axis=1, keepdims=True)
nn = np.divide(normals, np.where(nd > 1e-9, nd, 1.0))
shade = np.clip(0.45 + 0.42 * np.maximum(0, nn @ light1) + 0.16 * np.maximum(0, nn @ light2), 0.28, 1.0)

# Actual AMS lite 3 spools: Red (#C12E1F), White (#FFFFFF), Dark Green (#234D40)
C_RED = np.array([0xC1, 0x2E, 0x1F]) / 255.0
C_WHITE = np.array([0xF6, 0xF6, 0xF4]) / 255.0
C_GREEN = np.array([0x23, 0x4D, 0x40]) / 255.0


def z_to_idx_a(z):
    # 0: Red, 1: White, 2: Dark Green
    if z < 27.0:
        return 0
    if z < 40.5:
        return 1
    if z < 52.5:
        return 2
    if z < 55.0:
        return 0
    return 1


def z_to_idx_b(z):
    # 0: Red, 1: White, 2: Dark Green
    if z < 21.5:
        return 2
    if z < 27.0:
        return 0
    if z < 40.5:
        return 1
    if z < 52.5:
        return 0
    if z < 55.0:
        return 2
    return 1


PALETTE = np.array([C_RED, C_WHITE, C_GREEN])


def render_panel(ax, face_rgb, elev, azim, title):
    rgba = np.column_stack([face_rgb * shade[:, None], np.ones(len(face_rgb))])
    poly = Poly3DCollection(verts, facecolors=rgba, edgecolors="none", antialiased=False)
    ax.add_collection3d(poly)
    ax.set_xlim(-82, 92)
    ax.set_ylim(-50, 50)
    ax.set_zlim(0, 72)
    ax.set_box_aspect([174, 100, 72])
    ax.view_init(elev=elev, azim=azim)
    ax.set_facecolor("#e8edf2")
    ax.set_axis_off()
    ax.set_title(title, fontsize=11, fontweight="bold", pad=2)


def export_3color_3mf(src: pathlib.Path, dst: pathlib.Path, fn):
    with zipfile.ZipFile(src, "r") as zin:
        items = {n: zin.read(n) for n in zin.namelist()}
    root = ET.fromstring(items["3D/3dmodel.model"])
    res = root.find(f"{{{NS}}}resources")
    for cg in list(res.findall(f"{{{MNS}}}colorgroup")):
        res.remove(cg)
    cg = ET.Element(f"{{{MNS}}}colorgroup", {"id": "100"})
    for hx in ["#C12E1FFF", "#FFFFFFFF", "#234D40FF"]:
        ET.SubElement(cg, f"{{{MNS}}}color", {"color": hx})
    res.insert(0, cg)

    for obj in res.findall(f"{{{NS}}}object"):
        mesh = obj.find(f"{{{NS}}}mesh")
        if mesh is None:
            continue
        vs = [(float(v.attrib["x"]), float(v.attrib["y"]), float(v.attrib["z"])) for v in mesh.find(f"{{{NS}}}vertices").findall(f"{{{NS}}}vertex")]
        for tri in mesh.find(f"{{{NS}}}triangles").findall(f"{{{NS}}}triangle"):
            v1, v2, v3 = int(tri.attrib["v1"]), int(tri.attrib["v2"]), int(tri.attrib["v3"])
            zmid = (vs[v1][2] + vs[v2][2] + vs[v3][2]) / 3.0
            idx = str(fn(zmid))
            tri.attrib["pid"] = "100"
            tri.attrib["p1"] = idx
            tri.attrib["p2"] = idx
            tri.attrib["p3"] = idx
    items["3D/3dmodel.model"] = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    with zipfile.ZipFile(dst, "w", compression=zipfile.ZIP_DEFLATED) as zout:
        for n, d in items.items():
            zout.writestr(n, d)


idx_a = np.array([z_to_idx_a(z) for z in zc])
idx_b = np.array([z_to_idx_b(z) for z in zc])
ca = PALETTE[idx_a]
cb = PALETTE[idx_b]

fig = plt.figure(figsize=(14, 10), facecolor="#f7f5f0")
fig.suptitle("おふろレスキュー艇 Mk-II — 実機 AMS lite 3色（赤 #C12E1F / 白 #FFFFFF / 深緑 #234D40）Z層カラー比較", fontsize=13.5, fontweight="bold")

render_panel(fig.add_subplot(2, 2, 1, projection="3d"), ca, 26, -42, "パターンA：レスキューレッド主体（前方）\n赤(0-27) → 白(27-40.5) → 深緑(40.5-52.5) → 赤/白")
render_panel(fig.add_subplot(2, 2, 2, projection="3d"), ca, 26, 138, "パターンA：レスキューレッド主体（後方）\n交換4回・廃材約4g（前作v4と同一トーン）")
render_panel(fig.add_subplot(2, 2, 3, projection="3d"), cb, 26, -42, "パターンB：深緑ハル＋赤バンパー帯＋白ブリッジ（前方）\n深緑(0-21.5) → 赤帯(21.5-27) → 白(27-40.5) → 赤(40.5-52.5) → 深緑/白")
render_panel(fig.add_subplot(2, 2, 4, projection="3d"), cb, 26, 138, "パターンB：深緑ハル＋赤バンパー帯＋白ブリッジ（後方）\n交換5回・廃材約5g（高速パトロール艇風）")

plt.tight_layout(rect=[0, 0, 1, 0.95])
out_png = ROOT / "cad/out/mk2_ams_3color_compare.png"
fig.savefig(out_png, dpi=160)
plt.close(fig)
shutil.copy2(out_png, BRAIN / "mk2_ams_3color_compare.png")

export_3color_3mf(SRC_3MF, ROOT / "cad/out/bath_boat_mk2_ams3color_A.3mf", z_to_idx_a)
export_3color_3mf(SRC_3MF, ROOT / "cad/out/bath_boat_mk2_ams3color_B.3mf", z_to_idx_b)
print("Saved preview and both 3-color 3MFs!")
