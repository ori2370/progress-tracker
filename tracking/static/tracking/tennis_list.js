class TennisSessionSelectionController {
    constructor(form) {
        this.form = form;
        this.menu = document.querySelector(".actions-menu");
        this.startButton = document.querySelector("#start-selection");
        this.cancelButton = form.querySelector("#cancel-selection");
        this.toolbar = form.querySelector("#selection-toolbar");
        this.countLabel = form.querySelector("#selection-count");
        this.deleteButton = form.querySelector("#delete-selected");

        this.selectors = [
            ...form.querySelectorAll(".session-selector")
        ];

        this.checkboxes = [
            ...form.querySelectorAll('input[name="sessions"]')
        ];

        this.startButton.disabled = this.checkboxes.length === 0;

        this.startButton.addEventListener("click", () => {
            this.setSelectionMode(true);
        });

        this.cancelButton.addEventListener("click", () => {
            this.setSelectionMode(false);
        });

        this.form.addEventListener("change", () => {
            this.updateCount();
        });

        this.form.addEventListener("submit", (event) => {
            if (this.selectedCount() === 0) {
                event.preventDefault();
            }
        });

        this.updateCount();
    }

    selectedCount() {
        return this.checkboxes.filter(
            checkbox => checkbox.checked
        ).length;
    }

    setSelectionMode(enabled) {
        this.toolbar.hidden = !enabled;
        this.menu.open = false;

        this.selectors.forEach(selector => {
            selector.hidden = !enabled;
        });

        this.checkboxes.forEach(checkbox => {
            checkbox.disabled = !enabled;

            if (!enabled) {
                checkbox.checked = false;
            }
        });

        this.updateCount();

        if (enabled && this.checkboxes.length > 0) {
            this.checkboxes[0].focus();
        } else if (!enabled) {
            this.menu.querySelector("summary").focus();
        }
    }

    updateCount() {
        const count = this.selectedCount();

        this.countLabel.textContent = `${count} selected`;
        this.deleteButton.textContent = `Delete selected (${count})`;
        this.deleteButton.disabled = count === 0;
    }
}

const selectionForm = document.querySelector(
    "#session-selection-form"
);

if (selectionForm) {
    new TennisSessionSelectionController(selectionForm);
}