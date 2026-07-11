const state = {
    artists: [],
    releases: [],
    stats: {},
    page: 1,
    pages: 1,
    total: 0,
    artistPage: 1,
    artistPages: 1,
    activeTab: "releases",
    checkTimer: null,
    scanTimer: null,
    searchController: null,
};

const $ = (id) => document.getElementById(id);
const elements = {
    artistSearch: $("artist-search-input"),
    suggestions: $("search-suggestions"),
    searchSpinner: $("search-spinner"),
    checkButton: $("check-releases-btn"),
    scanPath: $("scan-path-input"),
    scanButton: $("scan-btn"),
    libraryToggle: $("toggle-library-btn"),
    libraryPanel: $("library-panel"),
    filterStatus: $("filter-status"),
    filterType: $("filter-type"),
    filterDays: $("filter-days"),
    filterSearch: $("filter-search"),
    releases: $("releases-container"),
    artists: $("artists-container"),
    artistFilter: $("artist-filter-search"),
    artistPagination: $("artist-pagination"),
    previousArtist: $("prev-artist-page"),
    nextArtist: $("next-artist-page"),
    artistPageInfo: $("artist-page-info"),
    pagination: $("pagination"),
    previous: $("prev-page"),
    next: $("next-page"),
    pageInfo: $("page-info"),
    resultInfo: $("releases-info-text"),
    queueTitle: $("queue-title"),
    jobBanner: $("job-banner"),
    jobKicker: $("job-kicker"),
    jobTitle: $("job-title"),
    jobDetail: $("job-detail"),
    jobProgress: $("job-progress"),
    cancelJob: $("cancel-job-btn"),
    toasts: $("toast-container"),
};

document.addEventListener("DOMContentLoaded", async () => {
    const configuredDays = String(window.SOUNDRADAR_CONFIG?.lookbackDays || 90);
    if ([...elements.filterDays.options].some((option) => option.value === configuredDays)) {
        elements.filterDays.value = configuredDays;
    }
    bindEvents();
    await refreshDashboard();
    await resumeJobs();
});

function bindEvents() {
    document.querySelectorAll("[data-tab]").forEach((tab) => {
        tab.addEventListener("click", () => switchTab(tab.dataset.tab));
    });
    elements.libraryToggle.addEventListener("click", toggleLibraryPanel);
    elements.checkButton.addEventListener("click", startReleaseCheck);
    elements.scanButton.addEventListener("click", startScan);
    elements.cancelJob.addEventListener("click", cancelReleaseCheck);

    elements.filterStatus.addEventListener("change", filtersChanged);
    elements.filterType.addEventListener("change", filtersChanged);
    elements.filterDays.addEventListener("change", filtersChanged);
    elements.filterSearch.addEventListener("input", debounce(filtersChanged, 280));
    elements.artistFilter.addEventListener("input", () => {
        state.artistPage = 1;
        renderArtists();
    });

    elements.previous.addEventListener("click", () => changePage(state.page - 1));
    elements.next.addEventListener("click", () => changePage(state.page + 1));
    elements.previousArtist.addEventListener("click", () => changeArtistPage(state.artistPage - 1));
    elements.nextArtist.addEventListener("click", () => changeArtistPage(state.artistPage + 1));
    elements.artistSearch.addEventListener("input", debounce(searchArtists, 300));
    elements.artistSearch.addEventListener("keydown", (event) => {
        if (event.key === "Escape") hideSuggestions();
    });
    document.addEventListener("click", (event) => {
        if (!event.target.closest(".artist-search")) hideSuggestions();
    });
}

async function api(url, options = {}) {
    const response = await fetch(url, options);
    let payload = null;
    try {
        payload = await response.json();
    } catch (_) {
        payload = {};
    }
    if (!response.ok) {
        const error = new Error(payload.error || `Request failed (${response.status})`);
        error.status = response.status;
        throw error;
    }
    return payload;
}

async function refreshDashboard() {
    try {
        await Promise.all([fetchArtists(), fetchStats(), fetchReleases()]);
    } catch (error) {
        showToast(error.message || "Could not load SoundRadar.", "warning");
    }
}

async function fetchArtists() {
    state.artists = await api("/api/artists");
    if (state.activeTab === "artists") renderArtists();
}

