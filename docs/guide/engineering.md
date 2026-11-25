# Naval & CAE Verification

## Evolution from v4 to Mk-II

- **Hull Silhouette**: Multi-stage lofted V-bow & flared hull (`163.5 × 87.6 mm`) with side bumpers and stealth command bridge.
- **Dual Print-in-Place Mechanisms**: 6-spoke stealth radar spinner (`Radar_Spinner`) + 6-blade hydro turbine (`Hydro_Turbine`), `0` interferences, `0.424264 mm` radial clearance.
- **Flooding Draft Margin**: Increased to `Z = 18.5 mm` (`+1.0 mm` over v4).

## Hydrostatics, LBM Fluid & Static FEA

- **Hydrostatics**: At 25% infill (`95.34 g`), equilibrium draft is `11.04 mm` (`7.46 mm` flooding margin), `GM_T = +30.12 mm`, positive GZ righting arm through **`65°` heel**.
- **FieldCraft 3D Free-Surface LBM (`132,704` cells)**: Confirmed `0.00%` interior flooding across the watertight standpipe and elevated turbine bay.
- **FieldCraft Static FEA (`163,569` tet4 elements)**: `20 N` cabin roof load produces `0.00126 mm` max displacement and `0.2075 MPa` max von Mises stress.
