(() => {
    const form = document.getElementById("exercise-form");
    const searchButton = document.getElementById("find-videos");
    const videoInput = document.getElementById("id_video_url");
    const results = document.getElementById("video-results");
    const status = document.getElementById("video-search-status");

    if (!form || !searchButton || !videoInput || !results || !status) {
        return;
    }

    function createVideoCard(video) {
        const card = document.createElement("article");
        card.className = "card video-result";

        const image = document.createElement("img");
        image.src = video.thumbnail;
        image.alt = "";
        image.loading = "lazy";
        image.referrerPolicy = "no-referrer";

        const title = document.createElement("h3");
        title.textContent = video.title;

        const channel = document.createElement("p");
        channel.className = "muted";
        channel.textContent =
            `${video.channel} · ${video.duration || "Duration unavailable"}`;

        const actions = document.createElement("div");
        actions.className = "form-actions";

        const preview = document.createElement("a");
        preview.className = "button secondary";
        preview.href = video.url;
        preview.target = "_blank";
        preview.rel = "noopener noreferrer";
        preview.textContent = "Preview ↗";
        preview.setAttribute(
            "aria-label",
            `Preview ${video.title} on YouTube (opens in a new tab)`
        );

        const choose = document.createElement("button");
        choose.type = "button";
        choose.textContent = "Use this video";
        choose.setAttribute("aria-label", `Use ${video.title}`);

        choose.addEventListener("click", () => {
            videoInput.value = video.url;
            status.textContent = "Video selected. Saving exercise…";
            let stayField = form.querySelector('input[name="stay_on_form"]');

            if (!stayField) {
                stayField = document.createElement("input");
                stayField.type = "hidden";
                stayField.name = "stay_on_form";
                form.append(stayField);
            }

            stayField.value = "1";
            form.requestSubmit();
        });

        actions.append(preview, choose);
        card.append(image, title, channel, actions);

        return card;
    }

    searchButton.addEventListener("click", async () => {
        searchButton.disabled = true;
        results.replaceChildren();
        results.setAttribute("aria-busy", "true");
        status.textContent = "Finding demonstrations…";

        try {
            const response = await fetch(searchButton.dataset.searchUrl, {
                headers: {"Accept": "application/json"},
                credentials: "same-origin",
            });

            if (response.redirected) {
                throw new Error(
                    "Your session may have expired. Refresh and sign in again."
                );
            }

            const contentType = response.headers.get("content-type") || "";

            if (!contentType.includes("application/json")) {
                throw new Error("Video search is temporarily unavailable.");
            }

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || "Video search failed.");
            }

            if (!Array.isArray(data.videos)) {
                throw new Error("Unexpected video search response.");
            }

            for (const video of data.videos) {
                results.append(createVideoCard(video));
            }

            status.textContent = data.videos.length
                ? "Choose a demonstration below."
                : "No videos found. You can still paste a link manually.";
        } catch (error) {
            status.textContent = error.message || "Could not load videos.";
        } finally {
            searchButton.disabled = false;
            results.removeAttribute("aria-busy");
        }
    });
})();