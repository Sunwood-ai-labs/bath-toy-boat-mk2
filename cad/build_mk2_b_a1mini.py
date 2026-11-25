"""Build native A1 mini Z-band 3-color .gcode.3mf for HRX-02 AQUA-VANGUARD (Pattern B)
matching live AMS lite spools:
- Extruder 0 (T0 -> AMS Tray 3 #234D40 Dark Green): Z < 21.5 mm & 52.5..55.0 mm
- Extruder 1 (T1 -> AMS Tray 2 #C12E1F Red):        21.5..27.0 mm & 40.5..52.5 mm
- Extruder 2 (T2 -> AMS Tray 0 #FFFFFF White):      27.0..40.5 mm & >= 55.0 mm

Profile: 0.20mm Standard @BBL A1M, Textured PEI Plate (65C), 3 wall loops, 20% Gyroid, NO support.
"""
import hashlib
import json
import pathlib
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = pathlib.Path(r"C:\Users\makim\.gemini\antigravity\scratch\bath-toy-boat-mk2")
STL_PATH = ROOT / "cad" / "out" / "bath_boat_mk2.stl"
SLICER_DIR = ROOT / "cad" / "slicer"
OUT_3MF = SLICER_DIR / "hrx02_mk2_patternB_a1mini.gcode.3mf"

BAMBU_EXE = pathlib.Path(r"C:\Users\makim\AppData\Local\Programs\Bambu Studio\bambu-studio.exe")
BBL_DIR = pathlib.Path(r"C:\Users\makim\AppData\Local\Programs\Bambu Studio\resources\profiles\BBL")


def load_flat_profile(subdir: str, name: str) -> dict:
    p = BBL_DIR / subdir / f"{name}.json"
    if not p.exists():
        for cand in (BBL_DIR / subdir).glob("*.json"):
            try:
                d = json.loads(cand.read_text(encoding="utf-8"))
                if d.get("name") == name:
                    p = cand
                    break
            except Exception:
                pass
    d = json.loads(p.read_text(encoding="utf-8"))
    res = {}
    inh = d.get("inherits")
    if inh:
        res.update(load_flat_profile(subdir, inh))
    for inc in d.get("include", []):
        res.update(load_flat_profile(subdir, inc))
    res.update(d)
    res.pop("inherits", None)
    res.pop("include", None)
    return res


def a1m_change_filament_block(prev_ext: int, next_ext: int, max_layer_z: float, flush_len: float) -> str:
    """Evaluated Bambu Lab A1 mini 0.4 nozzle change_filament_gcode block (all PLA @ 220C)."""
    feed_v = "523.843"
    rem = flush_len - 23.7
    return "\n".join([
        ";===== A1mini 20251031 =====",
        "G392 S0",
        "M1007 S0",
        f"M620 S{next_ext}A",
        "M204 S9000",
        f"G1 Z{max_layer_z + 3.0:.2f} F1200",
        "",
        "M400",
        "M106 P1 S0",
        "M106 P2 S0",
        "M104 S220",
        "",
        "G1 X180 F18000",
        "",
        f"M620.11 S1 I{prev_ext} E-18 F1200",
        "M400",
        "",
        f"M620.1 E F{feed_v} T220",
        f"M620.10 A0 F{feed_v}",
        f"T{next_ext}",
        f"M620.1 E F{feed_v} T220",
        f"M620.10 A1 F{feed_v} L{flush_len:.1f} H0.4 T220",
        "",
        "G1 Y90 F9000",
        "",
        f"M620.11 S1 I{prev_ext} E18 F{feed_v}",
        "M628 S1",
        "G92 E0",
        f"G1 E18 F{feed_v}",
        "M400",
        "M629 S1",
        "",
        "M400",
        "G92 E0",
        "M628 S0",
        "",
        "; FLUSH_START",
        "; always use highest temperature to flush",
        "M400",
        "M1002 set_filament_type:UNKNOWN",
        "M109 S220",
        "M106 P1 S60",
        f"G1 E23.7 F{feed_v} ; do not need pulsatile flushing for start part",
        f"G1 E{rem * 0.02:.4f} F50",
        f"G1 E{rem * 0.23:.4f} F{feed_v}",
        f"G1 E{rem * 0.02:.4f} F50",
        f"G1 E{rem * 0.23:.4f} F{feed_v}",
        f"G1 E{rem * 0.02:.4f} F50",
        f"G1 E{rem * 0.23:.4f} F{feed_v}",
        f"G1 E{rem * 0.02:.4f} F50",
        f"G1 E{rem * 0.23:.4f} F{feed_v}",
        "; FLUSH_END",
        "G1 E-0.8 F1800",
        "G1 E0.8 F300",
        "M400",
        "M1002 set_filament_type:PLA",
        "",
        "M629",
        "",
        "M400",
        "M106 P1 S60",
        "M109 S220",
        f"G1 E5 F{feed_v} ;Compensate for filament spillage during waiting temperature",
        "M400",
        "G92 E0",
        "G1 E-0.8 F1800",
        "M400",
        "M106 P1 S178",
        "M400 S3",
        "G1 X-3.5 F18000",
        "G1 X-13.5 F3000",
        "G1 X-3.5 F18000",
        "G1 X-13.5 F3000",
        "G1 X-3.5 F18000",
        "G1 X-13.5 F3000",
        "M400",
        f"G1 Z{max_layer_z + 3.0:.2f} F3000",
        "M106 P1 S0",
        "M204 S6000",
        "",
        "M622.1 S0",
        "M9833 F8.75 A0.3 ; cali dynamic extrusion compensation",
        "M1002 judge_flag filament_need_cali_flag",
        "M622 J1",
        "  G92 E0",
        "  G1 E-0.8 F1800",
        "  M400",
        "  M106 P1 S178",
        "  M400 S7",
        "  G1 X0 F18000",
        "  G1 X-13.5 F3000",
        "  G1 X0 F18000 ;wipe and shake",
        "  G1 X-13.5 F3000",
        "  G1 X0 F12000 ;wipe and shake",
        "  G1 X-13.5 F3000",
        "  G1 X0 F12000 ;wipe and shake",
        "  M400",
        "  M106 P1 S0",
        "M623",
        "",
        f"M621 S{next_ext}A",
        "G392 S0",
        "",
        "M1007 S1",
    ])


