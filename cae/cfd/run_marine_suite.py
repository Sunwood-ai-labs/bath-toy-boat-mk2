"""Full Naval-Architecture FieldCraft 0.8.1 CFD Suite for Bath Toy Boat Mk-II:
1. Towing Tank Hydrodynamic Drag CFD (water flow past V-bow hull)
2. Superstructure Wind Tunnel Aerodynamic CFD (air flow over stealth bridge & aero funnel)
3. Internal Chimney-to-Turbine Jet Flow CFD (free-surface water poured into funnel -> elbow -> jet -> stern bay)
"""
import json
import subprocess
import sys
from pathlib import Path
import numpy as np

FIELDCRAFT_CLI = Path(r"D:\Prj\mini4wd-cad-lab\runtime\fieldcraft-0.8.1\fieldcraft-0.8.1-windows-x64\fieldcraft-cli.exe")
ROOT = Path(r"C:\Users\makim\.gemini\antigravity\scratch\bath-toy-boat-mk2")
MESH_3MF = ROOT / "cad" / "handoff" / "hull.3mf"
OUT_DIR = ROOT / "cae" / "cfd"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(OUT_DIR))
from run_float_sim import decode_free_surface


def run_fc(name: str, script: list, timeout: int = 300):
    spath = OUT_DIR / f"script_{name}.json"
    spath.write_text(json.dumps(script, indent=1), encoding="utf-8")
    r = subprocess.run([str(FIELDCRAFT_CLI), "run", str(spath)], capture_output=True, text=True, timeout=timeout)
    (OUT_DIR / f"stdout_{name}.txt").write_text(r.stdout, encoding="utf-8")
    (OUT_DIR / f"stderr_{name}.txt").write_text(r.stderr, encoding="utf-8")
    print(f"[{name}] exit={r.returncode} stderr={r.stderr.strip()[:280]}")
    if r.returncode != 0:
        raise RuntimeError(f"{name} failed: {r.stderr}")


