class TennisSessionFormController {
    constructor(form) {
        this.form = form;
        this.typeSelect = form.querySelector("#id_session_type");
        this.modeSelect = form.querySelector("#id_recording_mode");
        this.countSelect = form.querySelector("#id_set_count");
        this.resultSelect = form.querySelector("#id_match_result");
        this.setSection = form.querySelector("#match-sets");
        this.setRows = [...form.querySelectorAll(".set-row")];
        this.submitButton = form.querySelector('button[type="submit"]');

        form.addEventListener("change", () => this.update());
        form.addEventListener("input", () => this.update());

        this.update();
    }

    setVisibility(container, visible) {
        if (!container) return;

        container.hidden = !visible;

        for (const control of container.querySelectorAll(
            "input, select, textarea"
        )) {
            control.disabled = !visible;
        }
    }

    showField(name, visible) {
        const container = this.form.querySelector(
            `[data-field="${name}"]`
        );

        this.setVisibility(container, visible);
    }

    update() {
        const type = this.typeSelect.value;
        const isLive = this.modeSelect?.value === "live";
        const isMatch = type === "match";
        const showResults = isMatch && !isLive;
        const count = showResults
            ? Number(this.countSelect.value)
            : 0;

        this.showField("coach_feedback", type === "lesson");
        this.showField("match_result", showResults);
        this.showField("set_count", showResults);

        this.resultSelect.required = showResults;
        this.setSection.hidden = !showResults || count === 0;

        if (this.submitButton) {
            this.submitButton.textContent = isLive
                ? "Start session"
                : "Save session";
        }

        this.setRows.forEach((row, index) => {
            const visible = showResults && index < count;

            this.setVisibility(row, visible);

            const mine = row.querySelector('[name$="-my_games"]');
            const theirs = row.querySelector(
                '[name$="-opponent_games"]'
            );

            mine.required = visible;
            theirs.required = visible;

            const hasTieBreak =
                (mine.value === "7" && theirs.value === "6") ||
                (mine.value === "6" && theirs.value === "7");

            const tieBreakFields = row.querySelector(
                ".tiebreak-fields"
            );
            const showTieBreak = visible && hasTieBreak;

            this.setVisibility(tieBreakFields, showTieBreak);

            for (const input of tieBreakFields.querySelectorAll(
                "input"
            )) {
                input.required = showTieBreak;
            }
        });
    }
}

const tennisTypeSelect = document.querySelector("#id_session_type");
const tennisForm = tennisTypeSelect?.closest("form");

if (tennisForm) {
    new TennisSessionFormController(tennisForm);
}