async function fetchStats() {
    const days = elements.filterDays.value;
    state.stats = await api(`/api/stats?days=${encodeURIComponent(days)}`);
    $("stat-pending-count").textContent = formatNumber(state.stats.pending);
    $("stat-upcoming-count").textContent = formatNumber(state.stats.upcoming);
    $("stat-artists-count").textContent = formatNumber(state.stats.artists);
    $("stat-unresolved-count").textContent = formatNumber(state.stats.unresolved_artists);
    $("stat-artists-detail").textContent = `${formatNumber(state.stats.confirmed_artists)} confirmed`;
    $("signal-status").textContent = state.stats.unresolved_artists
        ? `${state.stats.unresolved_artists} matches need review`
        : "Library signal is clear";
    $("signal-detail").textContent = `${formatNumber(state.stats.visible_releases)} releases in this window`;
}

async function fetchReleases() {
    elements.releases.setAttribute("aria-busy", "true");
    const params = new URLSearchParams({
        status: elements.filterStatus.value,
        type: elements.filterType.value,
        days: elements.filterDays.value,
        search: elements.filterSearch.value.trim(),
        page: String(state.page),
        per_page: "30",
    });
    try {
        const data = await api(`/api/releases?${params}`);
        state.releases = data.items;
        state.page = data.page;
        state.pages = data.pages;
        state.total = data.total;
        renderReleases();
    } finally {
        elements.releases.removeAttribute("aria-busy");
    }
}

function filtersChanged() {
    state.page = 1;
    updateQueueTitle();
    Promise.all([fetchReleases(), fetchStats()]).catch((error) => showToast(error.message, "warning"));
}

function updateQueueTitle() {
    const labels = {
        pending: "Needs attention",
        downloaded: "Downloaded",
        dismissed: "Dismissed",
        all: "All releases",
    };
    elements.queueTitle.textContent = labels[elements.filterStatus.value];
}

function renderReleases() {
    elements.releases.replaceChildren();
    elements.resultInfo.textContent = `${formatNumber(state.total)} ${state.total === 1 ? "release" : "releases"}`;
    updateQueueTitle();

    if (!state.releases.length) {
        elements.releases.append(emptyState(
            "Your queue is clear.",
            elements.filterStatus.value === "pending"
                ? "Try a wider date window, confirm unresolved artists, or run a release check."
                : "No releases match the current filters."
        ));
    } else {
        const fragment = document.createDocumentFragment();
        state.releases.forEach((release) => fragment.append(createReleaseCard(release)));
        elements.releases.append(fragment);
    }

    elements.pagination.classList.toggle("hidden", state.pages <= 1);
    elements.pageInfo.textContent = `Page ${state.page} of ${state.pages}`;
    elements.previous.disabled = state.page <= 1;
    elements.next.disabled = state.page >= state.pages;
}

function createReleaseCard(release) {
    const card = create("article", "release-card");
    const upcoming = isUpcoming(release.release_date);
    if (upcoming) card.classList.add("upcoming");

    const coverWrap = create("div", "cover-wrap");
    const image = create("img");
    image.src = safeImageUrl(release.cover_url);
    image.alt = `${release.title} cover`;
    image.loading = "lazy";
    image.addEventListener("error", () => {
        if (!image.src.endsWith("/static/default-avatar.svg")) image.src = "/static/default-avatar.svg";
    }, { once: true });
    const datePill = create("span", "date-pill", formatDate(release.release_date));
    coverWrap.append(image, datePill);

    const body = create("div", "release-body");
    const meta = create("div", "release-meta");
    meta.append(
        create("span", "release-type", upcoming ? "Upcoming" : release.type),
        create("span", "", release.status)
    );
    const title = create("strong", "release-title", release.title);
    title.title = release.title;
    const artist = create("span", "release-artist", release.artist_name);
    artist.title = release.artist_name;
    const actions = create("div", "release-actions");
    actions.append(
        actionButton("Copy info", () => copyText(`${release.title} - ${release.artist_name}`)),
        actionButton("Deezer link", () => copyText(release.link))
    );
    if (release.status === "pending") {
        actions.append(
            actionButton("Downloaded", () => updateReleaseStatus(release.id, "downloaded"), "positive"),
            actionButton("Dismiss", () => updateReleaseStatus(release.id, "dismissed"), "danger")
        );
    } else {
        actions.append(actionButton("Restore", () => updateReleaseStatus(release.id, "pending"), "positive"));
    }
    body.append(meta, title, artist, actions);
    card.append(coverWrap, body);
    return card;
}

