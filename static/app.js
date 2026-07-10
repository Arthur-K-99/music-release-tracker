// Global State
let followedArtists = [];
let allReleases = [];
let activeTab = 'releases';
let checkPollInterval = null;

// DOM Elements
const elements = {
    scanPathInput: document.getElementById('scan-path-input'),
    scanBtn: document.getElementById('scan-btn'),
    artistSearchInput: document.getElementById('artist-search-input'),
    searchSpinner: document.getElementById('search-spinner'),
    searchSuggestions: document.getElementById('search-suggestions'),
    
    statArtistsCount: document.getElementById('stat-artists-count'),
    statPendingCount: document.getElementById('stat-pending-count'),
    statDownloadedCount: document.getElementById('stat-downloaded-count'),
    checkReleasesBtn: document.getElementById('check-releases-btn'),
    
    navTabs: document.querySelectorAll('.nav-tab'),
    tabPanes: document.querySelectorAll('.tab-pane'),
    feedFilters: document.getElementById('feed-filters'),
    
    filterStatus: document.getElementById('filter-status'),
    filterType: document.getElementById('filter-type'),
    filterSearch: document.getElementById('filter-search'),
    
    releasesContainer: document.getElementById('releases-container'),
    releasesInfoText: document.getElementById('releases-info-text'),
    
    artistFilterSearch: document.getElementById('artist-filter-search'),
    artistsContainer: document.getElementById('artists-container'),
    
    toastContainer: document.getElementById('toast-container'),
    
    loaderModal: document.getElementById('loader-modal'),
    loaderTitle: document.getElementById('loader-title'),
    loaderText: document.getElementById('loader-text')
};

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    fetchData();
    checkRunningStatus(); // If page reloads while check is active
});

// Event Listeners Setup
function setupEventListeners() {
    // Tab switching
    elements.navTabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;
            switchTab(targetTab);
        });
    });

    // Scan Button
    elements.scanBtn.addEventListener('click', handleScan);

    // Manual Artist Search Input (Debounced)
    let searchTimeout;
    elements.artistSearchInput.addEventListener('input', (e) => {
        clearTimeout(searchTimeout);
        const query = e.target.value.trim();
        if (query.length < 2) {
            elements.searchSuggestions.classList.add('hidden');
            return;
        }
        
        searchTimeout = setTimeout(() => {
            searchDeezerArtists(query);
        }, 300);
    });

    // Close suggestions dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!elements.artistSearchInput.contains(e.target) && !elements.searchSuggestions.contains(e.target)) {
            elements.searchSuggestions.classList.add('hidden');
        }
    });

    // Check Releases Button
    elements.checkReleasesBtn.addEventListener('click', handleCheckReleases);

    // Filters for Releases Feed
    elements.filterStatus.addEventListener('change', renderReleases);
    elements.filterType.addEventListener('change', renderReleases);
    elements.filterSearch.addEventListener('input', renderReleases);

    // Filter for Followed Artists
    elements.artistFilterSearch.addEventListener('input', renderArtists);
}

// Fetch Initial Data
async function fetchData() {
    try {
        await Promise.all([
            fetchArtists(),
            fetchReleases()
        ]);
        updateStats();
    } catch (err) {
        showToast('Error loading initial data.', 'warning');
        console.error(err);
    }
}

// Tab Switching Logic
function switchTab(tabName) {
    activeTab = tabName;
    
    elements.navTabs.forEach(tab => {
        if (tab.dataset.tab === tabName) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });

    elements.tabPanes.forEach(pane => {
        if (pane.id === `tab-content-${tabName}`) {
            pane.classList.add('active');
        } else {
            pane.classList.remove('active');
        }
    });

    // Show/Hide filter options sidebar component
    if (tabName === 'releases') {
        elements.feedFilters.style.opacity = '1';
        elements.feedFilters.style.pointerEvents = 'all';
    } else {
        elements.feedFilters.style.opacity = '0.3';
        elements.feedFilters.style.pointerEvents = 'none';
    }
}

// Toast Notifications
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    let iconClass = 'fa-circle-check';
    if (type === 'info') iconClass = 'fa-circle-info';
    if (type === 'warning') iconClass = 'fa-triangle-exclamation';
    
    toast.innerHTML = `
        <i class="fa-solid ${iconClass}"></i>
        <span>${message}</span>
    `;
    
    elements.toastContainer.appendChild(toast);
    
    // Auto remove toast
    setTimeout(() => {
        toast.style.animation = 'fadeOut 0.4s ease forwards';
        toast.addEventListener('animationend', () => {
            toast.remove();
        });
    }, 3500);
}

// Show/Hide Loader Modal
function showLoader(title, text) {
    elements.loaderTitle.innerText = title;
    elements.loaderText.innerText = text;
    elements.loaderModal.classList.remove('hidden');
}

