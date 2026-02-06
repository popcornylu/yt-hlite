// ============= Configuration =============
const youtubeVideoId = new URLSearchParams(window.location.search).get('v');
let videoDuration = 0;

// ============= State =============
let highlights = []; // client-side highlight objects
let selectedHighlightId = null;
let recordingStart = null;
let mode = 'watch';
let highlightCounter = 0;

// Sequential playback state
let isPlayingAll = false;
let playAllClipIndex = 0;
let playAllClips = [];

// Timeline zoom modes
const ZOOM_MODES = [
    { label: 'Hidden', hidden: true, getPixelsPerSecond: () => null },
    { label: 'Full length', hidden: false, getPixelsPerSecond: () => null },
    { label: '1 inch = 5s', hidden: false, getPixelsPerSecond: () => 96 / 5 },
];
let currentZoomMode = 1;
let pixelsPerSecond = ZOOM_MODES[1].getPixelsPerSecond();

// YouTube player
let ytPlayer = null;
let ytPlayerReady = false;
let ytTimeUpdateInterval = null;

// Jump amounts
const JUMP_LARGE = 5;
const JUMP_SMALL = 2;

// ============= VideoPlayer Interface =============
const VideoPlayer = {
    getCurrentTime() {
        if (ytPlayer && ytPlayerReady) return ytPlayer.getCurrentTime() || 0;
        return 0;
    },
    setCurrentTime(time) {
        time = Math.max(0, Math.min(time, this.getDuration()));
        if (ytPlayer && ytPlayerReady) ytPlayer.seekTo(time, true);
    },
    play() {
        if (ytPlayer && ytPlayerReady) ytPlayer.playVideo();
    },
    pause() {
        if (ytPlayer && ytPlayerReady) ytPlayer.pauseVideo();
    },
    isPaused() {
        if (ytPlayer && ytPlayerReady) return ytPlayer.getPlayerState() !== YT.PlayerState.PLAYING;
        return true;
    },
    getDuration() {
        if (ytPlayer && ytPlayerReady) return ytPlayer.getDuration() || videoDuration;
        return videoDuration;
    },
    getPlaybackRate() {
        if (ytPlayer && ytPlayerReady) return ytPlayer.getPlaybackRate();
        return 1;
    },
    setPlaybackRate(rate) {
        rate = Math.round(Math.max(0.1, Math.min(rate, 4.0)) * 10) / 10;
        if (ytPlayer && ytPlayerReady) ytPlayer.setPlaybackRate(rate);
    }
};

// ============= Initialize =============
document.addEventListener('DOMContentLoaded', () => {
    if (!youtubeVideoId || !/^[a-zA-Z0-9_-]{11}$/.test(youtubeVideoId)) {
        showError('Invalid or missing video ID');
        return;
    }

    loadVideoData(youtubeVideoId);
});

// ============= Load Video Data from Worker =============
async function loadVideoData(videoId) {
    try {
        const response = await fetch(`${CONFIG.WORKER_URL}/api/yt-metadata?v=${videoId}`);
        const data = await response.json();

        if (data.error) {
            showError(data.error);
            return;
        }

        // Update page title
        document.title = `${data.title} - YouTube Highlights`;

        // Load highlights from description
        highlights = data.highlights.map((h, i) => ({
            id: `desc_${i + 1}`,
            start_time: h.start_time,
            end_time: h.end_time,
            duration: h.end_time - h.start_time,
            source: 'description',
            label: null,
        }));
        highlightCounter = highlights.length;

        // Determine initial mode based on highlights
        mode = highlights.length > 0 ? 'watch' : 'edit';

        // Hide loading, show UI
        document.getElementById('loading-state').classList.add('hidden');
        document.getElementById('editor-layout').classList.remove('hidden');
        document.getElementById('timeline-section').classList.remove('hidden');
        document.getElementById('shortcuts-toggle').classList.remove('hidden');

        // Initialize UI
        setMode(mode);
        setupKeyboardShortcuts();
        setupPlayheadDrag();
        setupSplitter();

        // Load YouTube IFrame API
        loadYouTubeAPI();

        // Recapture focus from YouTube iframe
        document.addEventListener('click', () => {
            if (document.activeElement && document.activeElement.tagName === 'IFRAME') {
                document.activeElement.blur();
                document.body.focus();
            }
        });

    } catch (err) {
        console.error('Failed to load video data:', err);
        showError('Failed to fetch video metadata. Check that the Worker URL is configured correctly.');
    }
}