function renderArtists() {
    const query = elements.artistFilter.value.trim().toLowerCase();
    const filtered = state.artists.filter((artist) => artist.name.toLowerCase().includes(query));
    const perPage = 60;
    state.artistPages = Math.max(1, Math.ceil(filtered.length / perPage));
    state.artistPage = Math.min(state.artistPage, state.artistPages);
    const start = (state.artistPage - 1) * perPage;
    const visible = filtered.slice(start, start + perPage);
    elements.artists.replaceChildren();
    if (!filtered.length) {
        elements.artists.append(emptyState("No artists found.", query ? "Try a different name." : "Scan a library or add an artist above."));
        elements.artistPagination.classList.add("hidden");
        return;
    }
    const fragment = document.createDocumentFragment();
    visible.forEach((artist) => fragment.append(createArtistCard(artist)));
    elements.artists.append(fragment);
    elements.artistPagination.classList.toggle("hidden", state.artistPages <= 1);
    elements.artistPageInfo.textContent = `Page ${state.artistPage} of ${state.artistPages} · ${formatNumber(filtered.length)} artists`;
    elements.previousArtist.disabled = state.artistPage <= 1;
    elements.nextArtist.disabled = state.artistPage >= state.artistPages;
}

function createArtistCard(artist) {
    const card = create("article", "artist-card");
    const image = create("img");
    image.src = safeImageUrl(artist.picture_url);
    image.alt = "";
    image.loading = "lazy";
    image.addEventListener("error", () => { image.src = "/static/default-avatar.svg"; }, { once: true });

    const copy = create("div");
    const name = create("div", "artist-name", artist.name);
    name.title = artist.name;
    const isConfirmed = artist.match_status === "confirmed";
    const detail = isConfirmed
        ? `${formatNumber(artist.release_count)} releases · confirmed`
        : "Needs a Deezer match";
    const status = create("div", `artist-state${isConfirmed ? "" : " unresolved"}`, detail);
    copy.append(name, status);
    if (!isConfirmed) {
        const match = actionButton("Find match", () => beginArtistMatch(artist.name));
        match.classList.add("match-button");
        copy.append(match);
    }

    const remove = create("button", "remove-button", "×");
    remove.type = "button";
    remove.setAttribute("aria-label", `Stop following ${artist.name}`);
    remove.title = "Stop following";
    remove.addEventListener("click", () => removeArtist(artist));
    card.append(image, copy, remove);
    return card;
}

async function updateReleaseStatus(releaseId, status) {
    try {
        await api(`/api/releases/${releaseId}/status`, jsonOptions("POST", { status }));
        await Promise.all([fetchReleases(), fetchStats()]);
    } catch (error) {
        showToast(error.message, "warning");
    }
}

async function removeArtist(artist) {
    const confirmed = window.confirm(`Stop following ${artist.name}? Their saved releases will also be removed.`);
    if (!confirmed) return;
    try {
        await api(`/api/artists/${artist.id}`, { method: "DELETE" });
        showToast(`Stopped following ${artist.name}.`);
        await refreshDashboard();
    } catch (error) {
        showToast(error.message, "warning");
    }
}

function beginArtistMatch(name) {
    elements.artistSearch.value = name;
    elements.artistSearch.focus();
    searchArtists();
    window.scrollTo({ top: 0, behavior: "smooth" });
}

