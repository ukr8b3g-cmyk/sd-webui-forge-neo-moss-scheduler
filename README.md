# Forge Neo MOSS Scheduler 0.9.1

[日本語](#日本語) · [Implementation / validation](docs/LOCAL_IMPLEMENTATION_RESULT_JA.md)

Unofficial Forge port of [ComfyUI-MOSS-Shift-Scheduler](https://github.com/ukr8b3g-cmyk/ComfyUI-MOSS-Shift-Scheduler).
Repository: [sd-webui-forge-neo-moss-scheduler](https://github.com/ukr8b3g-cmyk/sd-webui-forge-neo-moss-scheduler).
Version 0.9.1 adds the three existing calculations to Schedule Type while preserving the lower controls. [Release notes](docs/RELEASE_NOTES_0.9.1.md).

## Selection

Select **MOSS Shift Scheduler**, **MOSS Curve Scheduler**, or **MOSS Sigma Scheduler** in Schedule Type. This works with the lower checkbox OFF.
The existing lower checkbox and Shift / Curve / Sigma controls remain available.

<img width="287" height="470" alt="Schedule Type — user-provided screenshot" src="https://github.com/user-attachments/assets/a079632e-fcd5-40bc-8bbd-34605c0f4b9b" />

Select the full MOSS scheduler name here; the lower checkbox can stay OFF.

| Schedule Type | Lower control | Effective schedule |
|---|---|---|
| MOSS mode | Either state | The MOSS mode selected in the list |
| Normal mode, e.g. Beta | ON | The lower MOSS mode |
| Normal mode | OFF | Native Forge schedule |

The main and Hires passes resolve separately. **Use same scheduler** inherits the main selection; **Automatic** is independent.
For MOSS main and normal Hires, turn the lower override OFF, select MOSS in the main list and Beta (or another normal mode) in Hires. With the lower override ON, a normal Hires selection is also overridden.
No automatic changes are made to seed, steps, CFG, model shift, LoRA or saved UI selection.

![Existing lower controls](docs/images/moss-scheduler-controls.png)

Fresh lower controls remain OFF + Shift. Hover help follows the WebUI locale: Japanese for Japanese, English otherwise.

## Recommended starting point

These are adjustable owner recommendations for MOSS-Image SFT plus acceleration LoRA, not benchmarked universal optima.

| Setting | Starting point |
|---|---|
| Model | [MOSS-Image SFT](https://huggingface.co/OpenMOSS-Team/MOSS-Image-SFT) |
| LoRA | [lora_latest.safetensors DMD](https://huggingface.co/lodestones/MOSS-Image-SFT-8-steps-dmd/blob/main/lora_latest.safetensors), strength 0.8 |
| Sampler | DPM++ SDE / DPM++ 2M SDE |
| Steps | 8–10, start at 8 |
| CFG | 3 |
| Model shift | 5 |
| Schedule Type | MOSS Shift Scheduler |
| Lower MOSS override | OFF when selecting directly from the list |

LoRA strength 0.8 differs from its author's 0.7 recommendation. Normal SFT without acceleration LoRA has had limited practical testing.
The sampler names above are recommendations only. Other compatible sigma-based samplers remain supported. DDIM/PLMS have no compatible sigma interface: choose a normal schedule and turn the lower override OFF.

| Mode | Existing equation |
|---|---|
| MOSS Shift Scheduler | Radiance compatible, power 2.4, midpoint_shift 0.98, steps+1 grid with penultimate removal |
| MOSS Curve Scheduler | Power Shift defaults, power 2.0, midpoint_shift 1.0 |
| MOSS Sigma Scheduler | power 2.4, midpoint_shift 0.98, offset 0.75 |

The core equations, duplicate timestep handling and sigma lengths are unchanged. Each MOSS sampling call calculates once, bypassing native extra-step / penultimate adjustments without changing global settings.

## Metadata and compatibility

Schedule type / Hires schedule type record the actual MOSS choice. MOSS Scheduler / MOSS Scheduler Mode preserve the lower controls, so list-selected MOSS with lower OFF restores OFF. Old images using the lower override still work.
MOSS Schedule intervals records the full schedule; MOSS Sampling intervals records the used suffix, with equivalent MOSS Hires fields. An image without lower-control fields restores the lower override OFF while retaining its standard schedule choice.

MOSS-Image models only. Another sigma override, invalid schedule, incompatible sampler or conflicting registration produces an explicit error. There is no silent fallback. Non-MOSS schedules with lower OFF retain native behavior.

## Install / update

Inside Forge's extensions directory:

```sh
git clone https://github.com/ukr8b3g-cmyk/sd-webui-forge-neo-moss-scheduler.git
```

Update existing installations through the usual extension updater. After Python code updates, fully restart Forge and reload the browser. UI Reload alone does not load updated Python modules. Install one copy only. No new dependencies or model downloads are required.

## 日本語

**v0.9.1**では、Schedule Typeに **MOSS Shift Scheduler／MOSS Curve Scheduler／MOSS Sigma Scheduler** を追加しました。従来の下段操作も使えます。[リリースノート](docs/RELEASE_NOTES_0.9.1.md)。

<img width="287" height="470" alt="Schedule Typeの選択例 — ユーザー提供画像" src="https://github.com/user-attachments/assets/f748070e-f064-4250-8de7-e0a87e849abd" />

この一覧でMOSSを選ぶ場合、下段をONにする必要はありません。

**一覧MOSS ＞ 下段ON ＞ 標準処理**の順で、通常生成とHiresそれぞれの方式を決定します。一覧でMOSSを選べば、下段チェックがOFFでも動作します。下段OFFは下段からの上書きだけを無効化します。

| Schedule Type | 下段 | 実効方式 |
|---|---|---|
| 一覧のMOSS方式 | ON／OFF | 一覧のMOSS方式 |
| Beta等の通常方式 | ON | 下段のMOSS方式 |
| 通常方式 | OFF | 標準Forge処理 |

HiresだけBeta等を使う場合は、下段をOFFにし、通常一覧でMOSS、Hires一覧でBeta等を選んでください。下段ONのままでは通常のHires選択も上書きします。Use same schedulerは通常側の選択を継承し、Automaticは別の自動選択です。

推奨開始値は **MOSS-Image SFT＋lora_latest DMD LoRA 0.8、8 steps、CFG 3、モデルshift 5、DPM++ SDEまたはDPM++ 2M SDE、一覧でMOSS Shift Scheduler、下段OFF**です。各値は調整できます。LoRAなしの通常SFTは実使用確認が少なく、画質優劣は未評価です。

1. 更新後、Forge本体を完全再起動し、ブラウザーを再読み込みします。
2. モデル・LoRA・サンプラー・Steps・CFG・モデルShiftを設定します。
3. Schedule TypeでMOSSの3方式から選びます。最初はMOSS Shift Scheduler・下段OFFで比較できます。
4. 従来操作を使う場合は一覧を通常方式にして下段をONにし、Shift／Curve／Sigmaを選びます。
5. Beta等へ戻す場合は一覧もその通常方式に変更し、下段をOFFにします。下段OFFだけでは一覧MOSSは無効になりません。

![従来の下段操作](docs/images/moss-scheduler-controls.png)

PNG InfoのSchedule type／Hires schedule typeには実際の方式、MOSS Scheduler／Modeには下段の入力状態を保存します。旧形式も復元できます。API infotextの文字列Falseは実bool Falseへ変換し、生成後の下段が勝手にONになることを防ぎます。

MOSS-Image専用です。DPM++の2種類は推奨で、サンプラー名による制限ではありません。DDIM／PLMSでは通常方式＋下段OFFにします。登録衝突・別sigma override・対応外モデル等は明示エラーです。

**利用前にForge本体を完全再起動し、ブラウザーを再読み込みしてください。** GPU確認はユーザー側で実施する前提です。CPU試験やGradio部品構築は、稼働画面・実APIサーバー・GPU生成の成功を証明しません。

## License / 来歴

MIT. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
The adapted scheduler retains the original Silver copyright and ComfyUI port attribution. No PPM or other new runtime dependency is added.