function showError(message) {
    document.getElementById('loading-state').classList.add('hidden');
    document.getElementById('error-state').classList.remove('hidden');
    document.getElementById('error-message').textContent = message;
}

// ============= YouTube IFrame API =============
function loadYouTubeAPI() {
    const tag = document.createElement('script');
    tag.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(tag);
}

function onYouTubeIframeAPIReady() {
    ytPlayer = new YT.Player('youtube-player', {
        videoId: youtubeVideoId,
        playerVars: {
            'autoplay': 0,
            'controls': 1,
            'modestbranding': 1,
            'rel': 0,
            'enablejsapi': 1,
            'origin': window.location.origin
        },
        events: {
            'onReady': onYTPlayerReady,
            'onStateChange': onYTPlayerStateChange
        }
    });
}

// Make it global for YouTube API callback
window.onYouTubeIframeAPIReady = onYouTubeIframeAPIReady;

function onYTPlayerReady(event) {
    ytPlayerReady = true;
    videoDuration = ytPlayer.getDuration();
    renderTimeline();
    renderHighlights();
    updateTotalTime();
    updateStats();

    ytTimeUpdateInterval = setInterval(() => {
        if (ytPlayerReady) {
            updateTimeDisplay();
            updatePlayheadPosition();
            if (isPlayingAll) onPlayAllTimeUpdate();
        }
    }, 100);

    // Auto-start sequential playback in watch mode
    if (mode === 'watch' && highlights.length > 0) {
        startPlayAll();
    }
}

function onYTPlayerStateChange(event) {
    // Could handle ended state for playAll
}

// ============= Mode Management =============
function setMode(newMode) {
    mode = newMode;
    document.body.dataset.mode = mode;

    // Show/hide empty overlay
    const overlay = document.getElementById('empty-overlay');
    if (mode === 'watch' && highlights.length === 0) {
        overlay.classList.remove('hidden');
    } else {
        overlay.classList.add('hidden');
    }

    // Stop sequential playback when leaving watch mode
    if (mode === 'edit' && isPlayingAll) {
        stopPlayAll();
    }

    // Cancel recording when leaving edit mode
    if (mode === 'watch' && recordingStart !== null) {
        cancelRecording();
    }

    renderHighlights();
    renderTimeline();
}

// ============= Sequential Playback (Watch Mode) =============
function startPlayAll() {
    if (highlights.length === 0) return;

    playAllClips = [...highlights].sort((a, b) => a.start_time - b.start_time);
    playAllClipIndex = 0;
    isPlayingAll = true;

    document.getElementById('play-all-btn').classList.add('hidden');
    document.getElementById('stop-play-btn').classList.remove('hidden');

    playCurrentClip();
}

function stopPlayAll() {
    isPlayingAll = false;
    VideoPlayer.pause();

    document.getElementById('play-all-btn').classList.remove('hidden');
    document.getElementById('stop-play-btn').classList.add('hidden');

    // Clear playing state
    document.querySelectorAll('.highlight-item').forEach(el => el.classList.remove('playing'));
    document.querySelectorAll('.timeline-segment').forEach(el => el.classList.remove('playing-segment'));
}