async function searchArtists() {
    const query = elements.artistSearch.value.trim();
    if (query.length < 2) {
        hideSuggestions();
        return;
    }
    if (state.searchController) state.searchController.abort();
    state.searchController = new AbortController();
    elements.searchSpinner.classList.remove("hidden");
    try {
        const response = await fetch(`/api/deezer/search/artist?q=${encodeURIComponent(query)}`, {
            signal: state.searchController.signal,
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Artist search failed.");
        renderSuggestions(data);
    } catch (error) {
        if (error.name !== "AbortError") showToast(error.message, "warning");
    } finally {
        elements.searchSpinner.classList.add("hidden");
    }
}

function renderSuggestions(artists) {
    elements.suggestions.replaceChildren();
    if (!artists.length) {
        elements.suggestions.append(create("div", "suggestion-empty", "No Deezer artists found."));
    } else {
        artists.forEach((artist) => {
            const option = create("button", "suggestion");
            option.type = "button";
            option.setAttribute("role", "option");
            const image = create("img");
            image.src = safeImageUrl(artist.picture_medium);
            image.alt = "";
            image.addEventListener("error", () => { image.src = "/static/default-avatar.svg"; }, { once: true });
            const copy = create("span");
            copy.append(
                create("strong", "", artist.name),
                create("small", "", `${formatNumber(artist.nb_album || 0)} releases on Deezer`)
            );
            option.append(image, copy);
            option.addEventListener("click", () => followArtist(artist));
            elements.suggestions.append(option);
        });
    }
    elements.suggestions.classList.remove("hidden");
}

async function followArtist(artist) {
    hideSuggestions();
    try {
        const data = await api("/api/artists", jsonOptions("POST", {
            name: artist.name,
            deezer_id: String(artist.id),
            picture_url: artist.picture_medium,
        }));
        elements.artistSearch.value = "";
        showToast(data.created ? `Following ${artist.name}.` : `${artist.name} is confirmed.`);
        await Promise.all([fetchArtists(), fetchStats()]);
    } catch (error) {
        showToast(error.message, "warning");
    }
}

async function startReleaseCheck() {
    elements.checkButton.disabled = true;
    try {
        await api("/api/releases/check", { method: "POST" });
        showJob("Release check", "Reading confirmed artist catalogs…", "Starting", 0, true);
        pollReleaseCheck();
    } catch (error) {
        if (error.status === 409) pollReleaseCheck();
        else showToast(error.message, "warning");
    }
}

async function pollReleaseCheck() {
    clearTimeout(state.checkTimer);
    try {
        const data = await api("/api/releases/check/status");
        const progress = data.total ? Math.round((data.processed / data.total) * 100) : 0;
        if (data.active) {
            const detail = data.total
                ? `${data.processed} of ${data.total} confirmed artists · ${data.new_releases} new`
                : "Preparing confirmed artists";
            showJob("Release check", data.current_artist || "Checking catalogs…", detail, progress, true);
            state.checkTimer = setTimeout(pollReleaseCheck, 900);
        } else {
            elements.checkButton.disabled = false;
            hideJob();
            if (data.finished_at) {
                const suffix = data.skipped_unresolved ? ` ${data.skipped_unresolved} unresolved artists were safely skipped.` : "";
                showToast(`Release check complete: ${data.new_releases} new.${suffix}`);
                if (data.errors?.length) showToast(`${data.errors.length} artists could not be checked.`, "warning");
                await refreshDashboard();
            }
        }
    } catch (error) {
        elements.checkButton.disabled = false;
        hideJob();
        showToast(error.message, "warning");
    }
}

async function cancelReleaseCheck() {
    try {
        await api("/api/releases/check/cancel", { method: "POST" });
        elements.cancelJob.disabled = true;
        elements.cancelJob.textContent = "Cancelling…";
    } catch (error) {
        showToast(error.message, "warning");
    }
}

async function startScan() {
    const path = elements.scanPath.value.trim();
    if (!path) return showToast("Enter a music folder path.", "warning");
    elements.scanButton.disabled = true;
    try {
        await api("/api/scan", jsonOptions("POST", { path }));
        showJob("Library scan", "Reading local audio metadata…", path, 10, false);
        pollScan();
    } catch (error) {
        elements.scanButton.disabled = false;
        showToast(error.message, "warning");
    }
}

async function pollScan() {
    clearTimeout(state.scanTimer);
    try {
        const data = await api("/api/scan/status");
        if (data.active) {
            showJob(
                "Library scan",
                data.current_file || "Reading local audio metadata…",
                `${formatNumber(data.files_processed)} files · ${formatNumber(data.artists_found)} artists`,
                35,
                false
            );
            state.scanTimer = setTimeout(pollScan, 700);
        } else {
            elements.scanButton.disabled = false;
            hideJob();
            if (data.error) showToast(data.error, "warning");
            else if (data.finished_at) {
                showToast(`Scan complete: ${data.artists_added} new artists added for review.`);
                await Promise.all([fetchArtists(), fetchStats()]);
            }
        }
    } catch (error) {
        elements.scanButton.disabled = false;
        hideJob();
        showToast(error.message, "warning");
    }
}

async function resumeJobs() {
    try {
        const [check, scan] = await Promise.all([
            api("/api/releases/check/status"),
            api("/api/scan/status"),
        ]);
        if (check.active) pollReleaseCheck();
        else if (scan.active) pollScan();
    } catch (_) {
        // The dashboard remains usable if job state cannot be restored.
    }
}

function showJob(kicker, title, detail, progress, cancellable) {
    elements.jobKicker.textContent = kicker;
    elements.jobTitle.textContent = title;
    elements.jobDetail.textContent = detail;
    elements.jobProgress.style.width = `${Math.max(3, Math.min(progress, 100))}%`;
    elements.cancelJob.classList.toggle("hidden", !cancellable);
    elements.cancelJob.disabled = false;
    elements.cancelJob.textContent = "Cancel";
    elements.jobBanner.classList.remove("hidden");
}

function hideJob() {
    elements.jobBanner.classList.add("hidden");
}

function switchTab(tabName) {
    state.activeTab = tabName;
    document.querySelectorAll("[data-tab]").forEach((button) => {
        const selected = button.dataset.tab === tabName;
        button.classList.toggle("active", selected);
        button.setAttribute("aria-selected", String(selected));
    });
    const releasesSelected = tabName === "releases";
    $("releases-pane").hidden = !releasesSelected;
    $("releases-pane").classList.toggle("active", releasesSelected);
    $("artists-pane").hidden = releasesSelected;
    $("artists-pane").classList.toggle("active", !releasesSelected);
    if (!releasesSelected) renderArtists();
}

function toggleLibraryPanel() {
    const opening = elements.libraryPanel.classList.contains("hidden");
    elements.libraryPanel.classList.toggle("hidden", !opening);
    elements.libraryToggle.setAttribute("aria-expanded", String(opening));
}

function changePage(page) {
    if (page < 1 || page > state.pages || page === state.page) return;
    state.page = page;
    fetchReleases()
        .then(() => elements.releases.scrollIntoView({ behavior: "smooth", block: "start" }))
        .catch((error) => showToast(error.message, "warning"));
}

function changeArtistPage(page) {
    if (page < 1 || page > state.artistPages || page === state.artistPage) return;
    state.artistPage = page;
    renderArtists();
    elements.artists.scrollIntoView({ behavior: "smooth", block: "start" });
}

function actionButton(label, handler, extraClass = "") {
    const button = create("button", `action-button ${extraClass}`.trim(), label);
    button.type = "button";
    button.addEventListener("click", handler);
    return button;
}

function emptyState(title, detail) {
    const empty = create("div", "empty-state");
    const copy = create("div");
    copy.append(create("strong", "", title), create("span", "", detail));
    empty.append(copy);
    return empty;
}

function create(tag, className = "", text = null) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== null) element.textContent = String(text);
    return element;
}

