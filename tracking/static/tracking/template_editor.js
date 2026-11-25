(() => {
    const form = document.getElementById("template-editor-form");
    const list = document.getElementById("template-exercise-list");
    const status = document.getElementById("order-status");

    if (!form) return;

    let dirty = false;
    let dragged = null;
    let pending = null;
    let holdTimer = null;
    let frame = null;
    let pointerY = 0;
    let mousePointer = null;
    let suppressClickUntil = 0;

    const rows = () => (
        list ? Array.from(list.querySelectorAll("[data-exercise-row]")) : []
    );

    const order = () => rows().map(
        row => row.querySelector('[name="exercise_order"]').value
    ).join(",");

    const updatePositions = () => {
        rows().forEach((row, index) => {
            row.querySelector("[data-position]").textContent = index + 1;
        });
    };

    const markChanged = () => {
        dirty = true;
        updatePositions();
        status.textContent = "Order changed. Save changes to keep it.";
    };

    form.addEventListener("input", () => {
        dirty = true;
    });

    form.addEventListener("submit", () => {
        dirty = false;
    });

    window.addEventListener("beforeunload", event => {
        if (!dirty) return;

        event.preventDefault();
        event.returnValue = "";
    });

    if (!list) return;

    const cancelHold = () => {
        clearTimeout(holdTimer);
        holdTimer = null;
        pending = null;
    };

    const animateDrag = () => {
        if (!dragged) return;

        const scroller = list.closest(".template-exercise-scroll");
        const bounds = scroller.getBoundingClientRect();

        if (pointerY < bounds.top + 45) {
            scroller.scrollTop -= 7;
        } else if (pointerY > bounds.bottom - 45) {
            scroller.scrollTop += 7;
        }

        const before = rows().find(row => {
            if (row === dragged) return false;

            const rect = row.getBoundingClientRect();
            return pointerY < rect.top + rect.height / 2;
        });

        const previous = order();
        list.insertBefore(dragged, before || null);

        if (order() !== previous) {
            markChanged();
        }

        frame = requestAnimationFrame(animateDrag);
    };

    const beginDrag = (row, y) => {
        dragged = row;
        pointerY = y;
        row.classList.add("is-dragging");
        status.textContent = "Move the exercise, then release to place it.";
        frame = requestAnimationFrame(animateDrag);
    };

    const finishDrag = () => {
        cancelHold();

        if (!dragged) return;

        dragged.classList.remove("is-dragging");
        dragged = null;
        suppressClickUntil = Date.now() + 400;

        if (frame !== null) {
            cancelAnimationFrame(frame);
            frame = null;
        }

        status.textContent = dirty
            ? "Save changes to keep your edits."
            : "Exercise placed.";
    };

    // Mouse dragging starts immediately.
    list.addEventListener("pointerdown", event => {
        if (
            event.pointerType !== "mouse"
            || event.button !== 0
            || event.target.closest("a, button, input")
        ) return;

        const row = event.target.closest("[data-exercise-row]");
        if (!row) return;

        event.preventDefault();
        mousePointer = event.pointerId;
        list.setPointerCapture(mousePointer);
        beginDrag(row, event.clientY);
    });

    list.addEventListener("pointermove", event => {
        if (event.pointerId === mousePointer && dragged) {
            pointerY = event.clientY;
        }
    });

    const finishMouse = event => {
        if (event.pointerId !== mousePointer) return;

        const pointer = mousePointer;
        mousePointer = null;
        finishDrag();

        if (list.hasPointerCapture(pointer)) {
            list.releasePointerCapture(pointer);
        }
    };

    list.addEventListener("pointerup", finishMouse);
    list.addEventListener("pointercancel", finishMouse);
    list.addEventListener("lostpointercapture", finishMouse);

    // Touch scrolling remains normal until a row is held for 350 ms.
    list.addEventListener("touchstart", event => {
        cancelHold();

        if (
            event.touches.length !== 1
            || event.target.closest("a, button, input")
        ) return;

        const row = event.target.closest("[data-exercise-row]");
        if (!row) return;

        const touch = event.touches[0];
        pending = {
            row,
            x: touch.clientX,
            y: touch.clientY,
        };

        holdTimer = setTimeout(() => {
            if (!pending) return;

            const { row, y } = pending;
            pending = null;
            holdTimer = null;
            beginDrag(row, y);
        }, 350);
    }, { passive: true });

    list.addEventListener("touchmove", event => {
        if (event.touches.length !== 1) {
            finishDrag();
            return;
        }

        const touch = event.touches[0];

        if (dragged) {
            event.preventDefault();
            pointerY = touch.clientY;
        } else if (
            pending
            && Math.hypot(
                touch.clientX - pending.x,
                touch.clientY - pending.y
            ) > 8
        ) {
            cancelHold();
        }
    }, { passive: false });

    list.addEventListener("touchend", finishDrag);
    list.addEventListener("touchcancel", finishDrag);

    list.addEventListener("contextmenu", event => {
        if (dragged || pending) {
            event.preventDefault();
        }
    });

    list.addEventListener("click", event => {
        if (Date.now() < suppressClickUntil) {
            event.preventDefault();
            event.stopPropagation();
        }
    }, true);

    // Keyboard alternative without extra visible buttons.
    list.addEventListener("keydown", event => {
        if (
            !event.altKey
            || !["ArrowUp", "ArrowDown"].includes(event.key)
        ) return;

        const row = event.target.closest("[data-exercise-row]");
        if (!row || event.target !== row) return;

        event.preventDefault();

        if (event.key === "ArrowUp") {
            const previous = row.previousElementSibling;
            if (!previous) return;

            list.insertBefore(row, previous);
        } else {
            const next = row.nextElementSibling;
            if (!next) return;

            list.insertBefore(next, row);
        }

        markChanged();
        row.focus({ preventScroll: true });
        row.scrollIntoView({ block: "nearest" });
    });

    updatePositions();
})();