function playCurrentClip() {
    if (!isPlayingAll || playAllClipIndex >= playAllClips.length) {
        stopPlayAll();
        return;
    }

    const clip = playAllClips[playAllClipIndex];

    // Update active highlight in sidebar
    document.querySelectorAll('.highlight-item').forEach(el => {
        el.classList.remove('playing');
        if (el.dataset.id === clip.id) {
            el.classList.add('playing');
            el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    });

    // Update active segment on timeline
    document.querySelectorAll('.timeline-segment').forEach(el => {
        el.classList.remove('playing-segment');
        if (el.dataset.id === clip.id) el.classList.add('playing-segment');
    });

    VideoPlayer.setCurrentTime(clip.start_time);
    VideoPlayer.play();
}

function onPlayAllTimeUpdate() {
    if (!isPlayingAll || playAllClipIndex >= playAllClips.length) return;

    const clip = playAllClips[playAllClipIndex];
    const currentTime = VideoPlayer.getCurrentTime();

    if (currentTime >= clip.end_time - 0.1) {
        // Move to next clip
        playAllClipIndex++;
        if (playAllClipIndex < playAllClips.length) {
            setTimeout(() => {
                if (isPlayingAll) playCurrentClip();
            }, 300);
        } else {
            stopPlayAll();
        }
    }
}

// ============= Copy for Description =============
async function copyForDescription() {
    if (highlights.length === 0) {
        showToast('No highlights to export');
        return;
    }

    const sorted = [...highlights].sort((a, b) => a.start_time - b.start_time);
    const watchUrl = `${window.location.origin}${window.location.pathname}?v=${youtubeVideoId}`;

    let lines = [watchUrl, '', '[Highlights]'];
    for (const h of sorted) {
        const start = formatTimestampForDescription(h.start_time);
        const end = formatTimestampForDescription(h.end_time);
        lines.push(`${start} - ${end}`);
    }

    const text = lines.join('\n');
    try {
        await navigator.clipboard.writeText(text);
        showToast(`Copied ${sorted.length} highlights for description`);
    } catch (e) {
        showToast('Failed to copy to clipboard');
    }
}

function formatTimestampForDescription(seconds) {
    const totalSecs = Math.round(seconds);
    const hours = Math.floor(totalSecs / 3600);
    const minutes = Math.floor((totalSecs % 3600) / 60);
    const secs = totalSecs % 60;
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    }
    return `${minutes}:${secs.toString().padStart(2, '0')}`;
}

// ============= Splitter =============
function setupSplitter() {
    const splitter = document.getElementById('splitter');
    const layout = document.getElementById('editor-layout');
    const videoPane = document.getElementById('video-pane');
    const highlightsPane = document.getElementById('highlights-pane');
    let isDragging = false;

    splitter.addEventListener('mousedown', (e) => {
        e.preventDefault();
        isDragging = true;
        splitter.classList.add('dragging');
        document.body.classList.add('no-select');

        const onMove = (e) => {
            if (!isDragging) return;
            const layoutRect = layout.getBoundingClientRect();
            const x = e.clientX - layoutRect.left;
            const totalWidth = layoutRect.width;
            const splitterWidth = 5;
            const minVideo = 300;
            const minHighlights = 180;
            const maxVideoWidth = totalWidth - splitterWidth - minHighlights;
            const videoWidth = Math.max(minVideo, Math.min(x, maxVideoWidth));
            const highlightsWidth = totalWidth - videoWidth - splitterWidth;

            videoPane.style.flex = 'none';
            videoPane.style.width = videoWidth + 'px';
            highlightsPane.style.width = highlightsWidth + 'px';
        };

        const onUp = () => {
            isDragging = false;
            splitter.classList.remove('dragging');
            document.body.classList.remove('no-select');
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
        };

        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    });
}

// ============= Timeline Zoom =============
function cycleTimelineZoom() {
    currentZoomMode = (currentZoomMode + 1) % ZOOM_MODES.length;
    const zoomMode = ZOOM_MODES[currentZoomMode];
    const section = document.querySelector('.timeline-section');

    if (zoomMode.hidden) {
        section.style.display = 'none';
        document.querySelector('.container').style.height = 'calc(100vh - 56px)';
    } else {
        section.style.display = '';
        document.querySelector('.container').style.height = '';
        applyZoomMode();
        renderTimeline();
        updatePlayheadPosition();
    }
}

function applyZoomMode() {
    const zoomMode = ZOOM_MODES[currentZoomMode];
    if (zoomMode.hidden) return;
    const pps = zoomMode.getPixelsPerSecond();
    if (pps === null) {
        const scrollContainer = document.getElementById('timeline-scroll');
        const duration = VideoPlayer.getDuration() || videoDuration || 100;
        pixelsPerSecond = scrollContainer.clientWidth / duration;
    } else {
        pixelsPerSecond = pps;
    }
    document.getElementById('timeline-zoom-label').textContent = zoomMode.label;
}

// ============= Toast =============
let toastTimeout = null;
let toastInterval = null;
function showToast(message) {
    const el = document.getElementById('toast');
    el.textContent = message;
    el.classList.add('visible');
    clearTimeout(toastTimeout);
    clearInterval(toastInterval);
    toastInterval = null;
    toastTimeout = setTimeout(() => el.classList.remove('visible'), 1500);
}