function hideLoader() {
    elements.loaderModal.classList.add('hidden');
}

// API: Fetch Followed Artists
async function fetchArtists() {
    const res = await fetch('/api/artists');
    followedArtists = await res.json();
    renderArtists();
}

// API: Fetch Checked Releases
async function fetchReleases() {
    const res = await fetch('/api/releases');
    allReleases = await res.json();
    renderReleases();
}

// API: Search Deezer Artists
async function searchDeezerArtists(query) {
    elements.searchSpinner.classList.remove('hidden');
    try {
        const res = await fetch(`/api/deezer/search/artist?q=${encodeURIComponent(query)}`);
        const data = await res.json();
        
        elements.searchSuggestions.innerHTML = '';
        
        if (data && data.length > 0) {
            data.slice(0, 6).forEach(artist => {
                const div = document.createElement('div');
                div.className = 'suggestion-item';
                div.innerHTML = `
                    <img class="suggestion-img" src="${artist.picture_medium || '/static/default-avatar.png'}" alt="${artist.name}">
                    <span class="suggestion-name">${artist.name}</span>
                `;
                div.addEventListener('click', () => selectArtistSuggestion(artist));
                elements.searchSuggestions.appendChild(div);
            });
            elements.searchSuggestions.classList.remove('hidden');
        } else {
            elements.searchSuggestions.innerHTML = '<div style="padding: 10px; font-size: 0.9rem; color: var(--text-secondary);">No artists found.</div>';
            elements.searchSuggestions.classList.remove('hidden');
        }
    } catch (err) {
        console.error(err);
    } finally {
        elements.searchSpinner.classList.add('hidden');
    }
}

// API: Select suggestion and follow
async function selectArtistSuggestion(deezerArtist) {
    elements.artistSearchInput.value = '';
    elements.searchSuggestions.classList.add('hidden');
    
    showLoader('Adding Artist...', `Resolving and adding ${deezerArtist.name} to followed list.`);
    
    try {
        const res = await fetch('/api/artists', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: deezerArtist.name,
                deezer_id: String(deezerArtist.id)
            })
        });
        
        const data = await res.json();
        if (data.success) {
            showToast(`Following ${deezerArtist.name}!`);
            await fetchData();
        } else {
            showToast(data.error || 'Failed to add artist', 'warning');
        }
    } catch (err) {
        showToast('Error adding artist', 'warning');
        console.error(err);
    } finally {
        hideLoader();
    }
}

// API: Handle Scan Local Library
async function handleScan() {
    const path = elements.scanPathInput.value.trim();
    if (!path) {
        showToast('Please enter a valid directory path.', 'warning');
        return;
    }
    
    showLoader('Scanning Directory...', `Walking through "${path}" to read audio tags and filenames.`);
    
    try {
        const res = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        });
        
        const data = await res.json();
        if (res.ok) {
            showToast(`Scan complete! Found ${data.found_artists.length} artists. Added ${data.added_count} new ones.`);
            await fetchData();
        } else {
            showToast(data.error || 'Failed to scan files.', 'warning');
        }
    } catch (err) {
        showToast('An error occurred during scanning.', 'warning');
        console.error(err);
    } finally {
        hideLoader();
    }
}

// API: Handle Check Releases (Triggers Background Worker)
async function handleCheckReleases() {
    if (followedArtists.length === 0) {
        showToast('Add some artists first before checking releases!', 'warning');
        return;
    }
    
    showLoader('Initializing Release Check...', 'Requesting search and update sequence.');
    
    try {
        const res = await fetch('/api/releases/check', {
            method: 'POST'
        });
        
        if (res.status === 200 || res.status === 409) {
            startPollingStatus();
        } else {
            showToast('Failed to start release checking.', 'warning');
            hideLoader();
        }
    } catch (err) {
        showToast('Error checking for releases.', 'warning');
        console.error(err);
        hideLoader();
    }
}

// Check if a background job is already active on load
async function checkRunningStatus() {
    try {
        const res = await fetch('/api/releases/check/status');
        const data = await res.json();
        if (data.active) {
            startPollingStatus();
        }
    } catch (err) {
        console.error(err);
    }
}

// Polling Loop for release check progress
function startPollingStatus() {
    if (checkPollInterval) clearInterval(checkPollInterval);
    
    showLoader('Checking Releases (0%)', 'Starting connection to Deezer API...');
    
    checkPollInterval = setInterval(async () => {
        try {
            const res = await fetch('/api/releases/check/status');
            const data = await res.json();
            
            if (data.active) {
                const pct = Math.round((data.processed / data.total) * 100) || 0;
                showLoader(
                    `Checking Releases (${pct}%)`,
                    `Current: ${data.current_artist}\nProcessed: ${data.processed} / ${data.total}\nNew Releases: ${data.new_releases}`
                );
            } else {
                clearInterval(checkPollInterval);
                checkPollInterval = null;
                hideLoader();
                
                if (data.new_releases > 0) {
                    showToast(`Check complete! Added ${data.new_releases} new releases.`, 'success');
                } else {
                    showToast('Checked! Your release feed is fully up to date.', 'info');
                }
                
                if (data.errors && data.errors.length > 0) {
                    console.warn(`${data.errors.length} errors occurred during checks.`, data.errors);
                }
                
                await fetchData();
            }
        } catch (err) {
            console.error('Error polling check status', err);
        }
    }, 1500);
}

