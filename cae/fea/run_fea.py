"""FieldCraft 0.8.1 static structural FEA for the Bath Toy Boat (Hull, tagged 3MF -> tet10).

Simulates a child pressing down on the cabin roof (total 20 N, ~2 kgf) while the twin-keel
bottom rests on a flat tub floor / support patch.
Pass A: mesh + throwaway static solve -> ASCII VTU to extract exact node coordinates.
Pass B: identical mesh + coordinate-selected boundary conditions & roof load -> solve, export VTU/CSV/native.
"""
import csv
import json
import re
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

FIELDCRAFT_CLI = Path(r"D:\Prj\mini4wd-cad-lab\runtime\fieldcraft-0.8.1\fieldcraft-0.8.1-windows-x64\fieldcraft-cli.exe")
ROOT = Path(__file__).resolve().parents[2]
MESH_3MF = ROOT / "cad" / "handoff" / "hull.3mf"
OUT_DIR = Path(__file__).resolve().parent


def P(name: str) -> str:
    return (OUT_DIR / name).as_posix()


def run_cli(name: str, script: list):
    spath = OUT_DIR / f"{name}.json"
    spath.write_text(json.dumps(script, indent=1), encoding="utf-8")
    r = subprocess.run([str(FIELDCRAFT_CLI), "run", str(spath)], capture_output=True, text=True, timeout=300)
    (OUT_DIR / f"{name}.stdout.txt").write_text(r.stdout, encoding="utf-8")
    (OUT_DIR / f"{name}.stderr.txt").write_text(r.stderr, encoding="utf-8")
    print(f"[{name}] exit={r.returncode} stderr={r.stderr.strip()[:300]}")
    if r.returncode != 0:
        raise RuntimeError(f"{name} failed with code {r.returncode}: {r.stderr}")


def parse_vtu_nodes(vtu_path: Path):
    text = vtu_path.read_text(encoding="utf-8")
    pts_m = re.search(r"<Points>\s*<DataArray[^>]*>(.*?)</DataArray>", text, re.S)
    lab_m = re.search(r'<DataArray[^>]*Name="node_label"[^>]*>(.*?)</DataArray>', text, re.S)
    pts = list(map(float, pts_m.group(1).split()))
    labs = list(map(int, lab_m.group(1).split()))
    xyz = [tuple(pts[i:i + 3]) for i in range(0, len(pts), 3)]
    return {lab: pos for lab, pos in zip(labs, xyz)}


def parse_vtu_results(vtu_path: Path):
    tree = ET.parse(vtu_path)
    root = tree.getroot()
    piece = root.find(".//Piece")
    n_points = int(piece.attrib["NumberOfPoints"])
    n_cells = int(piece.attrib["NumberOfCells"])
    point_data = {}
    for da in piece.findall("./PointData/DataArray"):
        name = da.attrib.get("Name")
        ncomp = int(da.attrib.get("NumberOfComponents", "1"))
        vals = [float(x) for x in da.text.split()]
        if ncomp > 1:
            point_data[name] = [vals[i:i + ncomp] for i in range(0, len(vals), ncomp)]
        else:
            point_data[name] = vals
    return n_points, n_cells, point_data