function startRecordingToast() {
    clearTimeout(toastTimeout);
    clearInterval(toastInterval);
    const el = document.getElementById('toast');
    el.classList.add('visible');
    const update = () => {
        if (recordingStart === null) return;
        const elapsed = Math.max(0, VideoPlayer.getCurrentTime() - recordingStart);
        el.textContent = `Highlight: ${elapsed.toFixed(1)}s`;
    };
    update();
    toastInterval = setInterval(update, 100);
}

// ============= Speed Indicator =============
let speedIndicatorTimeout = null;
function showSpeedIndicator(rate) {
    let el = document.getElementById('speed-indicator');
    if (!el) {
        el = document.createElement('div');
        el.id = 'speed-indicator';
        el.className = 'speed-indicator';
        document.getElementById('video-pane').appendChild(el);
    }
    el.textContent = rate.toFixed(1) + 'x';
    el.classList.add('visible');
    clearTimeout(speedIndicatorTimeout);
    speedIndicatorTimeout = setTimeout(() => el.classList.remove('visible'), 800);
}

// ============= Shortcuts / Highlights Panel Toggle =============
function toggleShortcuts() {
    document.getElementById('shortcuts-help').classList.toggle('hidden');
}

let highlightsPanelVisible = true;
function toggleHighlightsPanel() {
    highlightsPanelVisible = !highlightsPanelVisible;
    const panel = document.getElementById('highlights-pane');
    const splitter = document.getElementById('splitter');
    const tab = document.getElementById('highlights-tab');
    const videoPane = document.getElementById('video-pane');

    if (highlightsPanelVisible) {
        panel.classList.remove('collapsed');
        splitter.classList.remove('collapsed');
        tab.classList.add('hidden');
        videoPane.style.flex = '';
        videoPane.style.width = '';
        panel.style.width = '';
    } else {
        panel.classList.add('collapsed');
        splitter.classList.add('collapsed');
        tab.classList.remove('hidden');
        videoPane.style.flex = '1';
        videoPane.style.width = '';
    }
}

// ============= Keyboard Shortcuts =============
function setupKeyboardShortcuts() {
    document.addEventListener('keydown', async (e) => {
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

        const isMeta = e.metaKey || e.ctrlKey;
        const currentTime = VideoPlayer.getCurrentTime();

        switch (e.key) {
            case 'ArrowUp':
                e.preventDefault();
                if (isMeta) {
                    if (highlights.length > 0) selectHighlight(highlights[0].id);
                } else {
                    jumpToPrevHighlight();
                }
                break;

            case 'ArrowDown':
                e.preventDefault();
                if (isMeta) {
                    if (highlights.length > 0) selectHighlight(highlights[highlights.length - 1].id);
                } else {
                    jumpToNextHighlight();
                }
                break;

            case 'ArrowLeft':
                e.preventDefault();
                VideoPlayer.setCurrentTime(currentTime - JUMP_LARGE);
                break;

            case 'ArrowRight':
                e.preventDefault();
                VideoPlayer.setCurrentTime(currentTime + JUMP_LARGE);
                break;

            case 'z':
                e.preventDefault();
                VideoPlayer.setCurrentTime(currentTime - JUMP_SMALL);
                break;

            case 'x':
                e.preventDefault();
                VideoPlayer.setCurrentTime(currentTime + JUMP_SMALL);
                break;

            case '[':
                e.preventDefault();
                if (mode === 'edit') {
                    if (isMeta) jumpToPrevHighlight();
                    else setHighlightStart(currentTime);
                }
                break;

            case ']':
                e.preventDefault();
                if (mode === 'edit') {
                    if (isMeta) jumpToNextHighlight();
                    else setHighlightEnd(currentTime);
                }
                break;

            case ' ':
                e.preventDefault();
                if (VideoPlayer.isPaused()) VideoPlayer.play();
                else VideoPlayer.pause();
                break;

            case 'Backspace':
            case 'Delete':
                if (mode === 'edit') {
                    e.preventDefault();
                    deleteSelectedHighlight();
                }
                break;

            case 'd': {
                e.preventDefault();
                const newRate = Math.round(Math.max(0.1, Math.min(VideoPlayer.getPlaybackRate() + 0.1, 4.0)) * 10) / 10;
                VideoPlayer.setPlaybackRate(newRate);
                showSpeedIndicator(newRate);
                break;
            }

            case 's': {
                e.preventDefault();
                const newRate = Math.round(Math.max(0.1, Math.min(VideoPlayer.getPlaybackRate() - 0.1, 4.0)) * 10) / 10;
                VideoPlayer.setPlaybackRate(newRate);
                showSpeedIndicator(newRate);
                break;
            }

            case 'r': {
                if (isMeta) break;
                e.preventDefault();
                const newRate = VideoPlayer.getPlaybackRate() === 2.0 ? 1.0 : 2.0;
                VideoPlayer.setPlaybackRate(newRate);
                showSpeedIndicator(newRate);
                break;
            }

            case 'h':
                e.preventDefault();
                toggleHighlightsPanel();
                break;

            case 't':
                if (isMeta) break;
                e.preventDefault();
                cycleTimelineZoom();
                break;

            case '\\':
                e.preventDefault();
                if (mode === 'edit' && recordingStart !== null) {
                    cancelRecording();
                }
                break;

            case 'e':
                if (isMeta) break;
                if (mode === 'watch') {
                    e.preventDefault();
                    setMode('edit');
                }
                break;

            case 'Escape':
                e.preventDefault();
                if (mode === 'edit') {
                    if (selectedHighlightId !== null) {
                        deselectHighlight();
                    } else {
                        setMode('watch');
                    }
                } else {
                    deselectHighlight();
                }
                break;
        }
    }, true);
}

