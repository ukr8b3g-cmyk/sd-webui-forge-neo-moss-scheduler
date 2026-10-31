# Schedule Type共存：ローカル実装記録

2026-10-31 JST。対象：[sd-webui-forge-neo-moss-scheduler](https://github.com/ukr8b3g-cmyk/sd-webui-forge-neo-moss-scheduler)。以下は基準244ea289・内部版0.9.0での実装段階の検証記録です。後続のv0.9.1に収録する変更と現在の使用方法は[リリースノート](RELEASE_NOTES_0.9.1.md)とREADMEを参照してください。末尾の未公開記述は実装当時の履歴です。

## 実装

- registry.pyだけを製品モジュールとして追加。既存本体のScheduler定義・一覧・辞書へ3方式を登録。名前解決cacheの更新、非表示、再登録、所有権付き解除、第三者chain内の無効化、部分失敗のrollbackを扱う。
- runtime.pyに純粋なパス選択と共通sigma計算・検査を追加。各パスの一覧MOSS ＞ 下段ON ＞ native。通常／Hiresは個別判定。MOSSのget_sigmasは各sampling呼出し1回だけ。所有権・再入・未適用・二重計算・別overrideを検査し、例外／KeyboardInterruptでも復元する。
- before_processで入力を捕捉し、before_process_batchで自分のmetadataだけを前の値へ戻す。下段入力と実効Schedule typeを別々に記録し、Hires-onlyや使用suffixの区間数を扱う。
- Native PasteFieldの文字列targetを維持し、API用functionで実boolを返す。GUI／API共通の復元関数を使用。既存UIの2引数・初期OFF＋Shift・CSS等は維持。
- 日英ヘルプとREADMEを更新。本体ファイル・core.py・tests/reference/comfy_scheduler.py・依存・ユーザー設定は変更しない。

## ローカルへの適応と検証

利用者提供の最終仕様書と引継ぎを参照し、本体のScheduler／PasteField／script callback／API値変換／サンプラー実装をローカルで照合した。添付に記載された別のクラウド環境の試験結果を、今回の結果として扱わない。

比較JSON類は今回の添付に含まれていないため、元の720 fixtureを実行したとは主張しない。独立の直積720条件を生成して優先順位を検証し、変更していないcore参照との90条件を実torch CPUで比較する。要求stepsと実区間数が等しいとは仮定しない。

既存のFake hostを増やすだけにせず、本体から抽出したSchedulerクラス、PasteFieldクラス、get_sigmas／img2img処理、19の実solverコードを使用する。モデルは小さい代替denoiserでありcheckpointはロードしない。

- Python suite：23件（選択720条件、core比較90条件、native getterのdiscard4状態、19 solver・342条件を含む）。
- 登録・非表示・キャッシュ・衝突・外部所有権・inactive chain・partial rollback、通常／Hires、False復元、metadata reset、所有権／再入／二重計算／未適用、キャンセルを確認。
- 実Gradioの部品構築は試験するが、稼働ForgeのUI/API起動ではない。
- JS構文と差分空白を確認。新依存・GPU生成・モデルダウンロードなし。

導入先はForge-Neo／Forge-Neo2の既存extensionフォルダーを使用する。正本と両環境のファイル照合および最終試験の結果は次の機械可読記録に保存する：

`D:/Codex/_snapshots/Forge-Neo-MOSS-Scheduler/20261031-203724-dropdown-implementation/RESULT.json`

## 残る確認と操作

本体再起動・利用中ブラウザーreload・API-only/GUI+APIの実サーバー起動・実画面・GPU生成は未実施。GPUはユーザーが行う。新しいPythonを使うには本体を完全再起動してブラウザーを再読み込みする。

GPU前の確認例：一覧MOSS＋下段OFF、一覧Curve＋下段ON/Shift、通常Beta＋下段ON、MOSS Shift→Hires Sigma、MOSS Shift→Beta（下段OFF）、img2img、キャンセル後の通常方式＋下段OFF。PNG Infoの実効方式と下段OFF保存も確認する。

コード監査で、テストクラスimportによる二重実行を除去し、登録の部分失敗後にも予約名がAutomaticへ落ちないよう保護を残した。数式の複製や別々の計算パイプラインは追加していない。任意の外部拡張との全組合せ、全R条件の実サーバー／UI受入完了は主張しない。コミット・プッシュ・Release作成は未実施。
