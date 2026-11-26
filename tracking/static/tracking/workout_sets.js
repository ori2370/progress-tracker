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
            basis: field(row, "weight_basis")?.value ?? "",
            minutes: field(row, "minutes")?.value ?? "",
            seconds: field(row, "seconds")?.value ?? "",
        };
    }

    function readRecorded() {
        if (!recorded) return null;

        const duration = recorded.dataset.duration;
        const total = duration === "" ? null : Number(duration);

        return {
            reps: recorded.dataset.reps ?? "",
            weight: recorded.dataset.weight ?? "",
            basis: recorded.dataset.basis ?? "",
            minutes: total === null ? "" : String(Math.floor(total / 60)),
            seconds: total === null ? "" : String(total % 60),
        };
    }

    function hasValues(values) {
        return values && [
            values.reps,
            values.weight,
            values.minutes,
            values.seconds,
        ].some(value => value !== "");
    }

    rows.forEach((row, index) => {
        const button = row.querySelector("[data-copy-previous]");
        if (!button) return;

        button.addEventListener("click", () => {
            const values = index > 0
                ? readRow(rows[index - 1])
                : readRecorded();

            const feedback = row.querySelector("[data-copy-feedback]");

            if (!hasValues(values)) {
                feedback.textContent = "The previous set has no values to copy.";
                return;
            }

            const basisField = field(row, "weight_basis");

            if (basisField && !values.basis) {
                feedback.textContent =
                    "The previous weight basis was not recorded. Enter its weight and choose a basis.";
                return;
            }

            const mapping = {
                reps: "reps",
                weight_kg: "weight",
                weight_basis: "basis",
                minutes: "minutes",
                seconds: "seconds",
            };

            for (const [name, key] of Object.entries(mapping)) {
                const input = field(row, name);

                if (input) {
                    input.value = values[key];
                    input.dispatchEvent(
                        new Event("input", { bubbles: true })
                    );
                    input.dispatchEvent(
                        new Event("change", { bubbles: true })
                    );
                }
            }

            feedback.textContent = "Copied. Change any values before saving.";
        });
    });
}


if (setsEditor) {
    setsEditor.querySelectorAll("[data-weight-suggestion]").forEach(button => {
        button.addEventListener("click", () => {
            const row = button.closest(".workout-set-row");
            const weight = row.querySelector('[name$="-weight_kg"]');
            const basis = row.querySelector('[name$="-weight_basis"]');

            if (!weight || !basis) return;

            weight.value = button.dataset.weight;
            basis.value = button.dataset.basis;

            for (const input of [weight, basis]) {
                input.dispatchEvent(
                    new Event("input", { bubbles: true })
                );
                input.dispatchEvent(
                    new Event("change", { bubbles: true })
                );
            }

            row.querySelector("[data-copy-feedback]").textContent =
                "Previous weight and basis selected. Reps are unchanged.";
        });
    });
}