# AMS 3色プリント手順

## 3D プリント用モデル

- `cad/out/bath_boat_mk2_ams3color_B.3mf` — パターン B（深緑ハル＋赤ライン＋白ブリッジ / 交換5回・廃材約5g）
- `cad/out/bath_boat_mk2_ams3color_A.3mf` — パターン A（レスキューレッド主体 / 交換4回・廃材約4g）
- `cad/slicer/hrx02_mk2_patternB_a1mini.gcode.3mf` — Bambu Lab A1 mini 用スライス済み（`0.24mm Draft`・約3時間17分・サポートなし）

## 推奨スライス設定

- **サポート**: OFF（サポート材ゼロ）
- **外周壁 / インフィル**: 水密 `3` 周壁 / `15〜20%` Gyroid インフィル
- **顕微鏡 G-code 監査**: 実押出幅 `0.42 mm` で6箇所の軸受エアギャップを完全分離確認済み。
