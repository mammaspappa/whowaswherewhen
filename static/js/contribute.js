(() => {
    let minimap, minimarker;

    document.addEventListener('DOMContentLoaded', () => {
        // Mini map for location picking
        minimap = L.map('contrib-minimap').setView([30, 0], 2);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OSM',
            maxZoom: 18,
        }).addTo(minimap);

        minimap.on('click', (e) => {
            setLatLon(e.latlng.lat, e.latlng.lng);
        });

        // Geocode button
        document.getElementById('geocode-btn').addEventListener('click', async () => {
            const place = document.getElementById('place-name').value.trim();
            if (!place) return;
            const results = await API.geocode(place);
            if (results.length > 0) {
                setLatLon(results[0].lat, results[0].lon);
                minimap.setView([results[0].lat, results[0].lon], 8);
            }
        });

        // Form submission
        document.getElementById('contrib-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const status = document.getElementById('contrib-status');

            const dateInput = document.getElementById('date-input').value.trim();
            const parsed = parseDate(dateInput);
            if (!parsed) {
                status.innerHTML = '<span class="error">Could not parse date. Try formats like: 1815, June 1815, June 18 1815, 1810s, around 1800</span>';
                return;
            }

            const data = {
                person_name: document.getElementById('person-name').value.trim(),
                place_name: document.getElementById('place-name').value.trim(),
                latitude: parseFloat(document.getElementById('lat').value) || null,
                longitude: parseFloat(document.getElementById('lon').value) || null,
                date_start: parsed.date_start,
                date_end: parsed.date_end,
                date_precision: parsed.date_precision,
                date_display: parsed.date_display,
                description: document.getElementById('description').value.trim() || null,
                source_url: document.getElementById('source-url').value.trim() || null,
                source_title: document.getElementById('source-title').value.trim(),
                source_excerpt: document.getElementById('source-excerpt').value.trim() || null,
                contributor_name: document.getElementById('contributor-name').value.trim() || null,
            };

            try {
                const result = await API.submitContribution(data);
                if (result.id) {
                    status.innerHTML = '<span class="success">Thank you! Your contribution has been submitted for review.</span>';
                    document.getElementById('contrib-form').reset();
                    if (minimarker) { minimap.removeLayer(minimarker); minimarker = null; }
                } else {
                    status.innerHTML = `<span class="error">Error: ${result.error || 'Unknown error'}</span>`;
                }
            } catch (err) {
                status.innerHTML = `<span class="error">Network error. Please try again.</span>`;
            }
        });

        // Pre-fill from URL params
        const params = new URLSearchParams(window.location.search);
        if (params.get('person')) {
            document.getElementById('person-name').value = params.get('person');
        }
    });

    function setLatLon(lat, lon) {
        document.getElementById('lat').value = lat.toFixed(4);
        document.getElementById('lon').value = lon.toFixed(4);
        if (minimarker) minimap.removeLayer(minimarker);
        minimarker = L.marker([lat, lon]).addTo(minimap);
    }

    // --- Date Parsing ---
    const MONTHS = {
        'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
        'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6,
        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
    };

    function parseDate(input) {
        input = input.trim().toLowerCase();

        // "around YYYY"
        let m = input.match(/^around\s+(\d{3,4})$/);
        if (m) {
            const y = parseInt(m[1]);
            return {
                date_start: `${pad(y - 5)}-01-01`,
                date_end: `${pad(y + 5)}-12-31`,
                date_precision: 'approximate',
                date_display: `around ${y}`,
            };
        }

        // "YYYYs" (decade)
        m = input.match(/^(\d{3,4})s$/);
        if (m) {
            const y = parseInt(m[1]);
            return {
                date_start: `${pad(y)}-01-01`,
                date_end: `${pad(y + 9)}-12-31`,
                date_precision: 'decade',
                date_display: `the ${y}s`,
            };
        }

        // "Month DD, YYYY" or "Month DD YYYY" or "DD Month YYYY"
        m = input.match(/^(\w+)\s+(\d{1,2}),?\s+(\d{3,4})$/);
        if (m && MONTHS[m[1]]) {
            const month = MONTHS[m[1]];
            const day = parseInt(m[2]);
            const year = parseInt(m[3]);
            const ds = `${pad(year)}-${pad2(month)}-${pad2(day)}`;
            return { date_start: ds, date_end: ds, date_precision: 'day', date_display: input };
        }

        m = input.match(/^(\d{1,2})\s+(\w+)\s+(\d{3,4})$/);
        if (m && MONTHS[m[2]]) {
            const day = parseInt(m[1]);
            const month = MONTHS[m[2]];
            const year = parseInt(m[3]);
            const ds = `${pad(year)}-${pad2(month)}-${pad2(day)}`;
            return { date_start: ds, date_end: ds, date_precision: 'day', date_display: input };
        }

        // "Month YYYY"
        m = input.match(/^(\w+)\s+(\d{3,4})$/);
        if (m && MONTHS[m[1]]) {
            const month = MONTHS[m[1]];
            const year = parseInt(m[2]);
            const lastDay = new Date(year, month, 0).getDate();
            return {
                date_start: `${pad(year)}-${pad2(month)}-01`,
                date_end: `${pad(year)}-${pad2(month)}-${pad2(lastDay)}`,
                date_precision: 'month',
                date_display: input,
            };
        }

        // Plain year "YYYY"
        m = input.match(/^(\d{3,4})$/);
        if (m) {
            const year = parseInt(m[1]);
            return {
                date_start: `${pad(year)}-01-01`,
                date_end: `${pad(year)}-12-31`,
                date_precision: 'year',
                date_display: `${year}`,
            };
        }

        // Year range "YYYY-YYYY" or "YYYY to YYYY"
        m = input.match(/^(\d{3,4})\s*[-–to]+\s*(\d{3,4})$/);
        if (m) {
            const y1 = parseInt(m[1]);
            const y2 = parseInt(m[2]);
            return {
                date_start: `${pad(y1)}-01-01`,
                date_end: `${pad(y2)}-12-31`,
                date_precision: 'year',
                date_display: `${y1} - ${y2}`,
            };
        }

        return null;
    }

    function pad(year) {
        if (year < 0) return '-' + String(-year).padStart(4, '0');
        return String(year).padStart(4, '0');
    }

    function pad2(n) {
        return String(n).padStart(2, '0');
    }
})();
