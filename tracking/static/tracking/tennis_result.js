(() => {
    const count = document.getElementById("id_set_count");
    if (!count) return;

    const rows = Array.from(
        document.querySelectorAll("[data-result-set]")
    );

    const update = () => {
        rows.forEach((row, index) => {
            const visible = index < Number(count.value);
            row.hidden = !visible;

            row.querySelectorAll("input").forEach(input => {
                input.disabled = !visible;
            });
        });
    };

    count.addEventListener("change", update);
    update();
})();