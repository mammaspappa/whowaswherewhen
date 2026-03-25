const MapView = (() => {
    let map;
    const personLayers = {}; // personId -> { markers: [], path: L.polyline, color }

    function init(elementId) {
        map = L.map(elementId).setView([30, 0], 2);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '&copy; OpenStreetMap contributors',
            maxZoom: 18,
        }).addTo(map);
        return map;
    }

    function getMap() { return map; }

    function addPerson(personId, color, whereabouts) {
        removePerson(personId);

        const markers = [];
        const pathCoords = [];

        whereabouts.forEach(w => {
            const marker = L.circleMarker([w.lat, w.lon], {
                radius: 7,
                color: color,
                fillColor: color,
                fillOpacity: 0.3,
                weight: 2,
                className: 'whereabout-marker',
            });

            marker.bindPopup(`
                <div class="popup-place">${escapeHtml(w.place_name)}</div>
                <div class="popup-date">${escapeHtml(w.date_display || '')}</div>
                <div class="popup-desc">${escapeHtml(w.description || '')}</div>
                <div class="popup-confidence">${w.confidence}</div>
                <div class="popup-link">
                    <a href="/static/whereabout.html?id=${w.id}">View details</a> |
                    <a href="/static/person.html?id=${w.person_id || personId}">View person</a>
                </div>
            `);

            marker.whereaboutData = w;
            marker.addTo(map);
            markers.push(marker);
            pathCoords.push([w.lat, w.lon]);
        });

        const path = L.polyline(pathCoords, {
            color: color,
            weight: 2,
            opacity: 0.4,
            dashArray: '5, 8',
        }).addTo(map);

        personLayers[personId] = { markers, path, color };

        if (markers.length > 0) {
            const group = L.featureGroup(markers);
            map.fitBounds(group.getBounds().pad(0.1));
        }
    }

    function removePerson(personId) {
        const layer = personLayers[personId];
        if (!layer) return;
        layer.markers.forEach(m => map.removeLayer(m));
        map.removeLayer(layer.path);
        delete personLayers[personId];
    }

    function highlightDate(isoDate) {
        Object.values(personLayers).forEach(layer => {
            layer.markers.forEach(marker => {
                const w = marker.whereaboutData;
                const active = w.date_start <= isoDate && w.date_end >= isoDate;
                marker.setStyle({
                    fillOpacity: active ? 0.9 : 0.15,
                    opacity: active ? 1 : 0.3,
                    radius: active ? 9 : 6,
                });
                if (active) marker.bringToFront();
            });
        });
    }

    function fitAllMarkers() {
        const allMarkers = [];
        Object.values(personLayers).forEach(l => allMarkers.push(...l.markers));
        if (allMarkers.length > 0) {
            map.fitBounds(L.featureGroup(allMarkers).getBounds().pad(0.1));
        }
    }

    function clearAll() {
        Object.keys(personLayers).forEach(removePerson);
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    return { init, getMap, addPerson, removePerson, highlightDate, fitAllMarkers, clearAll };
})();
