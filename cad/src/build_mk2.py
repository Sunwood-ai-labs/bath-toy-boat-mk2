import json
import math
from pathlib import Path

ROOT = Path(r"C:\Users\makim\.gemini\antigravity\scratch\bath-toy-boat-mk2")
OUT_DIR = ROOT / "cad" / "out"
HANDOFF_DIR = ROOT / "cad" / "handoff"
SRC_DIR = ROOT / "cad" / "src"

def p(x, y):
    return [round(float(x), 4), round(float(y), 4)]

def make_hull_profile(bow_x, bow_tip_y, fwd_x, fwd_y, mid_x, max_y, stern_x, stern_y, stern_tip_x):
    """Symmetric 10-point speed-boat / rescue-cruiser planform (CCW)."""
    return [
        p(bow_x, bow_tip_y),
        p(fwd_x, fwd_y),
        p(mid_x, max_y),
        p(stern_x, stern_y),
        p(stern_tip_x, stern_y - 4.0),
        p(stern_tip_x, -(stern_y - 4.0)),
        p(stern_x, -stern_y),
        p(mid_x, -max_y),
        p(fwd_x, -fwd_y),
        p(bow_x, -bow_tip_y),
    ]

def add_loft_body(cmds, name_prefix, sections_z_pts, body_name, operation=None, sketch_registry=None):
    """Create XY sketches at given Z heights and loft piecewise linearly (2 sections per loft)
    so every side face is a clean ruled/planar face (zero rational-spline tessellation issues)."""
    sk_names = []
    for idx, (z, pts) in enumerate(sections_z_pts):
        sk_name = f"{name_prefix}_sk_{idx}"
        cmds.append({
            "command": "sketch.create",
            "params": {
                "plane": {"origin": [0, 0, round(float(z), 4)], "x_dir": [1, 0, 0], "y_dir": [0, 1, 0]},
                "name": sk_name
            }
        })
        cmds.append({
            "command": "sketch.line",
            "params": {
                "points": pts,
                "closed": True
            }
        })
        cmds.append({"command": "sketch.finish"})
        sk_names.append(sk_name)
        if sketch_registry is not None:
            sketch_registry.append(sk_name)

    if len(sk_names) == 2:
        loft_params = {
            "sections": [{"sketch": sk_names[0]}, {"sketch": sk_names[1]}],
            "body_name": body_name
        }
        if operation:
            loft_params["operation"] = operation
        cmds.append({"command": "solid.loft", "params": loft_params})
    else:
        seg_names = []
        for idx in range(len(sk_names) - 1):
            seg_body = body_name if idx == 0 else f"{body_name}_seg_{idx}"
            cmds.append({
                "command": "solid.loft",
                "params": {
                    "sections": [{"sketch": sk_names[idx]}, {"sketch": sk_names[idx + 1]}],
                    "body_name": seg_body
                }
            })
            seg_names.append(seg_body)
        cmds.append({
            "command": "solid.combine",
            "params": {
                "target": seg_names[0],
                "tools": seg_names[1:],
                "operation": "join"
            }
        })