// ============= Highlight CRUD (Client-side only) =============
function setHighlightStart(time) {
    if (selectedHighlightId !== null && recordingStart === null) {
        const highlight = highlights.find(h => h.id === selectedHighlightId);
        if (highlight && time < highlight.end_time) {
            if (wouldOverlap(time, highlight.end_time, selectedHighlightId)) return;
            updateHighlight(selectedHighlightId, { start_time: time });
            return;
        }
    }

    if (highlights.some(h => time >= h.start_time && time < h.end_time)) return;

    recordingStart = time;
    startRecordingToast();
    updateRecordingRegion();
}

function setHighlightEnd(time) {
    if (recordingStart !== null && time > recordingStart) {
        if (wouldOverlap(recordingStart, time)) return;
        createHighlight(recordingStart, time);
        recordingStart = null;
        updateRecordingRegion();
    } else if (selectedHighlightId !== null) {
        const highlight = highlights.find(h => h.id === selectedHighlightId);
        if (highlight && time > highlight.start_time) {
            if (wouldOverlap(highlight.start_time, time, selectedHighlightId)) return;
            updateHighlight(selectedHighlightId, { end_time: time });
        }
    }
}

function wouldOverlap(start, end, excludeId) {
    return highlights.some(h => {
        if (h.id === excludeId) return false;
        return start < h.end_time && end > h.start_time;
    });
}

function updateRecordingRegion() {
    const existing = document.getElementById('recording-region');
    if (existing) existing.remove();
    const existingMarker = document.getElementById('recording-marker');
    if (existingMarker) existingMarker.remove();

    if (recordingStart === null) return;

    const timeline = document.getElementById('timeline');
    const currentTime = VideoPlayer.getCurrentTime();

    const marker = document.createElement('div');
    marker.id = 'recording-marker';
    marker.className = 'recording-marker';
    marker.style.left = `${recordingStart * pixelsPerSecond}px`;
    timeline.appendChild(marker);

    if (currentTime > recordingStart) {
        const region = document.createElement('div');
        region.id = 'recording-region';
        region.className = 'recording-region';
        region.style.left = `${recordingStart * pixelsPerSecond}px`;
        region.style.width = `${(currentTime - recordingStart) * pixelsPerSecond}px`;
        timeline.appendChild(region);
    }
}

function cancelRecording() {
    recordingStart = null;
    showToast('Cancelled');
    updateRecordingRegion();
}

function createHighlight(start, end) {
    highlightCounter++;
    const highlight = {
        id: `manual_${highlightCounter}`,
        start_time: start,
        end_time: end,
        duration: end - start,
        source: 'manual',
        label: null,
    };

    highlights.push(highlight);
    highlights.sort((a, b) => a.start_time - b.start_time);

    selectedHighlightId = highlight.id;
    showToast('Highlight added');
    renderHighlights();
    renderTimeline();
    updateStats();
}

