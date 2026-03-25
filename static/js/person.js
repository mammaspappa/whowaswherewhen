(() => {
    const params = new URLSearchParams(window.location.search);
    const personId = params.get('id');
    if (!personId) {
        document.getElementById('person-name').textContent = 'No person specified';
        return;
    }

    document.addEventListener('DOMContentLoaded', async () => {
        const person = await API.getPerson(parseInt(personId));
        if (person.error) {
            document.getElementById('person-name').textContent = 'Person not found';
            return;
        }

        // Tabs
        document.getElementById('tab-links').innerHTML = `
            <a href="/static/person.html?id=${personId}" class="active">Map View</a>
            <a href="/static/text.html?id=${personId}">Text View</a>
            <a href="/static/history.html?type=person&id=${personId}">History</a>
        `;

        // Header
        document.title = `${person.name} – WhoWasWhereWhen`;
        document.getElementById('person-name').textContent = person.name;

        let meta = '';
        if (person.birth_date_display) meta += person.birth_date_display;
        if (person.death_date_display) meta += ' – ' + person.death_date_display;
        if (person.wikipedia_url) {
            meta += ` | <a href="${escapeHtml(person.wikipedia_url)}" target="_blank">Wikipedia</a>`;
        }
        document.getElementById('person-meta').innerHTML = meta;
        document.getElementById('person-desc').textContent = person.description || '';

        // Map
        const map = L.map('person-map').setView([30, 0], 2);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 18,
        }).addTo(map);

        const whereabouts = person.whereabouts || [];
        const markers = [];
        const pathCoords = [];

        whereabouts.forEach(w => {
            const marker = L.circleMarker([w.latitude, w.longitude], {
                radius: 7,
                color: '#3498db',
                fillColor: '#3498db',
                fillOpacity: 0.7,
                weight: 2,
            });
            marker.bindPopup(`
                <div class="popup-place">${escapeHtml(w.place_name)}</div>
                <div class="popup-date">${escapeHtml(w.date_display || '')}</div>
                <div class="popup-desc">${escapeHtml(w.description || '')}</div>
                <div class="popup-confidence">${w.confidence}${w.extraction_method ? ' &middot; ' + escapeHtml(w.extraction_method) : ''}</div>
            `);
            marker.addTo(map);
            markers.push(marker);
            pathCoords.push([w.latitude, w.longitude]);
        });

        if (pathCoords.length > 1) {
            L.polyline(pathCoords, { color: '#3498db', weight: 2, opacity: 0.4, dashArray: '5, 8' }).addTo(map);
        }

        if (markers.length > 0) {
            map.fitBounds(L.featureGroup(markers).getBounds().pad(0.1));
        }

        // Timeline list
        const listEl = document.getElementById('person-timeline-list');
        for (const w of whereabouts) {
            const sources = await API.getSources(w.id);
            const sourcesHtml = sources.length > 0
                ? '<div class="te-sources">Sources: ' + sources.map(s =>
                    s.url ? `<a href="${escapeHtml(s.url)}" target="_blank">${escapeHtml(s.title)}</a>` : escapeHtml(s.title)
                  ).join(', ') + '</div>'
                : '';

            const entry = document.createElement('div');
            entry.className = 'timeline-entry';

            // Method and verification badges
            let badges = '';
            if (w.extraction_method) {
                badges += `<span class="wa-badge wa-badge-method">${escapeHtml(w.extraction_method)}</span>`;
            }
            if (w.verified) {
                badges += `<span class="wa-badge wa-badge-verified">Verified</span>`;
            }

            // Source text preview
            let sourceTextHtml = '';
            if (w.source_text) {
                const preview = w.source_text.length > 150 ? w.source_text.substring(0, 150) + '...' : w.source_text;
                sourceTextHtml = `<div class="te-source-text">${escapeHtml(preview)}</div>`;
            }

            entry.innerHTML = `
                <div class="te-date">${escapeHtml(w.date_display || '')}</div>
                <div class="te-place">
                    <a href="/static/whereabout.html?id=${w.id}">${escapeHtml(w.place_name)}</a>
                    ${badges}
                </div>
                <div class="te-desc">${escapeHtml(w.description || '')}</div>
                ${sourceTextHtml}
                <div class="te-confidence">${w.confidence}${w.created_at ? ' &middot; added ' + escapeHtml(w.created_at.split('T')[0] || w.created_at.split(' ')[0]) : ''}</div>
                ${sourcesHtml}
            `;
            listEl.appendChild(entry);
        }

        if (whereabouts.length === 0) {
            listEl.innerHTML = '<p style="color:#888;padding:8px">No whereabouts recorded yet.</p>';
        }

        // Init person-level discussion
        Discussion.init('person-discussions', 'person', parseInt(personId));
    });

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
})();