def main():
    SLICER_DIR.mkdir(parents=True, exist_ok=True)
    tmp = pathlib.Path(tempfile.mkdtemp(prefix="a1m_mk2b_"))

    m = load_flat_profile("machine", "Bambu Lab A1 mini 0.4 nozzle")
    p = load_flat_profile("process", "0.20mm Standard @BBL A1M")
    f_base = load_flat_profile("filament", "Bambu PLA Basic @BBL A1M")

    # Textured PEI Plate (65C) + watertight 3 walls + 20% Gyroid + NO support
    p["curr_bed_type"] = "Textured PEI Plate"
    p["enable_support"] = "0"
    p["wall_loops"] = "3"
    p["sparse_infill_density"] = "20%"
    p["sparse_infill_pattern"] = "gyroid"
    p["timelapse_type"] = "0"

    # Pattern B filament order: T0=Dark Green, T1=Red, T2=White -> --ams-mapping 3,2,0
    f0, f1, f2 = dict(f_base), dict(f_base), dict(f_base)
    f0["default_filament_colour"] = ["#234D40"]
    f1["default_filament_colour"] = ["#C12E1F"]
    f2["default_filament_colour"] = ["#FFFFFF"]

    mp, pp = tmp / "machine.json", tmp / "process.json"
    fp0, fp1, fp2 = tmp / "f0.json", tmp / "f1.json", tmp / "f2.json"
    mp.write_text(json.dumps(m, indent=2), encoding="utf-8")
    pp.write_text(json.dumps(p, indent=2), encoding="utf-8")
    fp0.write_text(json.dumps(f0, indent=2), encoding="utf-8")
    fp1.write_text(json.dumps(f1, indent=2), encoding="utf-8")
    fp2.write_text(json.dumps(f2, indent=2), encoding="utf-8")

    cmd = [
        str(BAMBU_EXE),
        "--orient", "0",
        "--arrange", "1",
        "--load-settings", f"{mp};{pp}",
        "--load-filaments", f"{fp0};{fp1};{fp2}",
        "--slice", "0",
        "--outputdir", str(tmp),
        "--export-3mf", "base_mk2b.gcode.3mf",
        str(STL_PATH),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    base_3mf = tmp / "base_mk2b.gcode.3mf"
    if r.returncode != 0 or not base_3mf.exists():
        raise RuntimeError(f"Base slice failed: exit={r.returncode}, stderr={r.stderr[-400:]}")

    with zipfile.ZipFile(base_3mf, "r") as zin:
        entries = {item.filename: zin.read(item.filename) for item in zin.infolist()}

    g_lines = entries["Metadata/plate_1.gcode"].decode("utf-8").splitlines()
    bed_lines = [l for l in g_lines if "M140 S" in l or "M190 S" in l or "curr_bed_type" in l]
    print("[Verify Bed]", bed_lines)
    if not any("M140 S65" in l or "M190 S65" in l for l in bed_lines):
        raise RuntimeError(f"Expected 65C Textured PEI Plate temp, got: {bed_lines}")

    # Pattern B 5-swap schedule (0-based extruders: 0=Dark Green, 1=Red, 2=White):
    # Z >= 21.5: 0 (Dark Green) -> 1 (Red)        flush  95 mm
    # Z >= 27.0: 1 (Red)        -> 2 (White)      flush 115 mm
    # Z >= 40.5: 2 (White)      -> 1 (Red)        flush  85 mm
    # Z >= 52.5: 1 (Red)        -> 0 (Dark Green) flush  95 mm
    # Z >= 55.0: 0 (Dark Green) -> 2 (White)      flush 120 mm
    target_thresholds = [
        (21.5, 0, 1, 95.0),
        (27.0, 1, 2, 115.0),
        (40.5, 2, 1, 85.0),
        (52.5, 1, 0, 95.0),
        (55.0, 0, 2, 120.0),
    ]

    cur_z = 0.0
    next_t_idx = 0
    out_lines = []
    injected = []
    last_m106 = "M106 S0"
    in_exec = False
    total_layers = 300

    i = 0
    while i < len(g_lines):
        line = g_lines[i]
        if "; EXECUTABLE_BLOCK_START" in line:
            in_exec = True
        if in_exec and re.match(r"^M106\s+(?:P1\s+)?S\d+(?:\.\d+)?$", line.strip()):
            last_m106 = line.strip()
        out_lines.append(line)
        if in_exec and line.startswith("; Z_HEIGHT:"):
            prev_max_z = cur_z
            cur_z = float(line.split(":", 1)[1].strip())
            if next_t_idx < len(target_thresholds) and cur_z >= target_thresholds[next_t_idx][0] - 1e-6:
                _, p_ext, n_ext, fl_len = target_thresholds[next_t_idx]
                j = i + 1
                layer_num_seen = None
                while j < len(g_lines) and not g_lines[j].startswith("; OBJECT_ID:"):
                    if re.match(r"^M106\s+(?:P1\s+)?S\d+(?:\.\d+)?$", g_lines[j].strip()):
                        last_m106 = g_lines[j].strip()
                    out_lines.append(g_lines[j])
                    m_ln = re.search(r"layer num/total_layer_count:\s*(\d+)/(\d+)", g_lines[j])
                    if m_ln:
                        layer_num_seen = int(m_ln.group(1))
                        total_layers = int(m_ln.group(2))
                    j += 1
                block = a1m_change_filament_block(p_ext, n_ext, prev_max_z, fl_len)
                out_lines.append(block)
                out_lines.append("G90")
                out_lines.append("M83")
                out_lines.append(last_m106)

                # Replace post-swap spiral z-hop with safe XY travel at Z=(prev_max_z+3.0)
                k = j
                replaced_travel = False
                dest_x = dest_y = dest_z = None
                while k < min(len(g_lines), j + 12):
                    if (
                        k + 1 < len(g_lines)
                        and re.match(r"^G[23]\s+Z([\d.]+)\s+I[-\d.]+\s+J[-\d.]+\s+P1\b", g_lines[k].strip())
                        and re.match(r"^G1\s+X([-\d.]+)\s+Y([-\d.]+)\s+Z([\d.]+)\s*$", g_lines[k + 1].strip())
                    ):
                        m_dest = re.match(r"^G1\s+X([-\d.]+)\s+Y([-\d.]+)\s+Z([\d.]+)\s*$", g_lines[k + 1].strip())
                        dest_x, dest_y, dest_z = m_dest.group(1), m_dest.group(2), m_dest.group(3)
                        for pre_idx in range(j, k):
                            out_lines.append(g_lines[pre_idx])
                        out_lines.append(f"G1 X{dest_x} Y{dest_y} F18000 ; safe XY travel from wiper at Z={prev_max_z + 3.0:.2f}")
                        out_lines.append(f"G1 Z{dest_z} F12000 ; lower to z-hop height")
                        j = k + 2
                        replaced_travel = True
                        break
                    k += 1
                if not replaced_travel:
                    # Fallback: if no spiral z-hop, look for direct G1 X.. Y.. travel
                    out_lines.append(f"; note: standard post-swap travel at layer {layer_num_seen}")

                injected.append({
                    "layer": layer_num_seen,
                    "z_mm": cur_z,
                    "prev_ext": p_ext,
                    "next_ext": n_ext,
                    "flush_mm": fl_len,
                    "replaced_spiral": replaced_travel,
                })
                next_t_idx += 1
                i = j - 1
        i += 1

    if len(injected) != 5:
        raise RuntimeError(f"Expected 5 injected swaps, got {len(injected)}: {injected}")
    print("[Swaps Injected]", json.dumps(injected, indent=2))

    gcode_final_str = "\n".join(out_lines) + "\n"
    gcode_final_str = gcode_final_str.replace("; filament: 1\n", "; filament: 1,2,3\n", 1)
    gcode_bytes = gcode_final_str.encode("utf-8")
    md5_hex = hashlib.md5(gcode_bytes).hexdigest().upper().encode("utf-8")

    # Update slice_info.config
    l1, l2, l3, l4, l5 = [x["layer"] - 1 for x in injected]
    si_root = ET.fromstring(entries["Metadata/slice_info.config"])
    plate_el = si_root.find("plate")
    for md in plate_el.findall("metadata"):
        k = md.attrib.get("key")
        if k == "filament_maps":
            md.attrib["value"] = "1 2 3"
        elif k == "limit_filament_maps":
            md.attrib["value"] = "0 0 0"
        elif k == "prediction":
            md.attrib["value"] = str(int(md.attrib["value"]) + 280)
        elif k == "weight":
            md.attrib["value"] = "127.00"

    old_fils = plate_el.findall("filament")
    insert_idx = list(plate_el).index(old_fils[0])
    for f_el in old_fils:
        plate_el.remove(f_el)

    fil_specs = [
        ("1", "#234D40", "27.50", "83.20"),
        ("2", "#C12E1F", "8.60", "26.00"),
        ("3", "#FFFFFF", "5.90", "17.80"),
    ]
    for off, (fid, fcol, fm, fg) in enumerate(fil_specs):
        fe = ET.Element("filament", {
            "id": fid, "tray_info_idx": "GFA00", "type": "PLA", "color": fcol,
            "used_m": fm, "used_g": fg, "group_id": "0", "nozzle_diameter": "0.40",
            "volume_type": "Standard", "used_for_object": "true", "used_for_support": "false",
            "directly_used": "true", "total_load_time": "28.00", "total_unload_time": "34.00",
        })
        plate_el.insert(insert_idx + off, fe)

    lfl_parent = plate_el.find("layer_filament_lists")
    for ch in list(lfl_parent):
        lfl_parent.remove(ch)
    ranges = [
        ("0", f"0 {l1 - 1}"),
        ("1", f"{l1} {l2 - 1}"),
        ("2", f"{l2} {l3 - 1}"),
        ("1", f"{l3} {l4 - 1}"),
        ("0", f"{l4} {l5 - 1}"),
        ("2", f"{l5} {total_layers - 1}"),
    ]
    for flist, lrange in ranges:
        ET.SubElement(lfl_parent, "layer_filament_list", {"filament_list": flist, "layer_ranges": lrange})

    p1_json = json.loads(entries["Metadata/plate_1.json"].decode("utf-8"))
    p1_json["bed_type"] = "textured_plate"
    p1_json["filament_colors"] = ["#234D40", "#C12E1F", "#FFFFFF"]
    p1_json["filament_ids"] = [0, 1, 2]
    p1_json["first_extruder"] = 0

    fseq_json = {"plate_1": {"nozzle_sequence": [0], "optimal_assignment": [0, 1, 2], "sequence": [1, 2, 3]}}

    entries["Metadata/plate_1.gcode"] = gcode_bytes
    entries["Metadata/plate_1.gcode.md5"] = md5_hex
    entries["Metadata/slice_info.config"] = ET.tostring(si_root, encoding="utf-8", xml_declaration=True)
    entries["Metadata/plate_1.json"] = json.dumps(p1_json, separators=(",", ":")).encode("utf-8")
    entries["Metadata/filament_sequence.json"] = json.dumps(fseq_json, separators=(",", ":")).encode("utf-8")

    with zipfile.ZipFile(OUT_3MF, "w", zipfile.ZIP_DEFLATED) as zout:
        for fname, data in entries.items():
            zout.writestr(fname, data)

    print(f"[Built] {OUT_3MF} ({OUT_3MF.stat().st_size} bytes), md5={md5_hex.decode()}")


if __name__ == "__main__":
    main()
