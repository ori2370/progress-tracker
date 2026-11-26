(() => {
    document.querySelectorAll('[name="recording_mode"]').forEach(mode => {
        const form = mode.closest("form");
        const duration = form.querySelector('[name="duration_minutes"]');
        const wrapper = duration?.closest(".form-field");

        if (!duration || !wrapper) return;

        const update = () => {
            const completed = mode.value === "completed";

            wrapper.hidden = !completed;
            duration.disabled = !completed;
        };

        mode.addEventListener("change", update);
        update();
    });
})();