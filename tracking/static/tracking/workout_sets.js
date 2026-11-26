const setsEditor = document.querySelector("#workout-sets-editor");

if (setsEditor) {
    const rows = [...setsEditor.querySelectorAll(".workout-set-row")];
    const recorded = setsEditor.querySelector("#last-recorded-set");

    function field(row, name) {
        return row.querySelector(`[name$="-${name}"]`);
    }

    function readRow(row) {
        return {
            reps: field(row, "reps")?.value ?? "",
            weight: field(row, "weight_kg")?.value ?? "",
            minutes: field(row, "minutes")?.value ?? "",
            seconds: field(row, "seconds")?.value ?? "",
        };
    }

    function readRecorded() {
        if (!recorded) {
            return null;
        }

        const duration = recorded.dataset.duration;
        const total = duration === "" ? null : Number(duration);

        return {
            reps: recorded.dataset.reps,
            weight: recorded.dataset.weight,
            minutes: total === null ? "" : String(Math.floor(total / 60)),
            seconds: total === null ? "" : String(total % 60),
        };
    }

    rows.forEach((row, index) => {
        const button = row.querySelector("[data-copy-previous]");

        if (!button) {
            return;
        }

        button.addEventListener("click", () => {
            const values = index > 0
                ? readRow(rows[index - 1])
                : readRecorded();

            const feedback = row.querySelector("[data-copy-feedback]");

            if (!values || Object.values(values).every(value => value === "")) {
                feedback.textContent = "The previous set has no values to copy.";
                return;
            }

            const mapping = {
                reps: "reps",
                weight_kg: "weight",
                minutes: "minutes",
                seconds: "seconds",
            };

            for (const [name, key] of Object.entries(mapping)) {
                const input = field(row, name);

                if (input) {
                    input.value = values[key];
                    input.dispatchEvent(new Event("input", { bubbles: true }));
                }
            }

            feedback.textContent = "Copied. You can change these values before saving.";
        });
    });
}