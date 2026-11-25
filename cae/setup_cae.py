from pathlib import Path

old = Path(r"C:\Users\makim\.gemini\antigravity\scratch\bath-toy-boat")
new = Path(r"C:\Users\makim\.gemini\antigravity\scratch\bath-toy-boat-mk2")

# 1. verify_hydrostatics.py
s = (old / "cae/hydrostatics/verify_hydrostatics.py").read_text(encoding="utf-8")
s = s.replace("bath_boat.stl", "bath_boat_mk2.stl")
s = s.replace(
    'ev = json.loads(EVAL_PATH.read_text(encoding="utf-8"))',
    'ev = json.loads(EVAL_PATH.read_text(encoding="utf-8"))\n    ev = ev[0] if isinstance(ev, list) else ev',
)
s = s.replace("xs = np.arange(-76.0 + dx * 0.5, 76.0, dx)", "xs = np.arange(-80.0 + dx * 0.5, 90.0, dx)")
s = s.replace("ys = np.arange(-43.0 + dy * 0.5, 43.0, dy)", "ys = np.arange(-46.0 + dy * 0.5, 46.0, dy)")
s = s.replace("(tri_xmin[i] + 76.0)", "(tri_xmin[i] + 80.0)")
s = s.replace("(tri_xmax[i] + 76.0)", "(tri_xmax[i] + 80.0)")
s = s.replace("(tri_ymin[i] + 43.0)", "(tri_ymin[i] + 46.0)")
s = s.replace("(tri_ymax[i] + 43.0)", "(tri_ymax[i] + 46.0)")
s = s.replace("28.0 - d_eq", "27.0 - d_eq")
s = s.replace("おふろタグボート", "おふろレスキュー艇 Mk-II")
(new / "cae/hydrostatics/verify_hydrostatics.py").write_text(s, encoding="utf-8")

# 2. run_fea.py
s = (old / "cae/fea/run_fea.py").read_text(encoding="utf-8")
s = s.replace(
    "sup_keel = [n for n, (x, y, z) in nodes.items() if z <= 0.2 and abs(x) <= 40.0 and (abs(y) >= 23.5 or abs(y) <= 14.0)]",
    "sup_keel = [n for n, (x, y, z) in nodes.items() if z <= 0.2 and abs(x) <= 45.0 and (abs(y) >= 22.0 or abs(y) <= 13.5)]",
)
s = s.replace(
    "load_roof = [n for n, (x, y, z) in nodes.items() if z >= 39.8 and (-2.0 <= x <= 22.0) and abs(y) <= 18.0]",
    "load_roof = [n for n, (x, y, z) in nodes.items() if z >= 40.2 and (-4.0 <= x <= 30.0) and abs(y) <= 18.0]",
)
(new / "cae/fea/run_fea.py").write_text(s, encoding="utf-8")

# 3. run_float_sim.py
s = (old / "cae/cfd/run_float_sim.py").read_text(encoding="utf-8")
s = s.replace('{"min": [-96, -56, -12], "max": [96, 56, 0.0]}', '{"min": [-100, -58, -12], "max": [108, 58, 0.0]}')
s = s.replace('{"min": [-96, -56, 0.0], "max": [-74, 56, water_d]}', '{"min": [-100, -58, 0.0], "max": [-78, 58, water_d]}')
s = s.replace('{"min": [74, -56, 0.0], "max": [96, 56, water_d]}', '{"min": [88, -58, 0.0], "max": [108, 58, water_d]}')
s = s.replace('{"min": [-74, -56, 0.0], "max": [74, -41, water_d]}', '{"min": [-78, -58, 0.0], "max": [88, -44, water_d]}')
s = s.replace('{"min": [-74, 41, 0.0], "max": [74, 56, water_d]}', '{"min": [-78, 44, 0.0], "max": [88, 58, water_d]}')
s = s.replace('"min": [-96, -56, -12]', '"min": [-100, -58, -12]')
s = s.replace('"max": [96, 56, 32]', '"max": [108, 58, 32]')
s = s.replace("(X3 >= 24.0) & (X3 <= 56.0) & (np.abs(Y3) <= 24.0)", "(X3 >= 36.0) & (X3 <= 66.0) & (np.abs(Y3) <= 18.0)")
s = s.replace("(Z3 >= 17.5) & (Z3 <= 26.0) & (X3 >= -60.0) & (X3 <= -36.0)", "(Z3 >= 18.0) & (Z3 <= 26.0) & (X3 >= -62.0) & (X3 <= -38.0)")
s = s.replace("(X3 <= -80.0)", "(X3 <= -84.0)")
s = s.replace("おふろタグボート", "おふろレスキュー艇 Mk-II")
(new / "cae/cfd/run_float_sim.py").write_text(s, encoding="utf-8")
print("Prepared all 3 CAE scripts for Mk-II")