function updateHighlight(id, updates) {
    const index = highlights.findIndex(h => h.id === id);
    if (index >= 0) {
        Object.assign(highlights[index], updates);
        highlights[index].duration = highlights[index].end_time - highlights[index].start_time;
        highlights.sort((a, b) => a.start_time - b.start_time);
    }

    renderHighlights();
    renderTimeline();
    updateStats();
}

function deleteHighlight(id) {
    highlights = highlights.filter(h => h.id !== id);

    if (selectedHighlightId === id) selectedHighlightId = null;

    renderHighlights();
    renderTimeline();
    updateStats();
}

function deleteSelectedHighlight() {
    if (selectedHighlightId !== null) deleteHighlight(selectedHighlightId);
}

function selectHighlight(id) {
    selectedHighlightId = id;
    const highlight = highlights.find(h => h.id === id);
    if (highlight) {
        VideoPlayer.setCurrentTime(highlight.start_time);
        if (mode === 'watch') VideoPlayer.play();
    }
    renderHighlights();
    renderTimeline();

    requestAnimationFrame(() => {
        const el = document.querySelector(`.highlight-item[data-id="${id}"]`);
        if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    });
}

function deselectHighlight() {
    selectedHighlightId = null;
    renderHighlights();
    renderTimeline();
}

function jumpToPrevHighlight() {
    if (highlights.length === 0) return;
    const currentTime = VideoPlayer.getCurrentTime();
    let prev = null;
    for (let i = highlights.length - 1; i >= 0; i--) {
        if (highlights[i].start_time < currentTime - 0.5) {
            prev = highlights[i];
            break;
        }
    }
    if (prev) selectHighlight(prev.id);
    else selectHighlight(highlights[highlights.length - 1].id);
}

function jumpToNextHighlight() {
    if (highlights.length === 0) return;
    const currentTime = VideoPlayer.getCurrentTime();
    let next = null;
    for (const h of highlights) {
        if (h.start_time > currentTime + 0.5) {
            next = h;
            break;
        }
    }
    if (next) selectHighlight(next.id);
    else selectHighlight(highlights[0].id);
}

// ============= Rendering =============
function renderHighlights() {
    const list = document.getElementById('highlights-list');

    if (highlights.length === 0) {
        if (mode === 'edit') {
            list.innerHTML = `
                <div class="empty-state">
                    <p>No highlights yet</p>
                    <p class="hint">Press <kbd>[</kbd> to mark start, <kbd>]</kbd> to mark end</p>
                </div>
            `;
        } else {
            list.innerHTML = `
                <div class="empty-state">
                    <p>No highlights</p>
                </div>
            `;
        }
        return;
    }

    list.innerHTML = highlights.map((h, i) => {
        const isSelected = h.id === selectedHighlightId;
        const deleteBtn = mode === 'edit'
            ? `<button class="highlight-delete" onclick="event.stopPropagation(); deleteHighlight('${h.id}')" title="Delete">&times;</button>`
            : '';
        const sourceTag = h.source
            ? `<span class="highlight-source ${h.source}">${h.source}</span>`
            : '';

        return `
            <div class="highlight-item ${isSelected ? 'selected' : ''}"
                 data-id="${h.id}"
                 onclick="selectHighlight('${h.id}')">
                <span class="highlight-number">${i + 1}</span>
                <span class="highlight-times">${formatTimeShort(h.start_time)} - ${formatTimeShort(h.end_time)}</span>
                <span class="highlight-duration">${(h.duration || (h.end_time - h.start_time)).toFixed(1)}s</span>
                ${sourceTag}
                ${deleteBtn}
            </div>
        `;
    }).join('');

    document.getElementById('highlight-count').textContent = `(${highlights.length})`;
}