def run_towing_tank():
    """1. Hydrodynamic Towing Tank CFD (Water U = 4.0 mm/s)."""
    fc_path = OUT_DIR / "mk2_towing_tank.fieldcraft"
    speed = 4.0  # mm/s
    script = [
        {"command": "model.units", "params": {"system": "mm-t-s-N-MPa"}},
        {"command": "geometry.import.mesh", "params": {"path": MESH_3MF.as_posix()}},
        {
            "command": "model.material.create",
            "params": {
                "name": "BathWater",
                "density": 1.0e-9,
                "fluid": {"type": "newtonian", "viscosity": 1.0e-9},
            },
        },
        {
            "command": "model.fluid_domain.create",
            "params": {
                "name": "TowingTank",
                "material": "BathWater",
                "min": [-140, -75, 0],
                "max": [130, 75, 35],
                "spacing": 2.5,
                "obstacles": ["Hull"],
                "initial_velocity": [-speed, 0, 0],
                "faces": {
                    "x_max": {"type": "velocity", "velocity": [-speed, 0, 0], "profile": "uniform"},
                    "x_min": {"type": "pressure", "pressure": 0, "outflow": "convective"},
                    "y_min": {"type": "slip"},
                    "y_max": {"type": "slip"},
                    "z_min": {"type": "slip"},
                    "z_max": {"type": "slip"},
                },
            },
        },
        {
            "command": "model.step.create",
            "params": {
                "name": "Towing",
                "procedure": {
                    "type": "fluid",
                    "domain": "TowingTank",
                    "collision": "hrr",
                    "end_time": 10.0,
                    "frames": 20,
                },
            },
        },
        {"command": "solve.fluid", "params": {"step": "Towing", "backend": "cpu", "threads": 4}},
        {"command": "file.save_as", "params": {"path": fc_path.as_posix(), "results": True}},
    ]
    run_fc("towing_tank", script)
    d = decode_free_surface(fc_path)
    last = d["frames"][-1]
    vmag = np.linalg.norm(last["velocity"], axis=1)
    fvals = d["forces"][0]["values"] if d["forces"] else np.zeros((1, 3))
    n_tail = max(1, len(fvals) // 4)
    return {
        "speed_mm_s": speed,
        "grid_cells": d["grid"]["cells"],
        "max_speed_mm_s": round(float(vmag.max()) * 1000.0, 3),
        "drag_uN_mean_tail": round(float(-np.mean(fvals[-n_tail:, 0])) * 1e6, 2),
        "side_force_uN_mean_tail": round(float(np.mean(fvals[-n_tail:, 1])) * 1e6, 2),
    }


def run_wind_tunnel():
    """2. Superstructure Aerodynamic Wind Tunnel CFD (Air U = 60.0 mm/s above waterline Z=11mm)."""
    fc_path = OUT_DIR / "mk2_wind_tunnel.fieldcraft"
    speed = 60.0  # mm/s
    script = [
        {"command": "model.units", "params": {"system": "mm-t-s-N-MPa"}},
        {"command": "geometry.import.mesh", "params": {"path": MESH_3MF.as_posix()}},
        {
            "command": "model.material.create",
            "params": {
                "name": "Air20C",
                "density": 1.225e-12,
                "fluid": {"type": "newtonian", "viscosity": 1.81e-11},
            },
        },
        {
            "command": "model.fluid_domain.create",
            "params": {
                "name": "WindTunnel",
                "material": "Air20C",
                "min": [-140, -75, 11],
                "max": [130, 75, 92],
                "spacing": 3.0,
                "obstacles": ["Hull"],
                "initial_velocity": [-speed, 0, 0],
                "faces": {
                    "x_max": {"type": "velocity", "velocity": [-speed, 0, 0], "profile": "uniform"},
                    "x_min": {"type": "pressure", "pressure": 0, "outflow": "convective"},
                    "y_min": {"type": "slip"},
                    "y_max": {"type": "slip"},
                    "z_min": {"type": "slip"},
                    "z_max": {"type": "slip"},
                },
            },
        },
        {
            "command": "model.step.create",
            "params": {
                "name": "WindTunnel",
                "procedure": {
                    "type": "fluid",
                    "domain": "WindTunnel",
                    "collision": "hrr",
                    "end_time": 1.2,
                    "frames": 20,
                },
            },
        },
        {"command": "solve.fluid", "params": {"step": "WindTunnel", "backend": "cpu", "threads": 4}},
        {"command": "file.save_as", "params": {"path": fc_path.as_posix(), "results": True}},
    ]
    run_fc("wind_tunnel", script)
    d = decode_free_surface(fc_path)
    last = d["frames"][-1]
    vmag = np.linalg.norm(last["velocity"], axis=1)
    fvals = d["forces"][0]["values"] if d["forces"] else np.zeros((1, 3))
    n_tail = max(1, len(fvals) // 4)
    return {
        "wind_speed_mm_s": speed,
        "grid_cells": d["grid"]["cells"],
        "max_air_speed_mm_s": round(float(vmag.max()) * 1000.0, 2),
        "aero_drag_uN_mean_tail": round(float(-np.mean(fvals[-n_tail:, 0])) * 1e6, 4),
        "aero_lift_uN_mean_tail": round(float(np.mean(fvals[-n_tail:, 2])) * 1e6, 4),
    }


def run_jet_turbine():
    """3. Free-surface water poured into chimney funnel -> 90-deg elbow -> jet nozzle -> turbine bay."""
    fc_path = OUT_DIR / "mk2_jet_turbine.fieldcraft"
    # Water column filling funnel + vertical bore + elbow so hydrostatic head drives jet into turbine bay
    liquid_boxes = [
        {"min": [-26.5, -8.5, 48.0], "max": [-9.5, 8.5, 65.0]},
        {"min": [-23.0, -5.0, 17.0], "max": [-13.0, 5.0, 52.0]},
        {"min": [-34.0, -5.0, 17.0], "max": [-18.0, 5.0, 26.5]},
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
                "name": "JetChannel",
                "material": "BathWater",
                "min": [-84, -24, 15],
                "max": [0, 24, 66],
                "spacing": 1.5,
                "obstacles": ["Hull"],
                "acceleration": [0.0, 0.0, -9810.0],
                "free_surface": {"liquid": liquid_boxes},
            },
        },
        {
            "command": "model.step.create",
            "params": {
                "name": "JetFlow",
                "procedure": {
                    "type": "fluid",
                    "domain": "JetChannel",
                    "collision": "hrr",
                    "steps": 3200,
                    "frames": 32,
                },
            },
        },
        {"command": "solve.fluid", "params": {"step": "JetFlow", "backend": "cpu", "threads": 4}},
        {"command": "file.save_as", "params": {"path": fc_path.as_posix(), "results": True}},
    ]
    run_fc("jet_turbine", script)
    d = decode_free_surface(fc_path)
    g = d["grid"]
    nx, ny, nz = g["cells"]
    dx_mm = float(g["spacing"]) * 1000.0
    o_mm = np.array(g["origin"]) * 1000.0
    xs = o_mm[0] + (np.arange(nx) + 0.5) * dx_mm
    ys = o_mm[1] + (np.arange(ny) + 0.5) * dx_mm
    zs = o_mm[2] + (np.arange(nz) + 0.5) * dx_mm
    Z3, Y3, X3 = np.meshgrid(zs, ys, xs, indexing="ij")
    bay_mask = (X3 <= -34.0) & (X3 >= -66.0) & (np.abs(Y3) <= 16.0) & (Z3 >= 17.0)
    peak_jet_speed = 0.0
    max_bay_fill = 0.0
    for fr in d["frames"]:
        f3 = fr["fill"].reshape((nz, ny, nx))
        v3 = np.linalg.norm(fr["velocity"], axis=1).reshape((nz, ny, nx)) * 1000.0
        wet_bay = bay_mask & (f3 > 0.3)
        if np.any(wet_bay):
            peak_jet_speed = max(peak_jet_speed, float(v3[wet_bay].max()))
            max_bay_fill = max(max_bay_fill, float(f3[bay_mask].mean()))
    return {
        "grid_cells": g["cells"],
        "frames": len(d["frames"]),
        "final_time_ms": round(d["frames"][-1]["time"] * 1000.0, 2),
        "peak_jet_speed_in_turbine_bay_mm_s": round(peak_jet_speed, 1),
        "mean_turbine_bay_water_fill": round(max_bay_fill, 4),
    }


def main():
    summary = {}
    print("=== 1/3 Towing Tank Hydrodynamic CFD ===")
    summary["towing_tank"] = run_towing_tank()
    print("=== 2/3 Superstructure Wind Tunnel CFD ===")
    summary["wind_tunnel"] = run_wind_tunnel()
    print("=== 3/3 Chimney-to-Turbine Internal Jet CFD ===")
    summary["jet_turbine"] = run_jet_turbine()

    out_json = OUT_DIR / "marine_cfd_suite_summary.json"
    out_json.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print("=== ALL 3 FIELDCRAFT CFD SIMULATIONS COMPLETE ===")
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
