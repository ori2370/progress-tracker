(() => {
    const form = document.getElementById("template-exercise-form");
    if (!form) return;

    const definition = form.querySelector('[name="definition"]');
    const setsLabel = form.querySelector('label[for="id_planned_sets"]');

    if (!definition) return;

    const setVisible = (name, visible) => {
        const wrapper = form.querySelector(`[data-field="${name}"]`);
        if (!wrapper) return;

        wrapper.hidden = !visible;

        wrapper.querySelectorAll("input").forEach(input => {
            input.disabled = !visible;
        });
    };

    const updateMode = () => {
        const selected = definition.selectedOptions[0];
        const mode = selected?.dataset.trackingMode;
        const timed = mode === "duration";
        const strength = mode === "strength";

        setVisible("target_reps", strength);
        setVisible("target_minutes", timed);
        setVisible("target_seconds", timed);

        if (setsLabel) {
            setsLabel.textContent = timed
                ? "Rounds *"
                : "Sets *";
        }
    };

    definition.addEventListener("change", updateMode);
    updateMode();
})();