// API: Update Release Status
async function updateStatus(releaseId, newStatus) {
    try {
        const res = await fetch(`/api/releases/${releaseId}/status`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ status: newStatus })
        });
        
        const data = await res.json();
        if (data.success) {
            // Find release in local state and update it
            const rel = allReleases.find(r => r.id === releaseId);
            if (rel) {
                rel.status = newStatus;
                updateStats();
                
                // Animate card removal if filter dictates it
                const card = document.getElementById(`release-card-${releaseId}`);
                const currentFilterStatus = elements.filterStatus.value;
                
                if (card && currentFilterStatus !== 'all' && currentFilterStatus !== newStatus) {
                    card.style.transform = 'scale(0.8)';
                    card.style.opacity = '0';
                    setTimeout(() => {
                        renderReleases();
                    }, 300);
                } else {
                    renderReleases();
                }
            }
        }
    } catch (err) {
        showToast('Failed to update release status.', 'warning');
        console.error(err);
    }
}

// API: Unfollow Artist
async function unfollowArtist(artistId, artistName) {
    if (!confirm(`Are you sure you want to stop tracking ${artistName}? This will clear all their releases.`)) {
        return;
    }
    
    showLoader('Unfollowing...', `Removing ${artistName} from database.`);
    try {
        const res = await fetch(`/api/artists/${artistId}`, {
            method: 'DELETE'
        });
        
        if (res.ok) {
            showToast(`Stopped tracking ${artistName}`);
            await fetchData();
        } else {
            showToast('Failed to unfollow artist', 'warning');
        }
    } catch (err) {
        showToast('Error removing artist', 'warning');
        console.error(err);
    } finally {
        hideLoader();
    }
}

// Copy Handlers
function copyToClipboard(text, successMsg) {
    navigator.clipboard.writeText(text).then(() => {
        showToast(successMsg, 'info');
    }).catch(err => {
        showToast('Clipboard write failed.', 'warning');
        console.error(err);
    });
}

// Stats Calculation
function updateStats() {
    elements.statArtistsCount.innerText = followedArtists.length;
    
    const pendingCount = allReleases.filter(r => r.status === 'pending').length;
    elements.statPendingCount.innerText = pendingCount;
    
    const downloadedCount = allReleases.filter(r => r.status === 'downloaded').length;
    elements.statDownloadedCount.innerText = downloadedCount;
}

// RENDER: Artists Grid
function renderArtists() {
    elements.artistsContainer.innerHTML = '';
    
    const query = elements.artistFilterSearch.value.trim().toLowerCase();
    const filtered = followedArtists.filter(a => a.name.toLowerCase().includes(query));
    
    if (filtered.length === 0) {
        elements.artistsContainer.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-user-slash"></i>
                <p>${query ? 'No matching artists found.' : 'You are not tracking any artists.'}</p>
            </div>
        `;
        return;
    }
    
    filtered.forEach(artist => {
        const imgUrl = artist.deezer_id 
            ? `https://e-cdns-images.dzcdn.net/images/artist/${artist.deezer_id}/250x250-000000-80-0-0.jpg`
            : '/static/default-avatar.png';
            
        const card = document.createElement('div');
        card.className = 'artist-card glass';
        card.innerHTML = `
            <button class="remove-artist-btn" title="Stop Tracking"><i class="fa-solid fa-xmark"></i></button>
            <img class="artist-img" src="${imgUrl}" onerror="this.src='/static/default-avatar.png'" alt="${artist.name}">
            <div class="artist-name" title="${artist.name}">${artist.name}</div>
            <div class="artist-status">${artist.deezer_id ? 'Resolved on Deezer' : 'Locally Scanned'}</div>
        `;
        
        // Remove button event listener
        card.querySelector('.remove-artist-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            unfollowArtist(artist.id, artist.name);
        });
        
        elements.artistsContainer.appendChild(card);
    });
}

