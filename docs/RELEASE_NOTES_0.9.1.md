# Forge Neo MOSS Scheduler v0.9.1

[日本語](#日本語)

- Add **MOSS Shift Scheduler / MOSS Curve Scheduler / MOSS Sigma Scheduler** to Schedule Type, including Hires.
- Preserve the lower controls. Each pass resolves **list-selected MOSS > lower override ON > native schedule**. List-selected MOSS works with the checkbox OFF.
- Preserve core equations and request-local sigma handling; avoid double step adjustment / penultimate removal. Compatible sigma-based samplers remain supported without a sampler-name allowlist.
- Preserve lower input state separately from actual Schedule type in PNG Info. Fix API infotext False restoration; handle registration/unload, conflicts, batch metadata and exception/cancellation cleanup.
- Update the English/Japanese README, retaining the owner's two screenshots and explaining normal/Hires selection and returning to Beta or other native schedules.

Recommended start: MOSS-Image SFT + lora_latest DMD LoRA **0.8**, **8 steps, CFG 3, model shift 5**, DPM++ SDE or DPM++ 2M SDE, MOSS Shift Scheduler in the list, lower override OFF. Adjustable recommendations.

**Restart Forge itself, then reload the browser.** No new dependencies or model downloads. Validation: 23 tests per Neo/Neo2 environment, 720 independently generated selection cases, 90 canonical comparisons, 19 installed solvers / 342 CPU cases. Small stand-in denoisers replace checkpoint inference. Live API-only/GUI server startup, actual browser behavior and GPU generation remain unverified; GPU testing is performed by the user. Previous v0.9.0 remains available.

[Usage and images](https://github.com/ukr8b3g-cmyk/sd-webui-forge-neo-moss-scheduler/blob/v0.9.1/README.md)

## 日本語

- Schedule Typeへ **MOSS Shift Scheduler／MOSS Curve Scheduler／MOSS Sigma Scheduler** を追加しました。Hires側でも選べます。
- 従来の下段UIを維持し、通常／Hiresそれぞれで **一覧MOSS ＞ 下段ON ＞ 標準処理** の順に適用します。一覧でMOSSを選ぶ場合、下段はOFFでも有効です。
- 計算用coreは変更せず、ステップ補正・sigma削除の二重適用を防ぎます。サンプラー名では制限せず、対応するSIGMAS方式を使用できます。
- PNG Infoに下段の入力状態と実効方式を別々に記録します。APIのFalse復元、登録解除・衝突・世代管理・例外／キャンセル後の復元にも対応しました。
- ユーザー追加の画像2枚を保持し、日英READMEを現在の使い方に更新しました。

推奨開始例：**MOSS-Image SFT＋lora_latest DMD LoRA 0.8、8 steps、CFG 3、モデルShift 5、DPM++ SDEまたはDPM++ 2M SDE、一覧でMOSS Shift Scheduler、下段OFF**。固定値ではなく調整できます。

**更新後はForge本体を完全再起動し、ブラウザーを再読み込みしてください。** 両環境各23試験、独立選択720条件・正本比較90条件・19サンプラー342条件をCPUで確認しました。実サーバー起動・実画面・GPU生成は未確認で、GPUはユーザー側で確認する前提です。旧v0.9.0は保持します。