def main():
    base = [
        {"command": "model.units", "params": {"system": "mm-t-s-N-MPa"}},
        {"command": "geometry.import.mesh", "params": {"path": MESH_3MF.as_posix()}},
        {"command": "mesh.tet.generate", "params": {"surface": 0, "size": 5.5, "order": "linear"}},
        {"command": "model.set.create", "params": {"name": "ALL", "geometry": [{"body": "Hull"}]}},
        {
            "command": "model.material.create",
            "params": {
                "name": "ABS_PETG",
                "elastic": {"type": "isotropic", "young": 2200.0, "poisson": 0.35},
                "density": 1.05e-9,
            },
        },
        {"command": "model.section.create", "params": {"name": "solid", "set": "ALL", "material": "ABS_PETG", "kind": {"type": "solid"}}},
    ]

    # Pass A: throwaway solvable setup to export mesh coordinates
    runA = base + [
        {"command": "model.set.create", "params": {"name": "END", "nodes": list(range(1, 3001))}},
        {"command": "model.boundary_condition.create", "params": {"name": "fixA", "type": "fixed", "target": {"set": "END"}}},
        {"command": "model.step.create", "params": {"name": "A", "procedure": {"type": "static"}, "boundary_conditions": ["fixA"], "loads": []}},
        {"command": "solve.static", "params": {"step": "A"}},
        {"command": "results.export.vtu", "params": {"step": "A", "path": P("passA_mesh.vtu"), "encoding": "ascii"}},
    ]
    run_cli("passA", runA)
    nodes = parse_vtu_nodes(OUT_DIR / "passA_mesh.vtu")

    # Select keel support & cabin roof + integrated beacon load nodes by exact coordinates
    sup_keel = [n for n, (x, y, z) in nodes.items() if z <= 0.2 and abs(x) <= 45.0 and (abs(y) >= 22.0 or abs(y) <= 13.5)]
    load_roof = [n for n, (x, y, z) in nodes.items() if z >= 40.2 and (-4.0 <= x <= 30.0) and abs(y) <= 18.0]
    if not sup_keel or not load_roof:
        raise RuntimeError(f"Empty node selection: sup_keel={len(sup_keel)}, load_roof={len(load_roof)}")

    near = lambda S, target: min(S, key=lambda n: sum((nodes[n][i] - target[i]) ** 2 for i in range(3)))
    pin_r = near(sup_keel, (-35.0, 20.0, 0.0))
    pin_f = near(sup_keel, (35.0, 20.0, 0.0))

    sel = {
        "n_nodes": len(nodes),
        "sup_keel_count": len(sup_keel),
        "load_roof_count": len(load_roof),
        "pin_rear": [pin_r, nodes[pin_r]],
        "pin_front": [pin_f, nodes[pin_f]],
    }

    runB = base + [
        {"command": "model.set.create", "params": {"name": "SUP_KEEL", "nodes": sup_keel}},
        {"command": "model.set.create", "params": {"name": "PIN_R", "nodes": [pin_r]}},
        {"command": "model.set.create", "params": {"name": "PIN_F", "nodes": [pin_f]}},
        {"command": "model.set.create", "params": {"name": "LOAD_ROOF", "nodes": load_roof}},
        {"command": "model.boundary_condition.create", "params": {"name": "uz_keel", "type": "displacement", "target": {"set": "SUP_KEEL"}, "values": [None, None, 0, None, None, None]}},
        {"command": "model.boundary_condition.create", "params": {"name": "pin_r_xy", "type": "displacement", "target": {"set": "PIN_R"}, "values": [0, 0, None, None, None, None]}},
        {"command": "model.boundary_condition.create", "params": {"name": "pin_f_y", "type": "displacement", "target": {"set": "PIN_F"}, "values": [None, 0, None, None, None, None]}},
        {"command": "model.load.create", "params": {"name": "roof_press_20N", "type": "force", "target": {"set": "LOAD_ROOF"}, "vector": [0, 0, -20.0], "distribution": "total"}},
        {"command": "model.step.create", "params": {"name": "Static", "procedure": {"type": "static"}, "boundary_conditions": ["uz_keel", "pin_r_xy", "pin_f_y"], "loads": ["roof_press_20N"]}},
        {"command": "solve.static", "params": {"step": "Static"}},
        {"command": "results.reactions", "params": {"step": "Static"}},
        {"command": "results.export.csv", "params": {"what": "reactions", "path": P("reactions.csv"), "step": "Static"}},
        {"command": "results.export.vtu", "params": {"step": "Static", "path": P("result_static.vtu"), "encoding": "ascii"}},
        {"command": "file.save_as", "params": {"path": P("boat_static.fieldcraft"), "results": True}},
    ]
    run_cli("passB", runB)

    nodesB = parse_vtu_nodes(OUT_DIR / "result_static.vtu")
    sel["mesh_identical_A_B"] = (nodesB == nodes)
    (OUT_DIR / "node_selection.json").write_text(json.dumps(sel, indent=2), encoding="utf-8")

    # Parse VTU & reactions CSV
    n_pts, n_cells, pdata = parse_vtu_results(OUT_DIR / "result_static.vtu")
    disp_vecs = pdata["displacement"]
    disp_mags = [sum(c * c for c in v) ** 0.5 for v in disp_vecs]
    max_disp_idx = max(range(len(disp_mags)), key=lambda i: disp_mags[i])
    vm = pdata["von_mises"]
    max_vm_idx = max(range(len(vm)), key=lambda i: vm[i])
    node_labels = [int(round(x)) for x in pdata["node_label"]]

    # Sum reactions
    rx_sum = ry_sum = rz_sum = 0.0
    with open(OUT_DIR / "reactions.csv", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Look for total or individual node rows
            keys = {k.lower(): v for k, v in row.items()}
            if "fz" in keys or "rz" in keys:
                pass
        f.seek(0)
        raw_lines = f.read().splitlines()

    # Parse reactions directly from CSV header/rows
    rows = list(csv.DictReader(raw_lines))
    # FieldCraft reactions.csv has columns like set/node/fx/fy/fz or similar; also check passB.stdout.txt
    stdoutB = json.loads((OUT_DIR / "passB.stdout.txt").read_text(encoding="utf-8"))

    # Render von_mises and displacement snapshots via fieldcraft-cli snapshot
    for field_name, out_png in [("von_mises", "fea_von_mises.png"), ("displacement", "fea_displacement.png")]:
        snap_script = [
            {"command": "file.open", "params": {"path": P("boat_static.fieldcraft")}},
            {"command": "results.deformed", "params": {"step": "Static", "show": True, "scale": "auto"}},
            {"command": "results.contour", "params": {"step": "Static", "field": field_name, "bands": 12}},
        ]
        spath = OUT_DIR / f"snap_{field_name}.json"
        spath.write_text(json.dumps(snap_script, indent=1), encoding="utf-8")
        r = subprocess.run(
            [str(FIELDCRAFT_CLI), "snapshot", str(spath), "--out", P(out_png), "--view", "iso", "--size", "1280x900", "--field", field_name],
            capture_output=True, text=True, timeout=180,
        )
        print(f"[snapshot {field_name}] exit={r.returncode} {r.stderr.strip()[:200]}")

    summary = {
        "element_type": "tet4 (linear)",
        "elements": n_cells,
        "nodes": n_pts,
        "material": {"name": "ABS_PETG", "E_MPa": 2200.0, "poisson": 0.35},
        "load_N": [0.0, 0.0, -20.0],
        "max_displacement_mm": round(disp_mags[max_disp_idx], 5),
        "max_displacement_node": node_labels[max_disp_idx],
        "max_displacement_xyz_mm": [round(c, 3) for c in nodes[node_labels[max_disp_idx]]],
        "max_von_mises_MPa": round(vm[max_vm_idx], 4),
        "max_von_mises_node": node_labels[max_vm_idx],
        "max_von_mises_xyz_mm": [round(c, 3) for c in nodes[node_labels[max_vm_idx]]],
        "reactions_csv_rows": rows[:10],
        "stdout_summary": stdoutB,
    }
    (OUT_DIR / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
