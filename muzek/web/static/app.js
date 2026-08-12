const songListEl = document.getElementById("song-list");
const emptyStateEl = document.getElementById("empty-state");
const songViewEl = document.getElementById("song-view");
const songTitleEl = document.getElementById("song-title");
const songMetaEl = document.getElementById("song-meta");
const timelineEl = document.getElementById("timeline");
const detailPanelEl = document.getElementById("detail-panel");
const paletteEl = document.getElementById("palette");

const compareViewEl = document.getElementById("compare-view");
const compareTracksEl = document.getElementById("compare-tracks");
const compareTitleCountEl = document.getElementById("compare-title-count");
const compareBtn = document.getElementById("compare-btn");
const compareCountEl = document.getElementById("compare-count");

const featureGraphsEl = document.getElementById("feature-graphs");

const FEATURE_SPECS = [
  { key: "energy_mean", label: "Energy", color: "#f472b6", format: (v) => v.toFixed(2) },
  { key: "spectral_centroid_mean", label: "Brightness", color: "#facc15", format: (v) => `${v.toFixed(0)}Hz` },
  { key: "tempo_bpm", label: "Tempo", color: "#38bdf8", format: (v) => `${v.toFixed(0)}bpm` },
  { key: "onset_density", label: "Onset density", color: "#34d399", format: (v) => `${v.toFixed(1)}/s` },
];

const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("file-input");
const uploadFieldsEl = document.getElementById("upload-fields");
const uploadQueueEl = document.getElementById("upload-queue");
const uploadQueueCountEl = document.getElementById("upload-queue-count");
const uploadArtistEl = document.getElementById("upload-artist");
const uploadSubmitBtn = document.getElementById("upload-submit");
const uploadCancelBtn = document.getElementById("upload-cancel");
const uploadErrorEl = document.getElementById("upload-error");

const similarSongsEl = document.getElementById("similar-songs");
const insightsEl = document.getElementById("insights");

const dnaHelixEl = document.getElementById("dna-helix");
const dnaSequenceEl = document.getElementById("dna-sequence");
const dnaCaptionEl = document.getElementById("dna-caption");

let songsCache = [];
let selectedIds = new Set();

// Each entry: { id, file, title, status: "pending"|"analyzing"|"done"|"error", error }
let uploadQueue = [];
let uploadRunning = false;

// ---------- utils ----------

function formatSeconds(s) {
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60).toString().padStart(2, "0");
  return `${m}:${sec}`;
}

function readableTextColor(hex) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  const luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
  return luminance > 0.55 ? "#111" : "#f5f5f5";
}

function setMode(mode) {
  emptyStateEl.classList.toggle("hidden", mode !== "empty");
  songViewEl.classList.toggle("hidden", mode !== "song");
  compareViewEl.classList.toggle("hidden", mode !== "compare");
}

// ---------- song list ----------

async function loadSongs({ preserveSelection = true } = {}) {
  const res = await fetch("/api/songs");
  const songs = await res.json();
  songsCache = songs;

  if (!preserveSelection) selectedIds.clear();
  const validIds = new Set(songs.map((s) => s.id));
  selectedIds = new Set([...selectedIds].filter((id) => validIds.has(id)));

  renderSongList();
  updateCompareButton();
}

