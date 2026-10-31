# Forge Neo MOSS Scheduler：Schedule Type登録・既存UI共存仕様案

作成日：2026-10-31（JST）  
状態：**実装前の仕様案。製品コード・導入先は未変更。**

## 1. 対象と目的

対象リポジトリ：

**[ukr8b3g-cmyk/sd-webui-forge-neo-moss-scheduler](https://github.com/ukr8b3g-cmyk/sd-webui-forge-neo-moss-scheduler)**

確認したmain：[`244ea2891dfcf1cf6289dab6fa18ae0c13332a25`](https://github.com/ukr8b3g-cmyk/sd-webui-forge-neo-moss-scheduler/tree/244ea2891dfcf1cf6289dab6fa18ae0c13332a25)、内部版0.9.0。

移植元：[ComfyUI-MOSS-Shift-Scheduler](https://github.com/ukr8b3g-cmyk/ComfyUI-MOSS-Shift-Scheduler)。今回変更するのはForge版の選択・登録・保存経路であり、ComfyUI版への変更は含めない。

画像の「Schedule Type」にMOSSの3方式を追加し、一覧から直接選べるようにする。既存の「MOSS Scheduler」チェックボックスとShift／Curve／Sigmaボタンも残す。両方の選び方から同じ計算を利用し、各生成パスで適用する方式は1つだけにする。

## 2. 確認した現状

- `scripts/forge_moss_scheduler.py`が下段UIと生成直前の処理を登録している。
- `forge_moss_scheduler/runtime.py`は生成要求ごとにサンプラーの`get_sigmas`を一時的に置き換え、正常終了・例外時に元へ戻す。下段ONなら標準Schedule Typeを上書きする。
- `forge_moss_scheduler/core.py`に3方式の計算がある。現状はSchedule Typeの一覧には登録しない。
- ローカルForge Neo本体では`modules/sd_schedulers.py`の一覧・名前辞書をUIとサンプラーが参照する。通常生成とHiresはそれぞれ選択値を持つ。
- 本体の標準`get_sigmas`にはサンプラー固有／設定による追加ステップと末尾から2番目のsigma削除がある。そのまま標準経路へ移すだけでは、既存MOSSと数値や実行区間数が変わる可能性がある。

Forge Neo／Neo2の確認時の本体HEADは、ともに`2d79fc2ffefa63f4429c4abe35324e66977983d5`。これはソース確認であり、今回の機能を起動・実生成して検証した結果ではない。

## 3. 追加する選択肢

表示名は省略しない。通常のtxt2img／img2imgのSchedule Typeと、Hires schedule typeに登録する。

| 表示名 | 内部ID案 | 利用する既存計算 |
|---|---|---|
| **MOSS Shift Scheduler** | `moss_shift_scheduler` | Radiance互換。power 2.4、midpoint_shift 0.98、steps+1候補から末尾の指定位置を削除 |
| **MOSS Curve Scheduler** | `moss_curve_scheduler` | Power Shift。power 2.0、midpoint_shift 1.0 |
| **MOSS Sigma Scheduler** | `moss_sigma_scheduler` | power 2.4、midpoint_shift 0.98、step_offset 0.75 |

既存のAutomatic・Beta・Simple・Karras等を残す。初期選択、下段の初期状態「OFF＋Shift」、ユーザーの保存済み選択を自動変更しない。表示順は既存一覧の後ろへ3件追加する。

## 4. 選択の優先順位

各パスについて、次の順序で実効方式を解決する。

1. そのパスのSchedule TypeがMOSSなら、一覧で選んだ方式を使用する。
2. 通常のSchedule Typeで下段MOSSがONなら、下段で選んだ方式を使用する。
3. 通常のSchedule Typeで下段MOSSがOFFなら、標準Forge処理を使用する。

| Schedule Type | 下段の状態 | 実際に使用する方式 |
|---|---|---|
| MOSS Shift Scheduler | OFF | MOSS Shift Scheduler |
| MOSS Curve Scheduler | ON＋Shift | **MOSS Curve Scheduler** |
| MOSS Sigma Scheduler | ON＋Curve | **MOSS Sigma Scheduler** |
| Beta | ON＋Shift | MOSS Shift Scheduler（従来動作） |
| Simple | ON＋Sigma | MOSS Sigma Scheduler（従来動作） |
| Beta | OFF | Beta |

下段OFFは「下段からの上書きをしない」という意味になる。一覧でMOSSを選んだ場合まで無効にはしない。この意味と優先順位をREADME・日英マウスオーバーヘルプに明記する。

一覧を選んだだけで下段を自動ONにしたり、下段ボタンを自動変更したりしない。入力設定を保持し、実効方式だけを要求ごとに解決する。

## 5. 通常生成・img2img・Hires

- txt2img／img2imgは通常のSchedule Typeを使って第4節の規則を適用する。
- Hiresで「Use same scheduler」を選んだ場合は、通常パスのSchedule Typeを継承してから同じ規則を適用する。
- Hiresで方式を明示した場合は、そのHires選択を使って同じ規則を適用する。
- **下段ON＋Hiresで通常方式を指定した場合は、Hiresにも下段MOSSが適用される。** 従来の下段ON動作を保つため。Hiresに通常方式を使いたい場合は下段をOFFにし、通常パス側の一覧でMOSSを選ぶ。

| 通常の選択 | Hiresの選択 | 下段 | 通常／Hiresの実効方式 |
|---|---|---|---|
| MOSS Shift | Use same scheduler | OFF | Shift／Shift |
| MOSS Shift | MOSS Sigma | OFF | Shift／Sigma |
| MOSS Shift | Beta | OFF | Shift／Beta |
| Beta | MOSS Curve | OFF | Beta／Curve |
| MOSS Shift | Beta | ON＋Curve | Shift／Curve |

表中だけMOSS名を短縮している。実UIの表示名は第3節のフルネームとする。

img2imgのdenoiseによる区間切り出し、Hiresの追加パス、明示stepsはForgeの既存規則を維持する。MOSSの計算を二重に呼ばず、末尾sigmaを二重削除しない。丸めによる重複sigmaの除去や実際の区間数も現行MOSS出力を正本とし、常にstepsと区間数が等しいという仮定は置かない。

## 6. 実装構成

### 6.1 一覧登録

拡張側に小さな登録モジュールを設け、Forge本体ファイルの直接編集を避ける。

- `Scheduler`と`need_inner_model=True`を利用し、内部ID／表示名を名前辞書にも登録する。関数アダプターは既存`MODE_HANDLERS`を呼び、数式を複製しない。
- UI/APIで選択名を検証する前に登録する。拡張読込時に登録し、`on_before_ui`によるUI再生成でも重複しない構成とする。API-onlyの起動順も確認する。
- `all_schedulers`・表示対象の`schedulers`・`schedulers_map`を整合させ、既存の非表示設定を尊重する。
- 同じ登録処理を繰り返しても各方式は1件だけとする。他拡張が同じ名前を使っている場合は黙って置き換えない。
- 再読込／無効化時の登録解除は自分が登録した項目だけを対象とする。登録・解除後は`get_sampler_and_scheduler`等の名前解決キャッシュも必要に応じて無効化する。

### 6.2 実効方式の共通解決

`runtime.py`に「パスの選択値＋下段のON/OFF・方式」から実効MOSS方式または標準処理を返す、小さな解決関数を設ける。UIとAPIで同じ解決規則を利用する。

MOSSが選ばれた通常の生成経路は、現在の要求単位の`get_sigmas`置換へ集約する。標準Forge側の追加ステップ／sigma削除と、MOSS core内の処理が二重適用されるのを避ける。登録関数だけで全処理を完結させようとせず、パスの設定とstepsを持つruntimeを責任範囲とする。

MOSSを使わないパスは元のサンプラー処理へそのまま委譲する。MOSS→通常、通常→MOSSとHiresで切り替わっても、一時置換が次のパスや要求に漏れないようにする。既存の所有権確認・`finally`による復元を維持し、プロセス全体のサンプラークラスは置き換えない。

登録用関数は標準Schedulerの呼出し契約を満たすが、第三者拡張が生成runtimeを迂回して直接呼ぶ経路まで、従来MOSSのsteps互換を保証する対象には含めない。

### 6.3 対応範囲とエラー

今回もMOSS-Imageと`get_sigmas`を利用するサンプラーを対象とする。DPM++ SDE／DPM++ 2M SDEは推奨であり、サンプラー名の許可リストは戻さない。DDIM／PLMS、MOSS以外のモデル、別のsigma overrideとの同時使用は、実際にMOSSを適用するパスで明確なエラーにする。

通常方式＋下段OFFは、MOSSのモデル検査等で止めない。不正な既知MOSS指定を黙ってBetaやAutomaticへ置き換えない。sigmaの有限性・降順・終端0・利用可能区間の検査を維持する。

## 7. PNG Info・Send to・APIの互換性

- 既存の`MOSS Scheduler`／`MOSS Scheduler Mode`は下段のON/OFF・選択値として保存し、旧画像を引き続き読み込めるようにする。
- 新しい画像では`Schedule type`に通常パスで実際に使った方式、`Hires schedule type`にHiresで実際に使った方式を記録する。実効方式と異なる通常名を結果へ残さない。
- 下段から適用した場合も実効MOSS名を標準フィールドへ記録する。元の画面上の通常選択は書き換えず、旧形式の完全再現と結果の再現性を区別する。画像から復元した後の標準選択は記録された実効方式になる。
- 下段OFF＋一覧MOSSでは、下段の保存値はOFFのまま。OFFでも一覧で指定したMOSSが動くことをヘルプに明記する。実際に使った方式の確認先は標準Schedule typeフィールドとする。
- 既存のMOSS版情報と通常／Hiresのsteps・intervalsは、実際にMOSS計算が実行されたパスについて記録する。
- 旧画像の「通常Schedule type＋MOSS ON＋mode」は従来と同じ結果へ解決する。MOSS情報がない画像は下段OFFへ戻すが、標準フィールドに新MOSS名があれば、その選択は保持する。
- 未知の下段modeは従来どおり警告してOFFにする。拡張がない環境での新MOSS名の復元は保証しない。
- APIの`scheduler`／`hr_scheduler`でも同じ名前解決と優先順位を使う。下段script引数を渡さずMOSS名を指定しても有効になるようにする。新しい独自APIは追加しない。

## 8. 変更予定ファイルと作業順

| 順序 | 対象 | 作業 |
|---|---|---|
| 1 | 正本・Neo／Neo2導入先 | 指示・未コミット変更・版・ハッシュを確認し、変更前を退避 |
| 2 | `forge_moss_scheduler/registry.py`（新設案） | 一覧・名前辞書登録、重複防止、解除、名前解決キャッシュ更新 |
| 3 | `forge_moss_scheduler/runtime.py` | 実効方式の解決、パスごとの適用／復元、標準記録フィールドの整合 |
| 4 | `scripts/forge_moss_scheduler.py` | 起動・UI再生成・終了時の登録接続、既存下段UIと画像復元の接続 |
| 5 | `javascript/moss_scheduler_help.js` | 新旧UIの優先順位とOFFの意味を日英ヘルプへ反映 |
| 6 | `tests/test_extension.py`等 | 登録、優先順位、steps、復元、例外、APIの回帰条件を追加 |
| 7 | `README.md`／`CHANGELOG.md` | 日英の使い方・優先順位表・Hires例・更新手順を記載 |
| 8 | Neo／Neo2 | 検証済み成果物を対象別に反映し、ハッシュと必要な起動確認を記録 |

`core.py`の数式・名前・MIT表記は原則変更しない。追加依存・大規模な共通基盤・重複した数式実装を作らない。登録モジュールの分離は一覧のライフサイクルをruntimeから分けるための最小構成案であり、不要な抽象層を追加しない。

本依頼は仕様書作成まで。コード実装・Neo／Neo2への反映・再起動・コミット／プッシュ・Release作成は実施していない。後続の実装依頼では、明示された範囲で順に実施する。リリース版番号は実装完了時に決め、現行0.9.0をこの仕様書だけで変更しない。

## 9. 必須検証と合格条件

| 検証 | 合格条件 |
|---|---|
| 登録・再登録・UI再生成 | 3方式が各1件。通常選択肢・順序・他拡張の登録を保つ |
| txt2img／img2img／HiresのUI | 各一覧にフルネーム表示。Hiresの継承選択を保つ |
| 選択の優先順位 | 第4・5節の全ケースを満たし、計算は各パス1回だけ |
| 既存MOSSとのCPU比較 | 3方式のsigma列・長さ・終端・区間数が一致。steps 1/2/3/8/10/25/50、モデルshift 1/3/5を含む |
| サンプラー固有処理 | penultimate削除の有無／追加steps設定で二重削除・余分な区間変更がない |
| img2img／Hires | denoiseの代表境界、明示steps、同一／別方式／通常方式への復帰が正しい |
| 既存通常経路 | 通常方式＋下段OFFの呼出し・sigma列を変えない |
| 対応外条件 | 未対応モデル・sigma interfaceなし・別overrideを誤適用せず説明する |
| 例外・キャンセル・連続生成 | 一時置換を必ず解除。次の通常生成に漏れない |
| 画像の保存・復元 | 旧形式、新一覧のみ、下段のみ、両方、Hires別方式、MOSS情報なしを確認 |
| API | UI引数なしのMOSS指定、通常方式、Hires、内部ID／表示名を確認 |
| 実画面 | NeoとNeo2で一覧・優先順位・PNG Info／Send to・日英ヘルプを確認 |
| 実生成 | 代表MOSS条件で完走・エラー・復元を確認。画質優劣や速度改善とは別の判定 |

既存CPUテストと新しい境界テストを先に実行する。実画面・GPU確認は別途結果を記録し、CPU合格だけで合格扱いにしない。コード監査では登録解除の所有権、名前解決キャッシュ、二重適用、Hiresの切替、保存設定の書換え漏れを重点確認する。

## 10. 参照コード

- [現行Forge版runtime](https://github.com/ukr8b3g-cmyk/sd-webui-forge-neo-moss-scheduler/blob/244ea2891dfcf1cf6289dab6fa18ae0c13332a25/forge_moss_scheduler/runtime.py)
- [現行Forge版core・3方式](https://github.com/ukr8b3g-cmyk/sd-webui-forge-neo-moss-scheduler/blob/244ea2891dfcf1cf6289dab6fa18ae0c13332a25/forge_moss_scheduler/core.py)
- [現行Forge版UI接続](https://github.com/ukr8b3g-cmyk/sd-webui-forge-neo-moss-scheduler/blob/244ea2891dfcf1cf6289dab6fa18ae0c13332a25/scripts/forge_moss_scheduler.py)
- [現行Forge版README](https://github.com/ukr8b3g-cmyk/sd-webui-forge-neo-moss-scheduler/blob/244ea2891dfcf1cf6289dab6fa18ae0c13332a25/README.md)
- [ComfyUI移植元](https://github.com/ukr8b3g-cmyk/ComfyUI-MOSS-Shift-Scheduler)

本体の登録・サンプラー動作はローカルForge Neoの`modules/sd_schedulers.py`、`modules/sd_samplers.py`、`modules/sd_samplers_kdiffusion.py`、`modules/script_callbacks.py`、`webui.py`で確認した。導入先の版が変わった場合は実装前に差分を確認する。