// RENDER: Releases Timeline Feed
function renderReleases() {
    elements.releasesContainer.innerHTML = '';
    
    const filterStatusValue = elements.filterStatus.value;
    const filterTypeValue = elements.filterType.value;
    const searchQuery = elements.filterSearch.value.trim().toLowerCase();
    
    // Apply filters in memory
    let filtered = allReleases;
    
    if (filterStatusValue !== 'all') {
        filtered = filtered.filter(r => r.status === filterStatusValue);
    }
    
    if (filterTypeValue !== 'all') {
        filtered = filtered.filter(r => r.type === filterTypeValue || (filterTypeValue === 'single' && r.type === 'ep'));
    }
    
    if (searchQuery) {
        filtered = filtered.filter(r => 
            r.title.toLowerCase().includes(searchQuery) || 
            r.artist_name.toLowerCase().includes(searchQuery)
        );
    }
    
    elements.releasesInfoText.innerText = `Showing ${filtered.length} release${filtered.length === 1 ? '' : 's'}`;
    
    if (filtered.length === 0) {
        elements.releasesContainer.innerHTML = `
            <div class="empty-state">
                <i class="fa-solid fa-compact-disc"></i>
                <p>No releases match your current filters.</p>
            </div>
        `;
        return;
    }
    
    filtered.forEach(release => {
        const coverImg = release.cover_url || 'https://www.deezer.com/images/cover/default/250x250.jpg';
        const formattedDate = formatDate(release.release_date);
        const card = document.createElement('div');
        card.className = 'release-card glass';
        card.id = `release-card-${release.id}`;
        
        const isAlbum = release.type === 'album';
        const badgeClass = isAlbum ? 'badge-album' : 'badge-single';
        const badgeLabel = release.type.toUpperCase();
        
        // Setup control icons depending on status
        let statusToggleBtn = '';
        if (release.status === 'pending') {
            statusToggleBtn = `
                <button class="action-btn action-btn-check" data-action="download" title="Mark as Downloaded">
                    <i class="fa-solid fa-check"></i>
                </button>
                <button class="action-btn action-btn-dismiss" data-action="dismiss" title="Dismiss Release">
                    <i class="fa-solid fa-trash"></i>
                </button>
            `;
        } else if (release.status === 'downloaded') {
            statusToggleBtn = `
                <button class="action-btn action-btn-dismiss" data-action="pending" title="Mark as New/Pending">
                    <i class="fa-solid fa-arrow-rotate-left"></i>
                </button>
            `;
        } else if (release.status === 'dismissed') {
            statusToggleBtn = `
                <button class="action-btn action-btn-check" data-action="pending" title="Restore to Feed">
                    <i class="fa-solid fa-arrow-rotate-left"></i>
                </button>
            `;
        }
        
        card.innerHTML = `
            <div class="release-cover-wrapper">
                <img class="release-cover" src="${coverImg}" loading="lazy" alt="${release.title}">
                <span class="release-badge ${badgeClass}">${badgeLabel}</span>
                <span class="release-date-badge">${formattedDate}</span>
            </div>
            <div class="release-info">
                <div class="release-artist" title="${release.artist_name}">${release.artist_name}</div>
                <div class="release-title" title="${release.title}">${release.title}</div>
            </div>
            <div class="release-actions">
                <div class="action-left">
                    <button class="action-btn action-btn-copy" data-action="copy-info" title="Copy Track Info (Title - Artist)">
                        <i class="fa-solid fa-copy"></i>
                    </button>
                    <button class="action-btn action-btn-link" data-action="copy-link" title="Copy Deezer Album Link">
                        <i class="fa-solid fa-link"></i>
                    </button>
                </div>
                <div class="action-right">
                    ${statusToggleBtn}
                </div>
            </div>
        `;
        
        // Wire up click event handlers
        card.querySelector('[data-action="copy-info"]').addEventListener('click', () => {
            copyToClipboard(`${release.title} - ${release.artist_name}`, 'Song info copied to clipboard!');
        });
        
        card.querySelector('[data-action="copy-link"]').addEventListener('click', () => {
            copyToClipboard(release.link, 'Deezer link copied to clipboard!');
        });
        
        const checkBtn = card.querySelector('.action-btn-check');
        if (checkBtn) {
            checkBtn.addEventListener('click', () => {
                const action = checkBtn.dataset.action;
                updateStatus(release.id, action === 'download' ? 'downloaded' : 'pending');
            });
        }
        
        const dismissBtn = card.querySelector('.action-btn-dismiss');
        if (dismissBtn) {
            dismissBtn.addEventListener('click', () => {
                const action = dismissBtn.dataset.action;
                updateStatus(release.id, action === 'dismiss' ? 'dismissed' : 'pending');
            });
        }
        
        elements.releasesContainer.appendChild(card);
    });
}

// Date Formatter Helper
function formatDate(dateStr) {
    if (!dateStr || dateStr === '1970-01-01') return 'Unknown';
    try {
        const parts = dateStr.split('-');
        if (parts.length !== 3) return dateStr;
        const date = new Date(parts[0], parts[1] - 1, parts[2]);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch (e) {
        return dateStr;
    }
}
