(() => {
    const params = new URLSearchParams(window.location.search);
    const wId = params.get('id');
    if (!wId) {
        document.getElementById('wa-content').innerHTML = '<p>No whereabout specified.</p>';
        return;
    }

    let currentData = null;

    document.addEventListener('DOMContentLoaded', async () => {
        await loadAndRender();
        Discussion.init('wa-discussions', 'whereabout', parseInt(wId));
    });

    let prevWhereabout = null;
    let nextWhereabout = null;

    async function loadAndRender() {
        const w = await API.getWhereabout(parseInt(wId));
        if (w.error) {
            document.getElementById('wa-content').innerHTML = '<p>Whereabout not found.</p>';
            return;
        }
        currentData = w;
        document.title = `${w.place_name} – ${w.person_name || 'Unknown'} – WhoWasWhereWhen`;

        // Fetch siblings for prev/next navigation
        prevWhereabout = null;
        nextWhereabout = null;
        if (w.person_id) {
            const person = await API.getPerson(w.person_id);
            if (person && person.whereabouts) {
                const ww = person.whereabouts;
                const idx = ww.findIndex(x => x.id === w.id);
                if (idx > 0) prevWhereabout = ww[idx - 1];
                if (idx >= 0 && idx < ww.length - 1) nextWhereabout = ww[idx + 1];
            }
        }

        renderView(w);
        renderMap(w);
    }

    function renderView(w) {
        const el = document.getElementById('wa-content');

        let sourcesHtml = '';
        if (w.sources && w.sources.length > 0) {
            const items = w.sources.map(s => {
                let html = s.url ? `<a href="${esc(s.url)}" target="_blank">${esc(s.title)}</a>` : esc(s.title);
                if (s.author) html += ` <span class="wa-source-author">by ${esc(s.author)}</span>`;
                if (s.source_type) html += ` <span class="wa-badge wa-badge-source">${esc(s.source_type)}</span>`;
                if (s.excerpt) html += `<div class="wa-source-excerpt">${esc(s.excerpt)}</div>`;
                return `<li>${html}</li>`;
            });
            sourcesHtml = `<div class="wa-sources"><strong>Sources:</strong><ul>${items.join('')}</ul></div>`;
        }

        // Source text excerpt
        let sourceTextHtml = '';
        if (w.source_text) {
            sourceTextHtml = `
                <div class="wa-source-text">
                    <strong>Source Text:</strong>
                    <blockquote>${esc(w.source_text)}</blockquote>
                </div>`;
        }

        // Provenance section
        const provRows = [];
        if (w.extraction_method) provRows.push(['Method', methodLabel(w.extraction_method)]);
        if (w.extraction_model) provRows.push(['Model', w.extraction_model]);
        if (w.created_by) provRows.push(['Created by', w.created_by]);
        if (w.extracted_at) provRows.push(['Extracted', formatDate(w.extracted_at)]);
        if (w.created_at) provRows.push(['Added to DB', formatDate(w.created_at)]);
        if (w.geocode_source) provRows.push(['Geocoded via', w.geocode_source]);
        if (w.raw_place_text && w.raw_place_text !== w.place_name) provRows.push(['Original place text', w.raw_place_text]);
        if (w.raw_date_text) provRows.push(['Original date text', w.raw_date_text]);
        if (w.notes) provRows.push(['Notes', w.notes]);

        let provenanceHtml = '';
        if (provRows.length > 0) {
            const rows = provRows.map(([k, v]) =>
                `<tr><td class="wa-prov-label">${esc(k)}</td><td>${esc(v)}</td></tr>`
            ).join('');
            provenanceHtml = `
                <div class="wa-provenance">
                    <strong>Provenance:</strong>
                    <table class="wa-prov-table">${rows}</table>
                </div>`;
        }

        // Verification badge
        let verifiedHtml = '';
        if (w.verified) {
            verifiedHtml = `<span class="wa-badge wa-badge-verified" title="Verified by ${esc(w.verified_by || '?')} on ${esc(w.verified_at || '?')}">Verified</span>`;
        } else {
            verifiedHtml = `<span class="wa-badge wa-badge-unverified">Unverified</span>`;
        }

        // Navigation arrows
        let navHtml = '<div class="wa-nav">';
        if (prevWhereabout) {
            navHtml += `<a href="/static/whereabout.html?id=${prevWhereabout.id}" class="wa-nav-prev" title="${attr(prevWhereabout.place_name)} (${attr(prevWhereabout.date_display || prevWhereabout.date_start)})">&larr; ${esc(prevWhereabout.place_name)}</a>`;
        } else {
            navHtml += '<span class="wa-nav-prev wa-nav-disabled"></span>';
        }
        navHtml += `<a href="/static/person.html?id=${w.person_id}" class="wa-nav-person">${esc(w.person_name || 'Unknown')}</a>`;
        if (nextWhereabout) {
            navHtml += `<a href="/static/whereabout.html?id=${nextWhereabout.id}" class="wa-nav-next" title="${attr(nextWhereabout.place_name)} (${attr(nextWhereabout.date_display || nextWhereabout.date_start)})">${esc(nextWhereabout.place_name)} &rarr;</a>`;
        } else {
            navHtml += '<span class="wa-nav-next wa-nav-disabled"></span>';
        }
        navHtml += '</div>';

        el.innerHTML = `
            ${navHtml}
            <div class="wa-breadcrumb">
                <a href="/static/person.html?id=${w.person_id}">${esc(w.person_name || 'Unknown')}</a> &rsaquo;
                <span>${esc(w.place_name)}</span>
            </div>
            <h2>${esc(w.place_name)}</h2>
            <div class="wa-meta">
                <span class="wa-date">${esc(w.date_display || w.date_start + ' to ' + w.date_end)}</span>
                <span class="wa-confidence">Confidence: ${esc(w.confidence)}</span>
                <span class="wa-precision">Precision: ${esc(w.date_precision)}</span>
                ${w.extraction_method ? `<span class="wa-badge wa-badge-method">${esc(methodLabel(w.extraction_method))}</span>` : ''}
                ${verifiedHtml}
            </div>
            <div class="wa-description">${esc(w.description || 'No description provided.')}</div>
            <div class="wa-coords">Coordinates: ${w.latitude.toFixed(4)}, ${w.longitude.toFixed(4)}</div>
            ${sourceTextHtml}
            ${sourcesHtml}
            ${provenanceHtml}
            <div class="wa-actions">
                <button class="btn" id="edit-btn">Edit</button>
                <a href="/static/history.html?type=whereabout&id=${w.id}" class="btn btn-secondary">View History</a>
            </div>
        `;

        document.getElementById('edit-btn').addEventListener('click', () => renderEditForm(w));
    }

    function methodLabel(method) {
        const labels = {
            'wikidata': 'Wikidata SPARQL',
            'pattern': 'Pattern matching',
            'ner': 'spaCy NER',
            'category': 'Category mining',
            'claude': 'Claude AI',
            'manual': 'Manual entry',
            'seed': 'Seed data',
            'contribution': 'User contribution',
            'gemini': 'Gemini 2.5 Flash Lite',
            'gemini-flash': 'Gemini 2.5 Flash',
            'gemini-3': 'Gemini 3 Flash',
            'gemini-3.1': 'Gemini 3.1 Flash Lite',
            'groq': 'Groq (Llama)',
            'mistral': 'Mistral',
            'openrouter': 'OpenRouter',
        };
        return labels[method] || method;
    }

    function formatDate(iso) {
        if (!iso) return '';
        try {
            const d = new Date(iso);
            return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
        } catch { return iso; }
    }

    function renderEditForm(w) {
        const el = document.getElementById('wa-content');
        el.innerHTML = `
            <div class="wa-breadcrumb">
                <a href="/static/person.html?id=${w.person_id}">${esc(w.person_name || 'Unknown')}</a> &rsaquo;
                <span>Editing: ${esc(w.place_name)}</span>
            </div>
            <h2>Edit Whereabout</h2>
            <form id="edit-form" class="wa-edit-form">
                <div class="form-group">
                    <label for="ef-place">Place Name</label>
                    <input type="text" id="ef-place" value="${attr(w.place_name)}" required>
                </div>
                <div class="form-group">
                    <label for="ef-date-display">Date (display)</label>
                    <input type="text" id="ef-date-display" value="${attr(w.date_display || '')}">
                    <div class="help">Human-readable date, e.g. "Spring 1500" or "1482 - 1499"</div>
                </div>
                <div class="form-row">
                    <div class="form-group form-half">
                        <label for="ef-date-start">Date Start (ISO)</label>
                        <input type="text" id="ef-date-start" value="${attr(w.date_start)}" required>
                    </div>
                    <div class="form-group form-half">
                        <label for="ef-date-end">Date End (ISO)</label>
                        <input type="text" id="ef-date-end" value="${attr(w.date_end)}" required>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group form-half">
                        <label for="ef-precision">Precision</label>
                        <select id="ef-precision">
                            ${['day','month','season','year','decade','approximate'].map(p =>
                                `<option value="${p}" ${p === w.date_precision ? 'selected' : ''}>${p}</option>`
                            ).join('')}
                        </select>
                    </div>
                    <div class="form-group form-half">
                        <label for="ef-confidence">Confidence</label>
                        <select id="ef-confidence">
                            ${['certain','probable','possible','speculative'].map(c =>
                                `<option value="${c}" ${c === w.confidence ? 'selected' : ''}>${c}</option>`
                            ).join('')}
                        </select>
                    </div>
                </div>
                <div class="form-row">
                    <div class="form-group form-half">
                        <label for="ef-lat">Latitude</label>
                        <input type="number" step="any" id="ef-lat" value="${w.latitude}" required>
                    </div>
                    <div class="form-group form-half">
                        <label for="ef-lon">Longitude</label>
                        <input type="number" step="any" id="ef-lon" value="${w.longitude}" required>
                    </div>
                </div>
                <div class="form-group">
                    <label for="ef-desc">Description</label>
                    <textarea id="ef-desc" rows="3">${esc(w.description || '')}</textarea>
                </div>
                <div class="form-group">
                    <label for="ef-editor">Your Name (optional)</label>
                    <input type="text" id="ef-editor" placeholder="Anonymous">
                </div>
                <div class="form-group">
                    <label for="ef-summary">Edit Summary</label>
                    <input type="text" id="ef-summary" placeholder="What did you change and why?">
                </div>
                <div class="wa-actions">
                    <button type="submit" class="btn">Save Changes</button>
                    <button type="button" class="btn btn-secondary" id="cancel-btn">Cancel</button>
                </div>
                <div id="edit-status"></div>
            </form>
        `;

        document.getElementById('cancel-btn').addEventListener('click', () => renderView(currentData));

        document.getElementById('edit-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const status = document.getElementById('edit-status');
            const submitBtn = e.target.querySelector('button[type="submit"]');
            submitBtn.disabled = true;
            submitBtn.textContent = 'Saving...';

            const data = {
                place_name: document.getElementById('ef-place').value.trim(),
                date_start: document.getElementById('ef-date-start').value.trim(),
                date_end: document.getElementById('ef-date-end').value.trim(),
                date_display: document.getElementById('ef-date-display').value.trim(),
                date_precision: document.getElementById('ef-precision').value,
                confidence: document.getElementById('ef-confidence').value,
                latitude: parseFloat(document.getElementById('ef-lat').value),
                longitude: parseFloat(document.getElementById('ef-lon').value),
                description: document.getElementById('ef-desc').value.trim(),
            };

            const editor = document.getElementById('ef-editor').value.trim();
            const summary = document.getElementById('ef-summary').value.trim();
            if (editor) data.editor_name = editor;
            if (summary) data.edit_summary = summary;

            const result = await API.updateWhereabout(parseInt(wId), data);
            if (result.ok) {
                await loadAndRender();
            } else {
                status.innerHTML = `<span class="error">Error: ${result.error || 'Unknown error'}</span>`;
                submitBtn.disabled = false;
                submitBtn.textContent = 'Save Changes';
            }
        });
    }

    function renderMap(w) {
        const mapEl = document.getElementById('wa-map');
        mapEl.innerHTML = '';
        mapEl.style.height = '250px';

        const map = L.map(mapEl).setView([w.latitude, w.longitude], 8);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 18,
        }).addTo(map);

        L.marker([w.latitude, w.longitude]).addTo(map)
            .bindPopup(`<strong>${esc(w.place_name)}</strong>`).openPopup();
    }

    function esc(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function attr(text) {
        return (text || '').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
})();
