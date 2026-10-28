class TennisSessionFormController {
    constructor(form) {
        this.form = form;
        this.typeSelect = form.querySelector("#id_session_type");
        this.countSelect = form.querySelector("#id_set_count");
        this.setSection = form.querySelector("#match-sets");
        this.setRows = [...form.querySelectorAll(".set-row")];

        form.addEventListener("change", () => this.update());
        form.addEventListener("input", () => this.update());

        this.update();
    }

    setVisibility(container, visible) {
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
        const isMatch = type === "match";
        const count = isMatch ? Number(this.countSelect.value) : 0;

        this.showField("coach_feedback", type === "lesson");
        this.showField("match_result", isMatch);
        this.showField("set_count", isMatch);

        this.form.querySelector("#id_match_result").required = isMatch;
        this.setSection.hidden = !isMatch || count === 0;

        this.setRows.forEach((row, index) => {
            const visible = isMatch && index < count;

            this.setVisibility(row, visible);

            const mine = row.querySelector('[name$="-my_games"]');
            const theirs = row.querySelector('[name$="-opponent_games"]');

            mine.required = visible;
            theirs.required = visible;

            const hasTieBreak =
                (mine.value === "7" && theirs.value === "6") ||
                (mine.value === "6" && theirs.value === "7");

            const tieBreakFields = row.querySelector(".tiebreak-fields");
            const showTieBreak = visible && hasTieBreak;

            this.setVisibility(tieBreakFields, showTieBreak);

            for (const input of tieBreakFields.querySelectorAll("input")) {
                input.required = showTieBreak;
            }
        });
    }
}

const tennisForm = document.querySelector(".session-form");

if (tennisForm) {
    new TennisSessionFormController(tennisForm);
}