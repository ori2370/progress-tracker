(() => {
    const timers = Array.from(
        document.querySelectorAll("[data-session-timer]")
    ).map(element => ({
        element,
        initialSeconds: Number(element.dataset.elapsedSeconds),
        started: performance.now(),
    })).filter(timer => Number.isFinite(timer.initialSeconds));

    if (!timers.length) return;

    const formatDuration = total => {
        const seconds = Math.max(0, Math.floor(total));
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const remainder = seconds % 60;

        if (hours) {
            return `${hours} hr ${minutes} min ${remainder} sec`;
        }

        return `${minutes} min ${remainder} sec`;
    };

    const update = () => {
        const now = performance.now();

        timers.forEach(timer => {
            const elapsed = timer.initialSeconds
                + (now - timer.started) / 1000;

            timer.element.textContent = formatDuration(elapsed);
        });
    };

    update();
    window.setInterval(update, 1000);
})();