function renderTimeline() {
    const timeline = document.getElementById('timeline');
    const labels = document.getElementById('time-labels');
    const content = document.getElementById('timeline-content');

    timeline.innerHTML = '';
    labels.innerHTML = '';

    const duration = VideoPlayer.getDuration() || videoDuration || 100;
    applyZoomMode();

    const totalWidth = duration * pixelsPerSecond;
    content.style.width = `${totalWidth}px`;

    document.getElementById('timeline-duration').textContent = `Duration: ${formatTimeShort(duration)}`;

    highlights.forEach((h, i) => {
        const segment = document.createElement('div');
        segment.className = 'timeline-segment';
        segment.dataset.id = h.id;

        if (h.id === selectedHighlightId) segment.classList.add('selected');

        const left = h.start_time * pixelsPerSecond;
        const width = (h.end_time - h.start_time) * pixelsPerSecond;

        segment.style.left = `${left}px`;
        segment.style.width = `${Math.max(width, 3)}px`;
        segment.title = `#${i + 1}: ${formatTimeShort(h.start_time)} - ${formatTimeShort(h.end_time)}`;

        segment.onclick = (e) => {
            e.stopPropagation();
            selectHighlight(h.id);
        };

        timeline.appendChild(segment);
    });

    timeline.onclick = (e) => {
        if (e.target === timeline) {
            const rect = timeline.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const time = x / pixelsPerSecond;
            VideoPlayer.setCurrentTime(time);
        }
    };

    // Time labels
    const minLabelGap = 80;
    const rawInterval = minLabelGap / pixelsPerSecond;
    const niceIntervals = [1, 2, 5, 10, 15, 30, 60, 120, 300, 600];
    const labelInterval = niceIntervals.find(i => i >= rawInterval) || 600;
    const numLabels = Math.ceil(duration / labelInterval);
    for (let i = 0; i <= numLabels; i++) {
        const time = i * labelInterval;
        if (time > duration) break;

        const label = document.createElement('span');
        label.className = 'time-label';
        label.style.left = `${time * pixelsPerSecond}px`;
        label.textContent = formatTimeShort(time);
        labels.appendChild(label);
    }
}

function updatePlayheadPosition() {
    const playhead = document.getElementById('playhead');
    const currentTime = VideoPlayer.getCurrentTime();

    if (playhead) {
        const left = currentTime * pixelsPerSecond;
        playhead.style.left = `${left}px`;

        const scrollContainer = document.getElementById('timeline-scroll');
        const containerWidth = scrollContainer.clientWidth;
        const scrollLeft = scrollContainer.scrollLeft;

        if (left < scrollLeft || left > scrollLeft + containerWidth - 50) {
            scrollContainer.scrollLeft = Math.max(0, left - containerWidth / 2);
        }
    }

    if (recordingStart !== null) updateRecordingRegion();
}

let isPlayheadDragging = false;

function setupPlayheadDrag() {
    const playhead = document.getElementById('playhead');

    playhead.addEventListener('mousedown', (e) => {
        e.preventDefault();
        isPlayheadDragging = true;
        playhead.classList.add('dragging');
        VideoPlayer.pause();

        document.addEventListener('mousemove', onPlayheadDrag);
        document.addEventListener('mouseup', endPlayheadDrag);
    });
}

function onPlayheadDrag(e) {
    if (!isPlayheadDragging) return;

    const timeline = document.getElementById('timeline');
    const rect = timeline.getBoundingClientRect();
    let x = e.clientX - rect.left;
    const duration = VideoPlayer.getDuration() || videoDuration;
    const maxX = duration * pixelsPerSecond;
    x = Math.max(0, Math.min(x, maxX));
    const newTime = x / pixelsPerSecond;

    VideoPlayer.setCurrentTime(newTime);
    updateTimeDisplay();
    updatePlayheadPosition();
}

function endPlayheadDrag() {
    isPlayheadDragging = false;
    document.getElementById('playhead').classList.remove('dragging');
    document.removeEventListener('mousemove', onPlayheadDrag);
    document.removeEventListener('mouseup', endPlayheadDrag);
}

function updateTimeDisplay() {
    document.getElementById('current-time').textContent = formatTimePrecise(VideoPlayer.getCurrentTime());
}

function updateTotalTime() {
    document.getElementById('total-time').textContent = formatTimePrecise(VideoPlayer.getDuration());
}

function updateStats() {
    const count = highlights.length;
    const totalDuration = highlights.reduce((sum, h) => sum + (h.duration || (h.end_time - h.start_time)), 0);

    document.getElementById('total-duration').textContent = formatTimeShort(totalDuration);
    document.getElementById('timeline-stats').textContent = `${count} highlights (${formatTimeShort(totalDuration)})`;
    document.getElementById('tab-highlight-count').textContent = count;
}

// ============= Time Formatting =============
function formatTimePrecise(seconds) {
    if (seconds === undefined || seconds === null || isNaN(seconds)) return '00:00.00';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toFixed(2).padStart(5, '0')}`;
}

function formatTimeShort(seconds) {
    if (seconds === undefined || seconds === null || isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs.toString().padStart(2, '0')}`;
}
