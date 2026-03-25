(() => {
    const selectedPersons = new Map(); // id -> { name, color }
    const COLORS = [
        '#e74c3c', '#3498db', '#2ecc71', '#f39c12', '#9b59b6',
        '#1abc9c', '#e67e22', '#34495e', '#e91e63', '#00bcd4',
        '#8bc34a', '#ff5722'
    ];
    let colorIndex = 0;

    document.addEventListener('DOMContentLoaded', () => {
        MapView.init('map');

        Timeline.init('timeline-slider', 'timeline-label', 'play-btn', (isoDate) => {
            MapView.highlightDate(isoDate);
        });

        Search.init('search-input', 'search-dropdown', (personId, name) => {
            addPerson(personId, name);
        });

        loadAllPersons();
    });

    async function loadAllPersons() {
        const persons = await API.searchPersons('', 500);
        const list = document.getElementById('all-persons-list');
        list.innerHTML = '';
        persons.forEach(p => {
            const item = document.createElement('div');
            item.className = 'person-list-item';
            const dates = [p.birth_date_display, p.death_date_display].filter(Boolean).join(' \u2013 ');
            item.innerHTML = `
                <span class="pli-name">${escapeHtml(p.name)}</span>
                ${dates ? `<span class="pli-dates">${escapeHtml(dates)}</span>` : ''}
            `;
            item.addEventListener('click', () => addPerson(p.id, p.name));
            list.appendChild(item);
        });
        if (persons.length === 0) {
            list.innerHTML = '<p class="pli-empty">No figures in database yet.</p>';
        }
    }

    async function addPerson(personId, name) {
        if (selectedPersons.has(personId)) return;

        const color = COLORS[colorIndex % COLORS.length];
        colorIndex++;
        selectedPersons.set(personId, { name, color });

        renderChips();
        await refreshMap();
    }

    function removePerson(personId) {
        selectedPersons.delete(personId);
        MapView.removePerson(personId);
        renderChips();

        if (selectedPersons.size > 0) {
            refreshMap();
        } else {
            MapView.clearAll();
            document.getElementById('timeline-label').textContent = 'Select a figure';
        }
    }

    function renderChips() {
        const container = document.getElementById('selected-persons');
        const hint = document.getElementById('empty-hint');

        container.innerHTML = '';
        selectedPersons.forEach((info, id) => {
            const chip = document.createElement('div');
            chip.className = 'person-chip';
            chip.innerHTML = `
                <span class="dot" style="background: ${info.color}"></span>
                <span class="chip-name"><a href="/static/person.html?id=${id}">${escapeHtml(info.name)}</a></span>
                <span class="remove" data-id="${id}">&times;</span>
            `;
            chip.querySelector('.remove').addEventListener('click', () => removePerson(id));
            container.appendChild(chip);
        });

        hint.style.display = selectedPersons.size === 0 ? 'block' : 'none';
    }

    async function refreshMap() {
        const ids = Array.from(selectedPersons.keys());
        if (ids.length === 0) return;

        const data = await API.getTimelineData(ids);

        data.persons.forEach(p => {
            const info = selectedPersons.get(p.id);
            if (info) {
                // Use the color we assigned locally
                p.whereabouts.forEach(w => w.person_id = p.id);
                MapView.addPerson(p.id, info.color, p.whereabouts);
            }
        });

        Timeline.setRange(data.timeline_range.start, data.timeline_range.end);
        MapView.fitAllMarkers();
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
})();