function safeImageUrl(value) {
    if (!value) return "/static/default-avatar.svg";
    try {
        const url = new URL(value, window.location.origin);
        if (url.origin === window.location.origin || url.protocol === "https:") return url.href;
    } catch (_) {
        // Use the local fallback below.
    }
    return "/static/default-avatar.svg";
}

function formatDate(value) {
    if (!value) return "Unknown";
    const [year, month, day] = value.split("-").map(Number);
    const parsed = new Date(year, month - 1, day);
    if (Number.isNaN(parsed.getTime())) return value;
    return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

function isUpcoming(value) {
    if (!value) return false;
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const [year, month, day] = value.split("-").map(Number);
    return new Date(year, month - 1, day) > today;
}

function formatNumber(value) {
    return new Intl.NumberFormat().format(Number(value) || 0);
}

function jsonOptions(method, body) {
    return {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    };
}

function debounce(fn, wait) {
    let timer;
    return (...args) => {
        clearTimeout(timer);
        timer = setTimeout(() => fn(...args), wait);
    };
}

async function copyText(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast("Copied to clipboard.");
    } catch (_) {
        showToast("Clipboard access was unavailable.", "warning");
    }
}

function showToast(message, type = "success") {
    const toast = create("div", `toast ${type}`, message);
    elements.toasts.append(toast);
    window.setTimeout(() => toast.remove(), 4200);
}

function hideSuggestions() {
    elements.suggestions.classList.add("hidden");
}
