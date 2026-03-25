const Search = (() => {
    let input, dropdown;
    let debounceTimer = null;
    let onSelect = null;

    function init(inputId, dropdownId, callback) {
        input = document.getElementById(inputId);
        dropdown = document.getElementById(dropdownId);
        onSelect = callback;

        input.addEventListener('input', () => {
            clearTimeout(debounceTimer);
            const q = input.value.trim();
            if (q.length < 2) {
                hide();
                return;
            }
            debounceTimer = setTimeout(() => doSearch(q), 250);
        });

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') hide();
        });

        document.addEventListener('click', (e) => {
            if (!input.contains(e.target) && !dropdown.contains(e.target)) {
                hide();
            }
        });
    }

    async function doSearch(query) {
        const results = await API.searchPersons(query);
        if (results.length === 0) {
            dropdown.innerHTML = '<div class="dropdown-item"><em>No results</em></div>';
        } else {
            dropdown.innerHTML = results.map(p => `
                <div class="dropdown-item" data-id="${p.id}">
                    <div class="name">${escapeHtml(p.name)}</div>
                    <div class="dates">${escapeHtml(p.birth_date_display || '')} – ${escapeHtml(p.death_date_display || '')}</div>
                </div>
            `).join('');

            dropdown.querySelectorAll('.dropdown-item[data-id]').forEach(item => {
                item.addEventListener('click', () => {
                    const id = parseInt(item.dataset.id);
                    const name = item.querySelector('.name').textContent;
                    hide();
                    input.value = '';
                    if (onSelect) onSelect(id, name);
                });
            });
        }
        dropdown.classList.remove('hidden');
    }

    function hide() {
        dropdown.classList.add('hidden');
    }

    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    return { init };
})();