def build_commands(hull_only=False):
    cmds = []

    # Key parameters
    params = [
        ("floor_t", "3.5", "軽量バスタブ底厚 mm"),
        ("spinner_x", "14.0", "PIPレーダーターレット中心X mm"),
        ("chimney_x", "-18.0", "メイン注水ファネル中心X mm"),
        ("wheel_x", "-50.0", "PIP 6枚羽根ハイドロタービン中心X mm"),
        ("wheel_floor_z", "17.0", "高床タービンベイ・スピルウェイ浸水限界高さZ mm"),
        ("jet_z", "21.5", "ジェットノズル中心Z mm（上端26.0mmでZ=27mm天板と1.0mm肉厚確保）"),
    ]
    for name, expr, comment in params:
        cmds.append({
            "command": "parameters.add",
            "params": {"name": name, "expression": expr, "comment": comment}
        })

    # =========================================================================
    # 1. OUTER HULL: Stepped-Chine Flared Rescue Cruiser (160mm x 84mm x 27mm)
    #    All overhang angles <= 32 deg -> 100% support-free!
    # =========================================================================
    # Z=0 (keel flat): X=[-72, +71], Y=±33 (width 66)
    # Z=12 (chine):    X=[-75, +78], Y=±39 (width 78)  -> dY=6/12 (26.6 deg), dX_bow=7/12 (30.3 deg)
    # Z=27 (gunwale):  X=[-76, +84], Y=±42 (width 84)  -> dY=3/15 (11.3 deg), dX_bow=6/15 (21.8 deg)
    hull_outer_sections = [
        (0.0,  make_hull_profile(71.0, 5.5, 42.0, 27.5,  2.0, 33.0, -64.0, 30.0, -72.0)),
        (12.0, make_hull_profile(78.0, 6.5, 46.0, 33.5,  2.0, 39.0, -67.0, 35.5, -75.0)),
        (27.0, make_hull_profile(84.0, 7.5, 49.0, 36.5,  2.0, 42.0, -68.0, 38.0, -76.0)),
    ]
    add_loft_body(cmds, "HullOuter", hull_outer_sections, "Hull")

    # Side rub-rail / rescue bumper strake (Z=21.5 -> 24.5 -> 27.0, slight flare <= 35 deg)
    bumper_sections = [
        (21.5, make_hull_profile(81.5, 7.2, 47.8, 35.5,  2.0, 41.0, -67.6, 37.2, -75.6)),
        (24.5, make_hull_profile(85.0, 7.8, 50.0, 38.0,  2.0, 43.8, -68.5, 39.6, -76.5)),
        (27.0, make_hull_profile(84.0, 7.5, 49.0, 36.5,  2.0, 42.0, -68.0, 38.0, -76.0)),
    ]
    add_loft_body(cmds, "SideBumper", bumper_sections, "Side_Bumper")

    # High Bow Bulwark (Sheer wave-breaker: Z=26.5 -> 34.5, swept back along front)
    bow_bulwark_sections = [
        (26.5, make_hull_profile(84.0, 7.5, 49.0, 36.5,  2.0, 42.0, -68.0, 38.0, -76.0)),
        (34.5, make_hull_profile(87.0, 8.0, 50.5, 37.5,  2.0, 42.5, -68.0, 38.0, -76.0)),
    ]
    add_loft_body(cmds, "BowBulwark", bow_bulwark_sections, "Bow_Bulwark")

    # Cut aft portion of Bow_Bulwark with an angled sheer line (sweeping down from X=28 to X=6)
    # Bottom at Z=25.5 so nothing remains below Z=27 behind X=24
    cmds.append({
        "command": "solid.box",
        "params": {
            "length": "140",
            "width": "100",
            "height": "22",
            "center": ["-46", "0", "36.5"],
            "body_name": "Bulwark_AftCut"
        }
    })
    # Angled sheer ramp transition (X=24..44)
    cmds.append({
        "command": "solid.box",
        "params": {
            "length": "40",
            "width": "100",
            "height": "20",
            "center": ["30", "0", "40"],
            "body_name": "Bulwark_RampCut"
        }
    })
    cmds.append({
        "command": "solid.move",
        "params": {
            "bodies": ["Bulwark_RampCut"],
            "axis": [0, 1, 0],
            "angle": "-24 deg",
            "origin": ["24", "0", "27"]
        }
    })
    cmds.append({
        "command": "solid.combine",
        "params": {
            "target": "Bow_Bulwark",
            "tools": ["Bulwark_AftCut", "Bulwark_RampCut"],
            "operation": "cut"
        }
    })

    # Join bumper & bow bulwark to Hull
    cmds.append({
        "command": "solid.combine",
        "params": {
            "target": "Hull",
            "tools": ["Side_Bumper", "Bow_Bulwark"],
            "operation": "join"
        }
    })

    # =========================================================================
    # 2. HOLLOW BATHTUB INTERIOR (Thin-wall 3.5mm floor, ~4.2mm sides -> huge buoyancy!)
    # =========================================================================
    tub_sections = [
        (3.5,  make_hull_profile(65.5, 3.8, 39.5, 24.5,  2.0, 29.8, -60.5, 26.8, -68.0)),
        (12.0, make_hull_profile(72.0, 4.5, 43.0, 29.5,  2.0, 34.8, -63.0, 31.3, -70.5)),
        (27.0, make_hull_profile(78.0, 5.2, 46.0, 32.3,  2.0, 37.8, -64.0, 33.8, -71.5)),
        (36.0, make_hull_profile(81.5, 5.8, 47.5, 33.5,  2.0, 38.5, -64.0, 34.0, -71.5)),
    ]
    add_loft_body(cmds, "TubCut", tub_sections, "Tub_Cut")

    # Twin side keel grooves on bottom (Z=0..1.5) for straight tracking & style
    for side, yval in [("L", "18"), ("R", "-18")]:
        cmds.append({
            "command": "solid.box",
            "params": {
                "length": "88",
                "width": "7.5",
                "height": "2.0",
                "center": ["-4", yval, "0.5"],
                "body_name": f"Keel_Groove_{side}"
            }
        })

    cmds.append({
        "command": "solid.combine",
        "params": {
            "target": "Hull",
            "tools": ["Tub_Cut", "Keel_Groove_L", "Keel_Groove_R"],
            "operation": "cut"
        }
    })

    # =========================================================================
    # 3. STERN TWIN-PONTOON TURBINE POD (Clipped cleanly to Hull outer envelope)
    # =========================================================================
    # Outer envelope copy for clean intersection
    env_sections = [
        (0.0,  make_hull_profile(71.0, 5.5, 42.0, 27.5,  2.0, 33.0, -64.0, 30.0, -72.0)),
        (12.0, make_hull_profile(78.0, 6.5, 46.0, 33.5,  2.0, 39.0, -67.0, 35.5, -75.0)),
        (27.0, make_hull_profile(84.0, 7.5, 49.0, 36.5,  2.0, 42.0, -68.0, 38.0, -76.0)),
    ]
    add_loft_body(cmds, "HullEnv", env_sections, "Hull_Env")

    # Raised central turbine deck + sleek tapered twin side cowls (Z=0..27)
    stern_pod_sections = [
        (0.0,  [p(-26, 21), p(-76, 21), p(-76, -21), p(-26, -21)]),
        (17.0, [p(-26, 22), p(-76, 22), p(-76, -22), p(-26, -22)]),
        (27.0, [p(-28, 21), p(-76, 21), p(-76, -21), p(-28, -21)]),
    ]
    add_loft_body(cmds, "SternPod", stern_pod_sections, "Stern_Pod")

    # Twin sporty stern deck fins / cowls flanking the turbine bay (Z=26.5..31.5, tapered)
    for side, sgn in [("L", 1), ("R", -1)]:
        y_in = 16.5 * sgn
        y_out = 21.5 * sgn
        fin_pts_bot = [p(-30, y_in), p(-70, y_in), p(-74, y_out), p(-34, y_out)] if sgn > 0 else [p(-34, y_out), p(-74, y_out), p(-70, y_in), p(-30, y_in)]
        y_in2 = 17.5 * sgn
        y_out2 = 20.5 * sgn
        fin_pts_top = [p(-36, y_in2), p(-66, y_in2), p(-69, y_out2), p(-39, y_out2)] if sgn > 0 else [p(-39, y_out2), p(-69, y_out2), p(-66, y_in2), p(-36, y_in2)]
        add_loft_body(cmds, f"SternFin_{side}", [(26.5, fin_pts_bot), (31.5, fin_pts_top)], f"Stern_Fin_{side}")

    cmds.append({
        "command": "solid.combine",
        "params": {
            "target": "Stern_Pod",
            "tools": ["Hull_Env"],
            "operation": "intersect"
        }
    })

    # =========================================================================
    # 4. AERO COMMAND BRIDGE (Sleek raked stealth cabin + visor roof!)
    # =========================================================================
    # Raked front cabin: X=[-4, +40] at base (Z=3.5) tapering to X=[-4, +30] at Z=36.0
    # Overhang/slope: front leans BACK (super easy to print!), sides lean slightly IN.
    cabin_sections = [
        (3.5, [
            p(42.0, 8.0), p(30.0, 21.0), p(-4.0, 22.0),
            p(-4.0, -22.0), p(30.0, -21.0), p(42.0, -8.0)
        ]),
        (25.0, [
            p(37.0, 7.5), p(26.0, 20.0), p(-4.0, 21.0),
            p(-4.0, -21.0), p(26.0, -20.0), p(37.0, -7.5)
        ]),
        (36.0, [
            p(31.0, 7.0), p(22.0, 18.0), p(-4.0, 19.0),
            p(-4.0, -19.0), p(22.0, -18.0), p(31.0, -7.0)
        ]),
    ]
    add_loft_body(cmds, "CabinMain", cabin_sections, "Cabin_Main")

    # Visor Roof: 45-deg self-supporting flare outward from Z=35.5 -> 38.0 -> 40.5!
    roof_sections = [
        (35.5, [
            p(31.2, 7.0), p(22.2, 18.0), p(-4.0, 19.0),
            p(-4.0, -19.0), p(22.2, -18.0), p(31.2, -7.0)
        ]),
        (38.0, [
            p(34.0, 7.8), p(24.5, 20.5), p(-5.5, 21.5),
            p(-5.5, -21.5), p(24.5, -20.5), p(34.0, -7.8)
        ]),
        (40.5, [
            p(32.5, 7.2), p(23.5, 19.5), p(-5.0, 20.5),
            p(-5.0, -20.5), p(23.5, -19.5), p(32.5, -7.2)
        ]),
    ]
    add_loft_body(cmds, "CabinRoof", roof_sections, "Cabin_Roof")

    # =========================================================================
    # 5. AERO FUNNEL & ENGINE COWL (Integrated supercharger-style stack)
    # =========================================================================
    # Sleek tapered engine spine connecting cabin (X=-4) to stern pod (X=-32)
    spine_sections = [
        (3.5,  [p(-2.0, 14.0), p(-31.0, 13.0), p(-31.0, -13.0), p(-2.0, -14.0)]),
        (28.0, [p(-2.0, 13.0), p(-31.0, 11.5), p(-31.0, -11.5), p(-2.0, -13.0)]),
        (36.0, [p(-3.0, 10.5), p(-28.0,  9.5), p(-28.0,  -9.5), p(-3.0, -10.5)]),
    ]
    add_loft_body(cmds, "EngineSpine", spine_sections, "Engine_Spine")

    # Aero Funnel Shroud (raked sporty housing around the main vertical water funnel)
    funnel_shroud_sections = [
        (32.0, [p(-6.0, 10.5), p(-28.0, 10.0), p(-30.0, 5.0), p(-30.0, -5.0), p(-28.0, -10.0), p(-6.0, -10.5)]),
        (51.0, [p(-9.0,  9.5), p(-26.5,  9.0), p(-28.5, 4.5), p(-28.5, -4.5), p(-26.5,  -9.0), p(-9.0,  -9.5)]),
    ]
    add_loft_body(cmds, "FunnelShroud", funnel_shroud_sections, "Funnel_Shroud")

    # Main vertical funnel barrel + flared yellow pouring crown (Z=51..60)
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "22.0",
            "height": "50.5",
            "base": ["chimney_x", "0", "floor_t"],
            "axis": "Z",
            "body_name": "Chimney_Outer"
        }
    })
    cmds.append({
        "command": "solid.cone",
        "params": {
            "diameter": "22.0",
            "top_diameter": "26.5",
            "height": "2.5",
            "base": ["chimney_x", "0", "51.5"],
            "axis": "Z",
            "body_name": "Chimney_Flare"
        }
    })
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "26.5",
            "height": "6.0",
            "base": ["chimney_x", "0", "54.0"],
            "axis": "Z",
            "body_name": "Chimney_Top"
        }
    })

    # Rescue Side Pods / Lifebuoy Mounts on left & right midship deck
    for side, yval in [("L", "26.5"), ("R", "-26.5")]:
        cmds.append({
            "command": "solid.cylinder",
            "params": {
                "diameter": "12.6",
                "height": "11.0",
                "base": ["-18", yval, "floor_t"],
                "axis": "Z",
                "body_name": f"Lifebuoy_Pad_{side}"
            }
        })
        cmds.append({
            "command": "solid.torus",
            "params": {
                "major": "4.2",
                "minor": "1.9",
                "center": ["-18", yval, "14.8"],
                "body_name": f"Lifebuoy_{side}"
            }
        })

    # Bow Bollard / Rescue Tow Post on foredeck (X=56, Z=3.5..24, rounded top)
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "10.0",
            "height": "18.5",
            "base": ["56", "0", "floor_t"],
            "axis": "Z",
            "body_name": "Bow_Bollard_Post"
        }
    })
    cmds.append({
        "command": "solid.cone",
        "params": {
            "diameter": "10.0",
            "top_diameter": "13.0",
            "height": "2.0",
            "base": ["56", "0", "21.5"],
            "axis": "Z",
            "body_name": "Bow_Bollard_Flare"
        }
    })
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "13.0",
            "height": "2.5",
            "base": ["56", "0", "23.5"],
            "axis": "Z",
            "body_name": "Bow_Bollard_Cap"
        }
    })

    # Join all superstructure onto Hull
    cmds.append({
        "command": "solid.combine",
        "params": {
            "target": "Hull",
            "tools": [
                "Stern_Pod", "Stern_Fin_L", "Stern_Fin_R",
                "Cabin_Main", "Cabin_Roof",
                "Engine_Spine", "Funnel_Shroud",
                "Chimney_Outer", "Chimney_Flare", "Chimney_Top",
                "Lifebuoy_Pad_L", "Lifebuoy_Pad_R", "Lifebuoy_L", "Lifebuoy_R",
                "Bow_Bollard_Post", "Bow_Bollard_Flare", "Bow_Bollard_Cap"
            ],
            "operation": "join"
        }
    })

    # =========================================================================
    # 6. CABIN INTERIOR, PANORAMA WINDOWS & WATERPROOF STANDPIPE
    # =========================================================================
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "26.0",
            "height": "20.5",
            "base": ["spinner_x", "0", "floor_t"],
            "axis": "Z",
            "body_name": "Cabin_Int_Cyl"
        }
    })
    cmds.append({
        "command": "solid.cone",
        "params": {
            "diameter": "26.0",
            "top_diameter": "8.4",
            "height": "9.0",
            "base": ["spinner_x", "0", "24.0"],
            "axis": "Z",
            "body_name": "Cabin_Int_Cone"
        }
    })
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "8.4",
            "height": "7.5",
            "base": ["spinner_x", "0", "32.5"],
            "axis": "Z",
            "body_name": "Cabin_Roof_Hole"
        }
    })
    cmds.append({
        "command": "solid.cone",
        "params": {
            "diameter": "8.4",
            "top_diameter": "13.4",
            "height": "2.5",
            "base": ["spinner_x", "0", "38.5"],
            "axis": "Z",
            "body_name": "Cabin_Roof_Flare"
        }
    })
    # Side rescue hatches (arched top -> support-free!)
    cmds.append({
        "command": "solid.box",
        "params": {
            "length": "14.0",
            "width": "50.0",
            "height": "17.5",
            "center": ["spinner_x", "0", "floor_t + 8.75"],
            "body_name": "Cabin_Door_Box"
        }
    })
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "14.0",
            "height": "50.0",
            "base": ["spinner_x", "-25.0", "21.0"],
            "axis": "Y",
            "body_name": "Cabin_Door_Arch"
        }
    })
    # Front bridge panorama window (twin circular/oval port cut)
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "12.0",
            "height": "34.0",
            "base": ["spinner_x", "0", "26.0"],
            "axis": "X",
            "body_name": "Window_Front_C"
        }
    })
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "8.5",
            "height": "34.0",
            "base": ["spinner_x", "7.0", "26.0"],
            "axis": "X",
            "body_name": "Window_Front_L"
        }
    })
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "8.5",
            "height": "34.0",
            "base": ["spinner_x", "-7.0", "26.0"],
            "axis": "X",
            "body_name": "Window_Front_R"
        }
    })

    cmds.append({
        "command": "solid.combine",
        "params": {
            "target": "Hull",
            "tools": [
                "Cabin_Int_Cyl", "Cabin_Int_Cone",
                "Cabin_Roof_Hole", "Cabin_Roof_Flare",
                "Cabin_Door_Box", "Cabin_Door_Arch",
                "Window_Front_C", "Window_Front_L", "Window_Front_R"
            ],
            "operation": "cut"
        }
    })

    # Waterproof Standpipe around Spinner Bearing (Z=0..18.0mm -> keeps cabin 100% dry!)
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "17.6",
            "height": "18.0",
            "base": ["spinner_x", "0", "0"],
            "axis": "Z",
            "body_name": "PS_Standpipe"
        }
    })
    cmds.append({
        "command": "solid.combine",
        "params": {
            "target": "Hull",
            "tools": ["PS_Standpipe"],
            "operation": "join"
        }
    })

    # =========================================================================
    # 7. BEARINGS, WATER JET CHANNEL & HIGH-FLOOR TURBINE BAY CUTS
    # =========================================================================
    # Front Spinner 45-deg Hourglass Bearing Bore (Z=0..18.0)
    cmds.append({
        "command": "solid.cone",
        "params": {
            "diameter": "15.0", "top_diameter": "7.0", "height": "4.0",
            "base": ["spinner_x", "0", "-0.5"], "axis": "Z", "body_name": "Hull_PS_Bot"
        }
    })
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "7.0", "height": "11.2",
            "base": ["spinner_x", "0", "3.4"], "axis": "Z", "body_name": "Hull_PS_Neck"
        }
    })
    cmds.append({
        "command": "solid.cone",
        "params": {
            "diameter": "7.0", "top_diameter": "14.0", "height": "3.5",
            "base": ["spinner_x", "0", "14.5"], "axis": "Z", "body_name": "Hull_PS_Top_Flare"
        }
    })

    # Chimney -> Elbow -> Water Jet Nozzle aiming at Turbine blades
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "9.0", "height": "38.0",
            "base": ["chimney_x", "0", "jet_z"], "axis": "Z", "body_name": "Chimney_Bore"
        }
    })
    cmds.append({
        "command": "solid.sphere",
        "params": {
            "diameter": "9.0", "center": ["chimney_x", "0", "jet_z"], "body_name": "Jet_Elbow"
        }
    })
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "9.0", "height": "18.0",
            "base": ["-36.0", "0", "jet_z"], "axis": "X", "body_name": "Jet_Nozzle"
        }
    })
    cmds.append({
        "command": "solid.cone",
        "params": {
            "diameter": "9.0", "top_diameter": "19.0", "height": "8.5",
            "base": ["chimney_x", "0", "52.0"], "axis": "Z", "body_name": "Chimney_Funnel_Cup"
        }
    })

    # High-floor Turbine Bay (Z=17.0..33.0, dia 32.0) + Stern Diffuser Spillway
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "32.0", "height": "16.0",
            "base": ["wheel_x", "0", "wheel_floor_z"], "axis": "Z", "body_name": "Wheel_Bay_Cut"
        }
    })
    cmds.append({
        "command": "solid.box",
        "params": {
            "length": "26.0", "width": "17.0", "height": "16.0",
            "center": ["-70.0", "0", "wheel_floor_z + 8.0"], "body_name": "Stern_Spillway_Box"
        }
    })

    # Rear Turbine 45-deg Hourglass Bearing Bore (Z=0..17.0)
    cmds.append({
        "command": "solid.cone",
        "params": {
            "diameter": "15.0", "top_diameter": "7.0", "height": "4.0",
            "base": ["wheel_x", "0", "-0.5"], "axis": "Z", "body_name": "Hull_WW_Bot"
        }
    })
    cmds.append({
        "command": "solid.cylinder",
        "params": {
            "diameter": "7.0", "height": "10.2",
            "base": ["wheel_x", "0", "3.4"], "axis": "Z", "body_name": "Hull_WW_Neck"
        }
    })
    cmds.append({
        "command": "solid.cone",
        "params": {
            "diameter": "7.0", "top_diameter": "14.0", "height": "3.5",
            "base": ["wheel_x", "0", "13.5"], "axis": "Z", "body_name": "Hull_WW_Top_Flare"
        }
    })

    cmds.append({
        "command": "solid.combine",
        "params": {
            "target": "Hull",
            "tools": [
                "Hull_PS_Bot", "Hull_PS_Neck", "Hull_PS_Top_Flare",
                "Chimney_Bore", "Jet_Elbow", "Jet_Nozzle", "Chimney_Funnel_Cup",
                "Wheel_Bay_Cut", "Stern_Spillway_Box",
                "Hull_WW_Bot", "Hull_WW_Neck", "Hull_WW_Top_Flare"
            ],
            "operation": "cut"
        }
    })

    # =========================================================================
    # 7b. SF DEVELOPMENT CODENAME DEBOSS ON HULL BOTTOM ("HRX-02 / AQUA-VANGUARD")
    #     Plane flipped (y_dir=[0,-1,0]) so text reads left-to-right when viewed from bottom!
    #     Depth = 0.6 mm into 3.5 mm floor -> 2.9 mm solid wall left (100% watertight, support-free)
    # =========================================================================
    cmds.append({
        "command": "sketch.create",
        "params": {
            "plane": {"origin": [0, 0, 0], "x_dir": [1, 0, 0], "y_dir": [0, -1, 0]},
            "name": "Bottom_Code_Sk"
        }
    })
    cmds.append({
        "command": "sketch.text",
        "params": {
            "text": "HRX-02",
            "at": [-15.0, 3.2],
            "height": 7.5,
            "font": "C:/Windows/Fonts/consolab.ttf",
            "align": "center",
            "vertical_align": "middle",
            "letter_spacing": 0.6
        }
    })
    cmds.append({
        "command": "sketch.text",
        "params": {
            "text": "AQUA-VANGUARD",
            "at": [-15.0, -4.4],
            "height": 3.6,
            "font": "C:/Windows/Fonts/consolab.ttf",
            "align": "center",
            "vertical_align": "middle",
            "letter_spacing": 0.25
        }
    })
    cmds.append({"command": "sketch.finish"})
    cmds.append({
        "command": "solid.extrude",
        "params": {
            "sketch": "Bottom_Code_Sk",
            "distance": "-0.6",
            "operation": "cut",
            "targets": ["Hull"]
        }
    })

    if not hull_only:
        # =====================================================================
        # 8. PIP BODY 2: COMMAND RADAR TURRET (6-spoke Stealth Helm + Radar Bar)
        #    Clearance to Hull = 0.424264 mm on all 45-deg bearing surfaces!
        # =====================================================================
        cmds.append({
            "command": "solid.cone",
            "params": {
                "diameter": "12.8", "top_diameter": "5.8", "height": "3.5",
                "base": ["spinner_x", "0", "0"], "axis": "Z", "body_name": "Radar_Spinner"
            }
        })
        cmds.append({
            "command": "solid.cylinder",
            "params": {
                "diameter": "5.8", "height": "11.0",
                "base": ["spinner_x", "0", "3.5"], "axis": "Z", "body_name": "RS_Shaft_Core"
            }
        })
        cmds.append({
            "command": "solid.cone",
            "params": {
                "diameter": "5.8", "top_diameter": "11.8", "height": "3.0",
                "base": ["spinner_x", "0", "14.5"], "axis": "Z", "body_name": "RS_Mid_Cone"
            }
        })
        cmds.append({
            "command": "solid.cylinder",
            "params": {
                "diameter": "11.8", "height": "1.5",
                "base": ["spinner_x", "0", "17.5"], "axis": "Z", "body_name": "RS_Collar"
            }
        })
        cmds.append({
            "command": "solid.cone",
            "params": {
                "diameter": "11.8", "top_diameter": "6.8", "height": "2.5",
                "base": ["spinner_x", "0", "19.0"], "axis": "Z", "body_name": "RS_Taper_In"
            }
        })
        cmds.append({
            "command": "solid.cylinder",
            "params": {
                "diameter": "6.8", "height": "17.5",
                "base": ["spinner_x", "0", "21.5"], "axis": "Z", "body_name": "RS_Shaft"
            }
        })
        # Inner cabin decorative core visible through windows
        cmds.append({
            "command": "solid.cone",
            "params": {
                "diameter": "6.8", "top_diameter": "14.4", "height": "3.8",
                "base": ["spinner_x", "0", "22.0"], "axis": "Z", "body_name": "RS_Core_Low"
            }
        })
        cmds.append({
            "command": "solid.cone",
            "params": {
                "diameter": "14.4", "top_diameter": "6.8", "height": "3.8",
                "base": ["spinner_x", "0", "25.8"], "axis": "Z", "body_name": "RS_Core_High"
            }
        })
        # Roof-top Command Radar Turret (Z=38.5..52.5, 45-deg self-supporting)
        cmds.append({
            "command": "solid.cone",
            "params": {
                "diameter": "6.8", "top_diameter": "18.8", "height": "6.0",
                "base": ["spinner_x", "0", "38.5"], "axis": "Z", "body_name": "RS_Turret_Flare"
            }
        })
        cmds.append({
            "command": "solid.cylinder",
            "params": {
                "diameter": "18.8", "height": "3.0",
                "base": ["spinner_x", "0", "44.5"], "axis": "Z", "body_name": "RS_Turret_Rim"
            }
        })
        cmds.append({
            "command": "solid.cone",
            "params": {
                "diameter": "18.8", "top_diameter": "12.0", "height": "3.4",
                "base": ["spinner_x", "0", "47.5"], "axis": "Z", "body_name": "RS_Turret_Crown"
            }
        })

        # 6-spoke finger-grip wheel + twin radar bar (intersected with 45-deg envelope)
        spoke_names = []
        for k in range(3):
            bname = f"RS_Spoke_{k}"
            cmds.append({
                "command": "solid.box",
                "params": {
                    "length": "25.0", "width": "3.6", "height": "9.0",
                    "center": ["spinner_x", "0", "46.0"], "body_name": bname
                }
            })
            if k > 0:
                cmds.append({
                    "command": "solid.move",
                    "params": {
                        "bodies": [bname],
                        "axis": [0, 0, 1],
                        "angle": f"{k * 60} deg",
                        "origin": ["spinner_x", "0", "46.0"]
                    }
                })
            spoke_names.append(bname)
        cmds.append({
            "command": "solid.combine",
            "params": {"target": spoke_names[0], "tools": spoke_names[1:], "operation": "join"}
        })
        # Envelope for spokes (<= 45 deg overhang!)
        cmds.append({
            "command": "solid.cone",
            "params": {
                "diameter": "11.0", "top_diameter": "25.0", "height": "7.0",
                "base": ["spinner_x", "0", "40.0"], "axis": "Z", "body_name": "RS_Env"
            }
        })
        cmds.append({
            "command": "solid.cylinder",
            "params": {
                "diameter": "25.0", "height": "2.0",
                "base": ["spinner_x", "0", "47.0"], "axis": "Z", "body_name": "RS_Env_Cyl"
            }
        })
        cmds.append({
            "command": "solid.cone",
            "params": {
                "diameter": "25.0", "top_diameter": "19.0", "height": "2.5",
                "base": ["spinner_x", "0", "49.0"], "axis": "Z", "body_name": "RS_Env_Top"
            }
        })
        cmds.append({
            "command": "solid.combine",
            "params": {"target": "RS_Env", "tools": ["RS_Env_Cyl", "RS_Env_Top"], "operation": "join"}
        })
        cmds.append({
            "command": "solid.combine",
            "params": {"target": spoke_names[0], "tools": ["RS_Env"], "operation": "intersect"}
        })

        # Safe rounded dome cap on top of 6-spoke helm (unsafe protruding radar bar removed!)
        cmds.append({
            "command": "solid.combine",
            "params": {
                "target": "Radar_Spinner",
                "tools": [
                    "RS_Shaft_Core", "RS_Mid_Cone", "RS_Collar", "RS_Taper_In",
                    "RS_Shaft", "RS_Core_Low", "RS_Core_High",
                    "RS_Turret_Flare", "RS_Turret_Rim", "RS_Turret_Crown",
                    spoke_names[0]
                ],
                "operation": "join"
            }
        })

        # =====================================================================
        # 9. PIP BODY 3: 6-BLADE HYDRO TURBINE (Rear Water Wheel)
        #    Clearance to Hull = 0.424264 mm on all 45-deg bearing surfaces!
        # =====================================================================
        blade_names = []
        for k in range(3):
            bname = f"HT_Blade_{k}"
            cmds.append({
                "command": "solid.box",
                "params": {
                    "length": "28.0", "width": "3.0", "height": "11.0",
                    "center": ["wheel_x", "0", "wheel_floor_z + 5.5"], "body_name": bname
                }
            })
            if k > 0:
                cmds.append({
                    "command": "solid.move",
                    "params": {
                        "bodies": [bname],
                        "axis": [0, 0, 1],
                        "angle": f"{k * 60} deg",
                        "origin": ["wheel_x", "0", "wheel_floor_z + 5.5"]
                    }
                })
            blade_names.append(bname)
        cmds.append({
            "command": "solid.combine",
            "params": {"target": blade_names[0], "tools": blade_names[1:], "operation": "join"}
        })

        # 45-deg self-supporting turbine envelope
        cmds.append({
            "command": "solid.cone",
            "params": {
                "diameter": "11.8", "top_diameter": "28.0", "height": "8.1",
                "base": ["wheel_x", "0", "wheel_floor_z"], "axis": "Z", "body_name": "HT_Env"
            }
        })
        cmds.append({
            "command": "solid.cylinder",
            "params": {
                "diameter": "28.0", "height": "2.9",
                "base": ["wheel_x", "0", "wheel_floor_z + 8.1"], "axis": "Z", "body_name": "HT_Env_Cyl"
            }
        })
        cmds.append({
            "command": "solid.combine",
            "params": {"target": "HT_Env", "tools": ["HT_Env_Cyl"], "operation": "join"}
        })
        cmds.append({
            "command": "solid.combine",
            "params": {"target": blade_names[0], "tools": ["HT_Env"], "operation": "intersect"}
        })

        # Turbine bearing shaft + hub + nose cap
        cmds.append({
            "command": "solid.cone",
            "params": {
                "diameter": "12.8", "top_diameter": "5.8", "height": "3.5",
                "base": ["wheel_x", "0", "0"], "axis": "Z", "body_name": "Hydro_Turbine"
            }
        })
        cmds.append({
            "command": "solid.cylinder",
            "params": {
                "diameter": "5.8", "height": "10.0",
                "base": ["wheel_x", "0", "3.5"], "axis": "Z", "body_name": "HT_Shaft"
            }
        })
        cmds.append({
            "command": "solid.cone",
            "params": {
                "diameter": "5.8", "top_diameter": "11.8", "height": "3.5",
                "base": ["wheel_x", "0", "13.5"], "axis": "Z", "body_name": "HT_Mid_Cone"
            }
        })
        cmds.append({
            "command": "solid.cylinder",
            "params": {
                "diameter": "11.8", "height": "10.5",
                "base": ["wheel_x", "0", "wheel_floor_z"], "axis": "Z", "body_name": "HT_Hub"
            }
        })
        cmds.append({
            "command": "solid.cone",
            "params": {
                "diameter": "11.8", "top_diameter": "6.0", "height": "2.5",
                "base": ["wheel_x", "0", "wheel_floor_z + 10.5"], "axis": "Z", "body_name": "HT_Cap"
            }
        })
        cmds.append({
            "command": "solid.combine",
            "params": {
                "target": "Hydro_Turbine",
                "tools": ["HT_Shaft", "HT_Mid_Cone", "HT_Hub", "HT_Cap", blade_names[0]],
                "operation": "join"
            }
        })

        # =====================================================================
        # 10. APPEARANCE (Rescue Cruiser Colorway: Cobalt Blue / White / Vermilion / Yellow)
        # =====================================================================
        cmds.append({"command": "appearance.assign", "params": {"bodies": ["Hull"], "color": "#22579a"}})
        # White cabin roof & bow bulwark top accents
        cmds.append({
            "command": "appearance.assign",
            "params": {
                "body": "Hull",
                "faces": [[10, 0, 40.5], [84.5, 0, 34.5]],
                "color": "#f8f9fa"
            }
        })
        # High-vis yellow funnel crown
        cmds.append({
            "command": "appearance.assign",
            "params": {
                "body": "Hull",
                "faces": [[-18, 13.25, 57.0], [-18, 11.5, 60.0]],
                "color": "#ffd13b"
            }
        })
        cmds.append({"command": "appearance.assign", "params": {"bodies": ["Radar_Spinner"], "color": "#ff5a36"}})
        cmds.append({"command": "appearance.assign", "params": {"bodies": ["Hydro_Turbine"], "color": "#ffd13b"}})

        # Hide all construction sketches so snapshots are crystal-clean
        all_sketches = [c["params"]["name"] for c in cmds if c.get("command") == "sketch.create"]
        if all_sketches:
            cmds.append({
                "command": "browser.visibility",
                "params": {"visible": False, "items": all_sketches}
            })

        # Inspections
        cmds.append({"command": "inspect.measure"})
        cmds.append({"command": "inspect.interference"})
        cmds.append({
            "command": "inspect.clearance",
            "params": {
                "bodies": ["Hull"],
                "against": ["Radar_Spinner", "Hydro_Turbine"],
                "clearance": 2.0,
                "nearest": 2
            }
        })

        # Save & Export
        cmds.append({"command": "file.save", "params": {"path": str(OUT_DIR / "bath_boat_mk2.sc").replace("\\", "/")}})
        cmds.append({"command": "file.export", "params": {"path": str(OUT_DIR / "bath_boat_mk2.step").replace("\\", "/")}})
        cmds.append({"command": "file.export", "params": {"path": str(OUT_DIR / "bath_boat_mk2.stl").replace("\\", "/")}})
        cmds.append({"command": "file.export", "params": {"path": str(OUT_DIR / "bath_boat_mk2_pip.3mf").replace("\\", "/")}})
        cmds.append({"command": "file.export", "params": {"path": str(HANDOFF_DIR / "hull.step").replace("\\", "/"), "bodies": ["Hull"]}})
        cmds.append({"command": "file.export", "params": {"path": str(HANDOFF_DIR / "hull.stl").replace("\\", "/"), "bodies": ["Hull"]}})
        cmds.append({"command": "file.export", "params": {"path": str(HANDOFF_DIR / "hull.3mf").replace("\\", "/"), "bodies": ["Hull"], "format": "3mf-tagged"}})
    else:
        cmds.append({"command": "inspect.measure"})
        cmds.append({"command": "file.save", "params": {"path": str(HANDOFF_DIR / "hull.sc").replace("\\", "/")}})

    return cmds


if __name__ == "__main__":
    full_cmds = build_commands(hull_only=False)
    (SRC_DIR / "bath_boat_mk2.json").write_text(json.dumps(full_cmds, indent=1, ensure_ascii=False), encoding="utf-8")
    hull_cmds = build_commands(hull_only=True)
    (SRC_DIR / "hull_only_mk2.json").write_text(json.dumps(hull_cmds, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Generated bath_boat_mk2.json ({len(full_cmds)} commands) and hull_only_mk2.json ({len(hull_cmds)} commands)")
