/* Native hover help, scoped to this extension and the WebUI locale setting. */
(() => {
    "use strict";
    const help = {
        ja: [
            "ONにすると、選んだ方式を通常のSchedule Typeより優先して使います。一覧に項目は増えません。OFFなら通常のSchedule Typeを使います。MOSS-Imageモデル用です。",
            "MOSS Shift Scheduler：基準の方式です。元のRadiance Shiftと同じ計算を使います。まずはこの方式から比較してください。",
            "MOSS Curve Scheduler：元のPower Shiftの既定曲線です。Shiftとはノイズ量を下げる配分が異なります。仕上がりの違いを比較できます。",
            "MOSS Sigma Scheduler：Shiftに近い曲線で、各ステップの位置を少しずらした方式です。Shiftとの仕上がりの違いを比較できます。",
        ],
        en: [
            "ON uses the selected MOSS mode instead of Schedule Type; it does not add list entries. OFF uses the normal Schedule Type. For MOSS-Image models only.",
            "MOSS Shift Scheduler: the baseline, using the original Radiance Shift calculation. Start here when comparing modes.",
            "MOSS Curve Scheduler: the original Power Shift default curve. It distributes denoising steps differently from Shift; compare the resulting images.",
            "MOSS Sigma Scheduler: a curve close to Shift with slightly offset step placement. Compare its output with Shift.",
        ],
    };
    const isJapanese = value => /^(ja|jp)([-_.]|$)|japanese|日本語/i.test(String(value || "").trim());
    function setTitle(element, title) {
        if (element && element.getAttribute("title") !== title) element.setAttribute("title", title);
    }
    function refresh() {
        const app = typeof gradioApp === "function" ? gradioApp() : document;
        const locale = typeof opts !== "undefined" ? opts.localization : "";
        const text = help[isJapanese(locale) ? "ja" : "en"];
        for (const row of app.querySelectorAll(".forge-moss-scheduler")) {
            const checkbox = row.querySelector('input[type="checkbox"]');
            setTitle(checkbox, text[0]);
            setTitle(checkbox?.closest("label"), text[0]);
            const labels = [...row.querySelectorAll(".forge-moss-modes label")]
                .filter(label => label.querySelector('input[type="radio"]'));
            labels.forEach((label, index) => {
                if (!text[index + 1]) return;
                setTitle(label, text[index + 1]);
                setTitle(label.querySelector('input[type="radio"]'), text[index + 1]);
            });
        }
    }
    if (typeof onUiLoaded === "function") onUiLoaded(refresh);
    if (typeof onAfterUiUpdate === "function") onAfterUiUpdate(refresh);
    if (typeof onOptionsAvailable === "function") onOptionsAvailable(refresh);
    if (typeof onOptionsChanged === "function") onOptionsChanged(refresh);
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", refresh, {once: true});
    else refresh();
    window.ForgeMossSchedulerHelp = Object.freeze({refresh});
})();
