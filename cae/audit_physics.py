import pathlib
import sys
import numpy as np

ROOT = pathlib.Path(r"C:\Users\makim\.gemini\antigravity\scratch\bath-toy-boat-mk2")
sys.path.insert(0, str(ROOT / "cae/cfd"))
from run_float_sim import decode_free_surface

# 1. Jet-to-Turbine CFD audit
d = decode_free_surface(ROOT / "cae/cfd/mk2_jet_turbine.fieldcraft")
g = d["grid"]
nx, ny, nz = g["cells"]
dx_mm = g["spacing"] * 1000.0
o_mm = np.array(g["origin"]) * 1000.0
xs = o_mm[0] + (np.arange(nx) + 0.5) * dx_mm
ys = o_mm[1] + (np.arange(ny) + 0.5) * dx_mm
zs = o_mm[2] + (np.arange(nz) + 0.5) * dx_mm
Z3, Y3, X3 = np.meshgrid(zs, ys, xs, indexing="ij")
print("=== 1. JET CFD AUDIT ===")
for idx in [0, 8, 16, 24, 32]:
    fr = d["frames"][idx]
    f3 = fr["fill"].reshape((nz, ny, nx))
    wet = f3 > 0.3
    xmin = float(X3[wet].min()) if np.any(wet) else 999
    zmin = float(Z3[wet].min()) if np.any(wet) else 999
    n_bay = int(np.sum(wet & (X3 < -34.0)))
    print(f"  frame {idx:2d} t={fr['time']*1000:5.1f}ms | wet={int(wet.sum()):4d} | front_X={xmin:6.1f}mm | min_Z={zmin:5.1f}mm | bay(X<-34)={n_bay}")

# 2. Towing Tank & Wind Tunnel CFD audit
print("=== 2. TOWING & WIND TUNNEL AUDIT ===")
for name in ["mk2_towing_tank.fieldcraft", "mk2_wind_tunnel.fieldcraft"]:
    dd = decode_free_surface(ROOT / "cae/cfd" / name)
    s = dd["solid"]
    v = np.linalg.norm(dd["frames"][-1]["velocity"], axis=1) * 1000.0
    print(f"  {name}: cells={dd['grid']['cells']} solid={int((s>0).sum())} v_mean={v[s==0].mean():.2f} mm/s v_max={v[s==0].max():.2f} mm/s")