function renderSongList() {
  songListEl.innerHTML = "";
  if (songsCache.length === 0) {
    const li = document.createElement("li");
    li.className = "song-list-empty";
    li.textContent = "No songs cataloged yet — analyze one above.";
    songListEl.appendChild(li);
    return;
  }

  for (const song of songsCache) {
    const li = document.createElement("li");
    li.className = "song-list-item";
    li.dataset.songId = song.id;

    const swatchColor = song.swatch || "#555";
    const checkedAttr = selectedIds.has(song.id) ? "checked" : "";
    // Build the row's full markup in one shot -- setting innerHTML again
    // afterward (e.g. via +=) would destroy this checkbox and silently drop
    // its listener, which is what broke multi-select before.
    li.innerHTML = `
      <input type="checkbox" class="song-checkbox" ${checkedAttr} />
      <span class="song-list-swatch" style="background:${swatchColor}; color:${swatchColor}"></span>
      <span class="song-list-title">${escapeHtml(song.title || "(untitled)")}</span>
      <span class="song-list-duration">${formatSeconds(song.duration_seconds)}</span>
    `;

    const checkbox = li.querySelector(".song-checkbox");
    checkbox.addEventListener("click", (e) => {
      e.stopPropagation();
      toggleSelect(song.id, checkbox.checked);
    });

    li.addEventListener("click", () => selectSong(song.id));
    songListEl.appendChild(li);
  }
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function toggleSelect(id, checked) {
  if (checked) selectedIds.add(id);
  else selectedIds.delete(id);
  updateCompareButton();
}

function updateCompareButton() {
  compareCountEl.textContent = selectedIds.size;
  compareBtn.disabled = selectedIds.size < 2;
}

// ---------- single song view ----------

async function selectSong(songId) {
  document.querySelectorAll(".song-list-item").forEach((el) => {
    el.classList.toggle("active", Number(el.dataset.songId) === songId);
  });

  const res = await fetch(`/api/songs/${songId}`);
  if (!res.ok) return;
  const breakdown = await res.json();
  renderSong(breakdown);
  setMode("song");
}

function renderSong(breakdown) {
  detailPanelEl.classList.add("hidden");
  detailPanelEl.innerHTML = "";

  const song = breakdown.song;
  songTitleEl.textContent = song.title || "(untitled)";
  songMetaEl.textContent = `${formatSeconds(song.duration_seconds)} · analyzed ${new Date(song.analyzed_at).toLocaleString()}`;

  timelineEl.innerHTML = "";
  paletteEl.innerHTML = "";
  buildTimelineBlocks(timelineEl, breakdown, (seg, hex) => showDetail(seg, hex));
  renderFeatureGraphs(featureGraphsEl, breakdown);
  renderDna(breakdown);

  breakdown.segments.forEach((seg, i) => {
    const hex = seg.colors[0] ? seg.colors[0].hex : "#333333";
    const swatch = document.createElement("div");
    swatch.className = "palette-swatch palette-swatch-enter";
    swatch.style.background = hex;
    swatch.style.animationDelay = `${i * 35}ms`;
    swatch.title = hex;
    paletteEl.appendChild(swatch);
  });

  loadSimilarSongs(song.id);
}

async function loadSimilarSongs(songId) {
  similarSongsEl.innerHTML = `<div class="similar-songs-empty">Finding similar songs&hellip;</div>`;
  const res = await fetch(`/api/songs/${songId}/similar`);
  if (!res.ok) {
    similarSongsEl.innerHTML = "";
    return;
  }
  const matches = await res.json();

  if (matches.length === 0) {
    similarSongsEl.innerHTML = `<div class="similar-songs-empty">Analyze more songs to see similar matches.</div>`;
    return;
  }

  similarSongsEl.innerHTML = "";
  matches.forEach((match, i) => {
    const pct = Math.round(Math.max(0, Math.min(1, match.similarity)) * 100);
    const swatchColor = match.swatch || "#555";
    const card = document.createElement("div");
    card.className = "similar-song-card similar-song-card-enter";
    card.style.animationDelay = `${i * 60}ms`;
    card.innerHTML = `
      <div class="similar-song-swatch" style="background:${swatchColor}; color:${swatchColor}"></div>
      <div class="similar-song-info">
        <div class="similar-song-title">${escapeHtml(match.title || "(untitled)")}</div>
        <div class="similar-song-duration">${formatSeconds(match.duration_seconds)}</div>
      </div>
      <div class="similar-song-score">
        <div class="similar-song-score-bar"><div class="similar-song-score-fill" style="width:0%"></div></div>
        <span class="similar-song-score-pct">${pct}%</span>
      </div>
    `;
    card.addEventListener("click", () => selectSong(match.song_id));
    similarSongsEl.appendChild(card);

    const fill = card.querySelector(".similar-song-score-fill");
    requestAnimationFrame(() => {
      setTimeout(() => {
        fill.style.width = `${pct}%`;
      }, i * 60 + 250);
    });
  });
}

function buildTimelineBlocks(container, breakdown, onClick) {
  const totalDuration = breakdown.song.duration_seconds;
  breakdown.segments.forEach((seg, i) => {
    const color = seg.colors[0];
    const hex = color ? color.hex : "#333333";
    const widthPct = ((seg.end - seg.start) / totalDuration) * 100;

    const block = document.createElement("div");
    block.className = "segment-block segment-block-enter";
    block.style.width = `${widthPct}%`;
    block.style.background = hex;
    block.style.color = readableTextColor(hex);
    block.style.setProperty("--glow", hex);
    block.style.animationDelay = `${i * 45}ms`;
    block.textContent = seg.label;
    block.title = `${seg.label}  ${formatSeconds(seg.start)}–${formatSeconds(seg.end)}`;
    block.dataset.start = seg.start;
    block.dataset.end = seg.end;
    block.dataset.segIndex = String(i);
    if (onClick) block.addEventListener("click", () => onClick(seg, hex));
    container.appendChild(block);
  });
}

// Renders one feature as a step/area chart across the song's segments --
// each segment holds a flat value for its whole duration (that's the
// granularity the analysis produces), so a step function is the honest
// shape rather than smoothing between segment midpoints.
function buildFeatureGraphSVG(breakdown, spec) {
  const width = 1000;
  const height = 64;
  const padTop = 6;
  const padBottom = 4;

  const totalDuration = breakdown.song.duration_seconds;
  const values = breakdown.segments.map((seg) => (seg.features ? seg.features[spec.key] : null) ?? 0);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;

  const points = [];
  let x = 0;
  breakdown.segments.forEach((seg, i) => {
    const segWidth = ((seg.end - seg.start) / totalDuration) * width;
    const norm = (values[i] - min) / range;
    const y = height - padBottom - norm * (height - padTop - padBottom);
    points.push([x, y]);
    points.push([x + segWidth, y]);
    x += segWidth;
  });

  const linePath = points.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(2)},${p[1].toFixed(2)}`).join(" ");
  const areaPath = `${linePath} L${x.toFixed(2)},${height} L0,${height} Z`;
  const gradientId = `grad-${spec.key}-${Math.random().toString(36).slice(2, 8)}`;

  return `
    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" class="feature-graph-svg">
      <defs>
        <linearGradient id="${gradientId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="${spec.color}" stop-opacity="0.4" />
          <stop offset="100%" stop-color="${spec.color}" stop-opacity="0" />
        </linearGradient>
      </defs>
      <path class="feature-area" d="${areaPath}" fill="url(#${gradientId})" stroke="none"></path>
      <path class="feature-line" d="${linePath}" fill="none" stroke="${spec.color}" stroke-width="2" vector-effect="non-scaling-stroke"></path>
    </svg>
  `;
}

function renderFeatureGraphs(container, breakdown, { compact = false } = {}) {
  container.innerHTML = "";
  container.classList.toggle("feature-graphs-compact", compact);
  FEATURE_SPECS.forEach((spec, i) => {
    const values = breakdown.segments.map((seg) => (seg.features ? seg.features[spec.key] : null) ?? 0);
    const min = Math.min(...values);
    const max = Math.max(...values);

    const wrap = document.createElement("div");
    wrap.className = "feature-graph feature-graph-enter";
    wrap.style.animationDelay = `${i * 80}ms`;
    wrap.innerHTML = `
      <div class="feature-graph-label">
        <span class="feature-graph-name" style="color:${spec.color}">${spec.label}</span>
        <span class="feature-graph-range">${spec.format(min)} – ${spec.format(max)}</span>
      </div>
      ${buildFeatureGraphSVG(breakdown, spec)}
    `;
    container.appendChild(wrap);
    animateGraphDrawIn(wrap, i * 80);
  });
}

// Draws the line in stroke-by-stroke (classic SVG "line drawing" technique)
// and fades the area fill in behind it, staggered slightly per graph.
function animateGraphDrawIn(wrap, delayMs) {
  const line = wrap.querySelector(".feature-line");
  const area = wrap.querySelector(".feature-area");
  if (!line || !area) return;

  const length = line.getTotalLength();
  line.style.strokeDasharray = `${length}`;
  line.style.strokeDashoffset = `${length}`;
  area.style.opacity = "0";

  requestAnimationFrame(() => {
    setTimeout(() => {
      line.style.transition = "stroke-dashoffset 900ms cubic-bezier(0.22, 0.8, 0.2, 1)";
      area.style.transition = "opacity 700ms ease";
      line.style.strokeDashoffset = "0";
      area.style.opacity = "1";
    }, delayMs);
  });
}

function showDetail(seg, hex) {
  const f = seg.features || {};
  detailPanelEl.classList.remove("hidden");
  // Restart the entrance animation even if the panel is already open and
  // just switching to a different segment's details.
  detailPanelEl.classList.remove("detail-panel-enter");
  void detailPanelEl.offsetWidth;
  detailPanelEl.classList.add("detail-panel-enter");
  detailPanelEl.style.color = hex;
  detailPanelEl.innerHTML = `
    <div class="detail-swatch" style="background:${hex}"></div>
    <div class="detail-grid" style="color: var(--text)">
      <div><span class="detail-label">Section</span><span class="detail-value">${seg.label}</span></div>
      <div><span class="detail-label">Time</span><span class="detail-value">${formatSeconds(seg.start)}–${formatSeconds(seg.end)}</span></div>
      <div><span class="detail-label">Key</span><span class="detail-value">${f.key_name || "?"} ${f.mode || ""}</span></div>
      <div><span class="detail-label">Tempo</span><span class="detail-value">${f.tempo_bpm ? f.tempo_bpm.toFixed(0) : "?"} bpm</span></div>
      <div><span class="detail-label">Energy</span><span class="detail-value">${f.energy_mean != null ? f.energy_mean.toFixed(3) : "?"}</span></div>
      <div><span class="detail-label">Brightness</span><span class="detail-value">${f.spectral_centroid_mean != null ? f.spectral_centroid_mean.toFixed(0) + " Hz" : "?"}</span></div>
      <div><span class="detail-label">Onset density</span><span class="detail-value">${f.onset_density != null ? f.onset_density.toFixed(2) + "/s" : "?"}</span></div>
      <div><span class="detail-label">Color</span><span class="detail-value">${hex}</span></div>
      <div><span class="detail-label">Codon</span><span class="detail-value">${seg.codon ? seg.codon.code : "?"}</span></div>
    </div>
  `;
}

// ---------- DNA ----------

let dnaActiveIndex = -1;

function setActiveGene(breakdown, index) {
  const seg = breakdown.segments[index];
  const hex = seg.colors[0] ? seg.colors[0].hex : "#333333";

  dnaHelixEl.querySelectorAll(".dna-rung, .dna-rung-hit").forEach((el) => {
    el.classList.toggle("active", Number(el.dataset.index) === index);
  });
  dnaSequenceEl.querySelectorAll(".dna-chip").forEach((el) => {
    el.classList.toggle("active", Number(el.dataset.index) === index);
  });
  timelineEl.querySelectorAll(".segment-block").forEach((el) => {
    el.classList.toggle("selected", Number(el.dataset.segIndex) === index);
  });

  dnaActiveIndex = index;
  showDetail(seg, hex);
}

// A static, real-looking double helix: two continuous sine-wave backbone
// strands (180 degrees out of phase) sampled at fine resolution for a smooth
// curve, with a colored rung -- one per gene -- connecting the strands at
// that gene's twist position.
function renderDna(breakdown) {
  const segments = breakdown.segments;
  const n = segments.length;

  dnaSequenceEl.innerHTML = "";
  dnaActiveIndex = -1;

  const width = 220;
  const amplitude = 60;
  const centerX = width / 2;
  const spacing = 36; // vertical px per gene
  const padding = 24;
  const totalTwists = Math.max(2, n / 4); // ~4 genes per full twist
  const height = n * spacing + padding * 2;

  const phaseAt = (y) => ((y - padding) / (height - padding * 2)) * totalTwists * Math.PI * 2;
  const strandX = (y, sign) => centerX + sign * amplitude * Math.sin(phaseAt(y));

  const samplePath = (sign) => {
    const step = 4;
    let d = "";
    for (let y = 0; y <= height; y += step) {
      const x = strandX(y, sign);
      d += `${y === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)} `;
    }
    return d;
  };

  dnaCaptionEl.textContent = `${n} genes · click a gene to inspect`;

  const svgns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgns, "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("class", "dna-svg dna-enter");

  const makeStrand = (sign) => {
    const path = document.createElementNS(svgns, "path");
    path.setAttribute("d", samplePath(sign));
    path.setAttribute("class", "dna-strand");
    return path;
  };
  svg.appendChild(makeStrand(-1));
  svg.appendChild(makeStrand(1));

  segments.forEach((seg, i) => {
    const hex = seg.colors[0] ? seg.colors[0].hex : "#888888";
    const y = padding + (i + 0.5) * spacing;
    const xa = strandX(y, -1);
    const xb = strandX(y, 1);

    // A wide invisible line makes the thin colored rung easy to click/hover.
    const hit = document.createElementNS(svgns, "line");
    hit.setAttribute("x1", xa);
    hit.setAttribute("y1", y);
    hit.setAttribute("x2", xb);
    hit.setAttribute("y2", y);
    hit.setAttribute("class", "dna-rung-hit");
    hit.dataset.index = String(i);

    const rung = document.createElementNS(svgns, "line");
    rung.setAttribute("x1", xa);
    rung.setAttribute("y1", y);
    rung.setAttribute("x2", xb);
    rung.setAttribute("y2", y);
    rung.setAttribute("class", "dna-rung");
    rung.setAttribute("stroke", hex);
    rung.style.color = hex; // drop-shadow(currentColor) glow matches the stroke
    rung.dataset.index = String(i);

    const nodeA = document.createElementNS(svgns, "circle");
    nodeA.setAttribute("cx", xa);
    nodeA.setAttribute("cy", y);
    nodeA.setAttribute("r", 4);
    nodeA.setAttribute("class", "dna-node");

    const nodeB = document.createElementNS(svgns, "circle");
    nodeB.setAttribute("cx", xb);
    nodeB.setAttribute("cy", y);
    nodeB.setAttribute("r", 4);
    nodeB.setAttribute("class", "dna-node");

    const title = document.createElementNS(svgns, "title");
    title.textContent = `${seg.label} · ${seg.codon ? seg.codon.code : ""}`;
    hit.appendChild(title);

    const onEnter = () => {
      rung.classList.add("hover");
      nodeA.classList.add("hover");
      nodeB.classList.add("hover");
    };
    const onLeave = () => {
      rung.classList.remove("hover");
      nodeA.classList.remove("hover");
      nodeB.classList.remove("hover");
    };
    hit.addEventListener("mouseenter", onEnter);
    hit.addEventListener("mouseleave", onLeave);
    hit.addEventListener("click", () => setActiveGene(breakdown, i));

    svg.appendChild(rung);
    svg.appendChild(nodeA);
    svg.appendChild(nodeB);
    svg.appendChild(hit);

    const chip = document.createElement("div");
    chip.className = "dna-chip";
    chip.dataset.index = String(i);
    chip.style.setProperty("--chip-color", hex);
    chip.textContent = seg.codon ? seg.codon.code : "?";
    chip.title = `${seg.label}  ${formatSeconds(seg.start)}–${formatSeconds(seg.end)}`;
    chip.addEventListener("click", () => setActiveGene(breakdown, i));
    dnaSequenceEl.appendChild(chip);
  });

  dnaHelixEl.innerHTML = "";
  dnaHelixEl.appendChild(svg);
}

// ---------- compare view ----------

let scrubLineEl = null;
let compareTrackStates = []; // { breakdown, timelineEl, readoutEl, activeIndex }

function findSegmentAtTime(breakdown, time) {
  const segments = breakdown.segments;
  for (let i = 0; i < segments.length; i++) {
    if (time < segments[i].end || i === segments.length - 1) return i;
  }
  return 0;
}

function formatReadout(seg) {
  const f = seg.features || {};
  return `${seg.label} &middot; ${f.key_name || "?"}${(f.mode || "").slice(0, 1)} &middot; nrg ${f.energy_mean != null ? f.energy_mean.toFixed(2) : "?"} &middot; ${f.tempo_bpm ? f.tempo_bpm.toFixed(0) : "?"}bpm`;
}

function scrubTo(fraction) {
  compareTrackStates.forEach((state) => {
    const time = fraction * state.breakdown.song.duration_seconds;
    const index = findSegmentAtTime(state.breakdown, time);
    if (index === state.activeIndex) return;

    const prevBlock = state.timelineEl.children[state.activeIndex];
    if (prevBlock) prevBlock.classList.remove("scrub-active");
    const nextBlock = state.timelineEl.children[index];
    if (nextBlock) nextBlock.classList.add("scrub-active");

    state.activeIndex = index;
    state.readoutEl.innerHTML = formatReadout(state.breakdown.segments[index]);
    state.readoutEl.classList.remove("readout-pulse");
    void state.readoutEl.offsetWidth;
    state.readoutEl.classList.add("readout-pulse");
  });
}

function clearScrub() {
  compareTrackStates.forEach((state) => {
    const block = state.timelineEl.children[state.activeIndex];
    if (block) block.classList.remove("scrub-active");
    state.activeIndex = -1;
    state.readoutEl.textContent = "hover to inspect";
  });
}

// Attached once, rather than re-added on every "Compare" click, so repeated
// comparisons don't stack duplicate mousemove listeners on this container.
compareTracksEl.addEventListener("mousemove", (e) => {
  if (!scrubLineEl) return;
  const rect = compareTracksEl.getBoundingClientRect();
  const x = e.clientX - rect.left;
  scrubLineEl.style.left = `${x}px`;
  scrubLineEl.style.display = "block";
  scrubTo(Math.max(0, Math.min(1, x / rect.width)));
});
compareTracksEl.addEventListener("mouseleave", () => {
  if (scrubLineEl) scrubLineEl.style.display = "none";
  clearScrub();
});

function weightedMean(segments, key) {
  const totalWeight = segments.reduce((sum, s) => sum + (s.end - s.start), 0) || 1;
  return segments.reduce((sum, s) => sum + (s.features?.[key] ?? 0) * (s.end - s.start), 0) / totalWeight;
}

function summarizeSong(breakdown) {
  const segments = breakdown.segments;
  return {
    id: breakdown.song.id,
    title: breakdown.song.title || "(untitled)",
    energy: weightedMean(segments, "energy_mean"),
    brightness: weightedMean(segments, "spectral_centroid_mean"),
    tempo: weightedMean(segments, "tempo_bpm"),
    onsetDensity: weightedMean(segments, "onset_density"),
    sectionCount: segments.length,
    uniqueSections: new Set(segments.map((s) => s.label)).size,
  };
}

const INSIGHT_METRICS = [
  { key: "energy", label: "Most energetic", color: "#f472b6", format: (v) => v.toFixed(2) },
  { key: "brightness", label: "Brightest", color: "#facc15", format: (v) => `${v.toFixed(0)}Hz` },
  { key: "tempo", label: "Fastest", color: "#38bdf8", format: (v) => `${v.toFixed(0)}bpm` },
  { key: "onsetDensity", label: "Busiest", color: "#34d399", format: (v) => `${v.toFixed(1)}/s` },
  { key: "uniqueSections", label: "Most structurally varied", color: "#a78bfa", format: (v) => `${v} sections` },
];

async function renderInsights(breakdowns) {
  insightsEl.innerHTML = "";
  const summaries = breakdowns.map(summarizeSong);

  const leaderboards = document.createElement("div");
  leaderboards.className = "insight-leaderboards";
  INSIGHT_METRICS.forEach((metric, mi) => {
    const max = Math.max(...summaries.map((s) => s[metric.key]));
    const block = document.createElement("div");
    block.className = "insight-metric insight-enter";
    block.style.animationDelay = `${mi * 70}ms`;
    block.innerHTML = `<div class="insight-metric-label">${metric.label}</div>`;
    const ranked = [...summaries].sort((a, b) => b[metric.key] - a[metric.key]);
    ranked.forEach((s, i) => {
      const row = document.createElement("div");
      row.className = "insight-row";
      row.innerHTML = `
        <span class="insight-row-title">${i === 0 ? "&#9733;" : ""} ${escapeHtml(s.title)}</span>
        <div class="insight-row-bar"><div class="insight-row-fill" style="background:${metric.color}; width:0%"></div></div>
        <span class="insight-row-value">${metric.format(s[metric.key])}</span>
      `;
      block.appendChild(row);
      const fill = row.querySelector(".insight-row-fill");
      const pct = max > 0 ? (s[metric.key] / max) * 100 : 0;
      requestAnimationFrame(() => setTimeout(() => { fill.style.width = `${pct}%`; }, mi * 70 + 150));
    });
    leaderboards.appendChild(block);
  });
  insightsEl.appendChild(leaderboards);

  const ids = breakdowns.map((b) => b.song.id);
  const res = await fetch(`/api/similarity-matrix?ids=${ids.join(",")}`);
  const { pairs } = await res.json();
  if (pairs.length === 0) return;

  const titleById = new Map(summaries.map((s) => [s.id, s.title]));
  const pairsWrap = document.createElement("div");
  pairsWrap.className = "insight-pairs insight-enter";
  pairsWrap.style.animationDelay = `${INSIGHT_METRICS.length * 70}ms`;
  pairsWrap.innerHTML = `<div class="insight-metric-label">Pairwise similarity</div>`;
  [...pairs].sort((a, b) => b.similarity - a.similarity).forEach((pair, i) => {
    const pct = Math.round(Math.max(0, Math.min(1, pair.similarity)) * 100);
    const row = document.createElement("div");
    row.className = "insight-row";
    row.innerHTML = `
      <span class="insight-row-title">${escapeHtml(titleById.get(pair.a))} &harr; ${escapeHtml(titleById.get(pair.b))}</span>
      <div class="insight-row-bar"><div class="insight-row-fill" style="background:#a78bfa; width:0%"></div></div>
      <span class="insight-row-value">${pct}%</span>
    `;
    pairsWrap.appendChild(row);
    const fill = row.querySelector(".insight-row-fill");
    requestAnimationFrame(() => setTimeout(() => { fill.style.width = `${pct}%`; }, i * 70 + 150));
  });
  insightsEl.appendChild(pairsWrap);
}

async function runCompare(ids) {
  selectedIds = new Set(ids);
  updateCompareButton();
  compareTitleCountEl.textContent = ids.length;

  const breakdowns = await Promise.all(
    ids.map((id) => fetch(`/api/songs/${id}`).then((r) => r.json()))
  );

  compareTracksEl.innerHTML = "";
  compareTrackStates = [];
  document.querySelectorAll(".song-list-item").forEach((el) => el.classList.remove("active"));

  breakdowns.forEach((breakdown, trackIndex) => {
    const song = breakdown.song;
    const track = document.createElement("div");
    track.className = "compare-track compare-track-enter";
    track.style.animationDelay = `${trackIndex * 90}ms`;
    track.innerHTML = `
      <div class="compare-track-label">
        <span class="compare-track-title">${escapeHtml(song.title || "(untitled)")}</span>
        <span class="compare-track-readout">hover to inspect</span>
        <span class="compare-track-duration">${formatSeconds(song.duration_seconds)}</span>
      </div>
    `;
    const timeline = document.createElement("div");
    timeline.className = "compare-timeline";
    buildTimelineBlocks(timeline, breakdown);
    track.appendChild(timeline);

    const graphs = document.createElement("div");
    graphs.className = "feature-graphs";
    renderFeatureGraphs(graphs, breakdown, { compact: true });
    track.appendChild(graphs);

    compareTracksEl.appendChild(track);

    compareTrackStates.push({
      breakdown,
      timelineEl: timeline,
      readoutEl: track.querySelector(".compare-track-readout"),
      activeIndex: -1,
    });
  });

  scrubLineEl = document.createElement("div");
  scrubLineEl.className = "scrub-line";
  compareTracksEl.appendChild(scrubLineEl);

  renderInsights(breakdowns);
  setMode("compare");
}

compareBtn.addEventListener("click", () => runCompare([...selectedIds]));

// ---------- upload (multi-file queue, analyzed sequentially) ----------

let nextQueueId = 1;

function resetUpload() {
  uploadQueue = [];
  uploadRunning = false;
  fileInput.value = "";
  uploadArtistEl.value = "";
  uploadFieldsEl.classList.add("hidden");
  uploadErrorEl.classList.add("hidden");
  uploadSubmitBtn.disabled = false;
  uploadSubmitBtn.textContent = "Analyze";
  uploadCancelBtn.textContent = "Cancel";
  uploadCancelBtn.classList.remove("hidden");
  dropzone.classList.remove("hidden");
}

function addFilesToQueue(files) {
  if (!files || files.length === 0) return;
  for (const file of files) {
    uploadQueue.push({
      id: nextQueueId++,
      file,
      title: file.name.replace(/\.[^/.]+$/, ""),
      status: "pending",
      error: null,
    });
  }
  dropzone.classList.add("hidden");
  uploadFieldsEl.classList.remove("hidden");
  uploadErrorEl.classList.add("hidden");
  renderUploadQueue();
}

function removeFromQueue(id) {
  uploadQueue = uploadQueue.filter((entry) => entry.id !== id);
  if (uploadQueue.length === 0) {
    resetUpload();
  } else {
    renderUploadQueue();
  }
}

const STATUS_LABEL = {
  pending: "queued",
  analyzing: "analyzing…",
  done: "done",
  error: "failed",
};

function renderUploadQueue() {
  uploadQueueEl.innerHTML = "";
  for (const entry of uploadQueue) {
    const li = document.createElement("li");
    li.className = "upload-queue-item";

    const titleInput = document.createElement("input");
    titleInput.type = "text";
    titleInput.value = entry.title;
    titleInput.disabled = uploadRunning;
    titleInput.addEventListener("input", () => {
      entry.title = titleInput.value;
    });
    li.appendChild(titleInput);

    const status = document.createElement("span");
    status.className = `upload-queue-status status-${entry.status}`;
    status.textContent = STATUS_LABEL[entry.status];
    status.title = entry.error || "";
    li.appendChild(status);

    if (!uploadRunning) {
      const removeBtn = document.createElement("button");
      removeBtn.className = "upload-queue-remove";
      removeBtn.textContent = "×";
      removeBtn.addEventListener("click", () => removeFromQueue(entry.id));
      li.appendChild(removeBtn);
    }

    uploadQueueEl.appendChild(li);
  }
  uploadQueueCountEl.textContent = `(${uploadQueue.length})`;
}

async function uploadOne(entry) {
  const formData = new FormData();
  formData.append("file", entry.file);
  if (entry.title.trim()) formData.append("title", entry.title.trim());
  if (uploadArtistEl.value.trim()) formData.append("artist", uploadArtistEl.value.trim());

  const res = await fetch("/api/analyze", { method: "POST", body: formData });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Analysis failed");
  return data;
}

dropzone.addEventListener("click", () => fileInput.click());
fileInput.addEventListener("change", () => addFilesToQueue([...fileInput.files]));

["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-active");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-active");
  })
);
dropzone.addEventListener("drop", (e) => {
  addFilesToQueue([...e.dataTransfer.files]);
});

uploadCancelBtn.addEventListener("click", resetUpload);

uploadSubmitBtn.addEventListener("click", async () => {
  if (uploadRunning || uploadQueue.length === 0) return;

  uploadRunning = true;
  uploadSubmitBtn.disabled = true;
  uploadCancelBtn.classList.add("hidden");
  uploadErrorEl.classList.add("hidden");
  renderUploadQueue();

  let lastSucceededId = null;
  let failures = 0;

  for (const entry of uploadQueue) {
    entry.status = "analyzing";
    renderUploadQueue();
    try {
      const data = await uploadOne(entry);
      entry.status = "done";
      lastSucceededId = data.song.id;
    } catch (err) {
      entry.status = "error";
      entry.error = err.message;
      failures += 1;
    }
    renderUploadQueue();
  }

  await loadSongs();

  uploadCancelBtn.textContent = "Close";
  uploadCancelBtn.classList.remove("hidden");
  uploadSubmitBtn.textContent = failures > 0 ? `Done (${failures} failed)` : "Done";

  if (lastSucceededId != null) {
    selectSong(lastSucceededId);
  }
});

// ---------- init ----------

// Supports deep-linking a specific view, e.g. for sharing a link or scripting
// screenshots: ?song=3 opens a single song, ?compare=1,2,3 opens compare mode.
async function initFromUrl() {
  await loadSongs();

  const params = new URLSearchParams(window.location.search);
  const compareParam = params.get("compare");
  const songParam = params.get("song");

  if (compareParam) {
    const ids = compareParam.split(",").map(Number).filter((n) => !Number.isNaN(n));
    if (ids.length >= 2) await runCompare(ids);
  } else if (songParam) {
    const id = Number(songParam);
    if (!Number.isNaN(id)) await selectSong(id);
  }
}

initFromUrl();
