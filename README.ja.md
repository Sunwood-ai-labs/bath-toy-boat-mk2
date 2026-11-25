<div align="center">
  <img src="./assets/header.svg" alt="bath-toy-boat-mk2 ヘッダー" width="100%" />

  <h1>bath-toy-boat-mk2（おふろレスキュー艇 Mk-II）</h1>
  <p><strong>完全水密・サポート材ゼロの Print-in-Place レスキュー艇 — SolidCraft CAD × FieldCraft 3D流体/FEA × Bambu Studio CLI</strong></p>

  <p>
    <a href="https://github.com/Sunwood-ai-labs/bath-toy-boat-mk2/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/Sunwood-ai-labs/bath-toy-boat-mk2/ci.yml?branch=main&style=flat-square&label=CI" alt="CI" /></a>
    <a href="https://github.com/Sunwood-ai-labs/bath-toy-boat-mk2/actions/workflows/docs.yml"><img src="https://img.shields.io/github/actions/workflow/status/Sunwood-ai-labs/bath-toy-boat-mk2/docs.yml?branch=main&style=flat-square&label=Docs" alt="Docs" /></a>
    <a href="https://github.com/Sunwood-ai-labs/bath-toy-boat-mk2/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-0E7C5B?style=flat-square" alt="MIT License" /></a>
    <img src="https://img.shields.io/badge/Clearance-0.424%20mm-1F5AA6?style=flat-square" alt="最小隙間 0.424mm" />
    <img src="https://img.shields.io/badge/Supports-Zero-C12E1F?style=flat-square" alt="サポート材ゼロ" />
  </p>

  <p>
    <strong>🌐 言語:</strong>
    <a href="./README.md">English</a> |
    <a href="./README.ja.md"><strong>日本語</strong></a>
    &nbsp;&nbsp;·&nbsp;&nbsp;
    <strong>📚 ドキュメント:</strong>
    <a href="https://sunwood-ai-labs.github.io/bath-toy-boat-mk2/ja/">ドキュメントサイト</a>
  </p>
</div>

---

## ✨ 概要

**`bath-toy-boat-mk2`**（*HRX-02 AQUA-VANGUARD*）は、前作「おふろタグボート v4」の完全水密・サポートレス Print-in-Place 機構を継承しつつ、外観と2つの回転ギミックを全面刷新した進化型モデルです。

**SolidCraft**（コード駆動 3D CAD）・**FieldCraft 0.8.1**（13万セル自由表面 LBM 流体解析＋16万要素 FEA）・**Bambu Studio CLI** で設計・検証し、**6本スポークレーダー舵輪＋6枚羽根ハイドロタービン**をサポート材ゼロで一体造形します。

<div align="center">
  <img src="./cad/out/mk2_iso.png" alt="おふろレスキュー艇 Mk-II CAD 斜視図" width="48%" />
  <img src="./cad/out/mk2_section_y0.png" alt="中央縦断面（水密スタンドパイプ＆高床タービンベイ）" width="48%" />
</div>

---

## 📦 3D プリント用モデルファイル

| ファイル | 内容 |
| :--- | :--- |
| [`cad/out/bath_boat_mk2_ams3color_B.3mf`](./cad/out/bath_boat_mk2_ams3color_B.3mf) | パターン B（深緑ハル＋赤ライン＋白ブリッジ、Z層切替 AMS 3色・交換5回・廃材約5g） |
| [`cad/out/bath_boat_mk2_ams3color_A.3mf`](./cad/out/bath_boat_mk2_ams3color_A.3mf) | パターン A（レスキューレッド主体、交換4回・廃材約4g） |
| [`cad/slicer/hrx02_mk2_patternB_a1mini.gcode.3mf`](./cad/slicer/hrx02_mk2_patternB_a1mini.gcode.3mf) | Bambu Lab A1 mini 用スライス済み（パターン B・サポートなし） |
| [`cad/out/bath_boat_mk2.step`](./cad/out/bath_boat_mk2.step) | 編集用 STEP モデル |

---

## 🔍 造船工学・CAE 検証ハイライト

- **B-rep PIP 精度**: 3閉ボディ（`Hull` / `Radar_Spinner` / `Hydro_Turbine`）、干渉 `0` 件、最小隙間 `0.424264 mm`、non-manifold 欠陥 `0` 件。
- **3D 静水力学 & GZ 復原力曲線**: 浸水限界喫水 `Z = 18.5 mm`（前作比 `+1.0 mm`）、横メタセンタ高さ `GM_T = +30.12 mm`、**横傾き `65°` まで転覆せず起き上がる**復原力を確認。
- **自由表面 LBM 3D 流体解析（`132,704` セル）**: 水密スタンドパイプ＆高床ベイによる **船内バスタブ浸水率 `0.00%`（完全乾燥）** を直接計算で実証。
- **静構造解析 FEA（`163,569` 要素）**: キャビン屋根 20 N 押下で最大変位 `0.00126 mm`・最大 von Mises 応力 `0.2075 MPa`。
- **実Gコード顕微鏡 PIP 非溶着監査（`cad/slicer/mk2_pip_gcode_audit.png`）**: 実押出幅 `0.42 mm` で6箇所の軸受エアギャップを顕微鏡レベルで完全分離確認。

<div align="center">
  <img src="./cad/slicer/mk2_pip_gcode_audit.png" alt="実Gコード顕微鏡PIP非溶着監査" width="94%" />
</div>

---

## 📄 ライセンス

MIT License — 詳細は [LICENSE](./LICENSE) を参照してください。
