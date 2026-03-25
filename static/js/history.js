(() => {
    const params = new URLSearchParams(window.location.search);
    const targetType = params.get('type');
    const targetId = params.get('id');

    if (!targetType || !targetId) {
        document.getElementById('history-content').innerHTML = '<p>Missing type or id parameter.</p>';
        return;
    }

    document.addEventListener('DOMContentLoaded', async () => {
        const titleEl = document.getElementById('history-title');
        const contentEl = document.getElementById('history-content');

        // Load target name for title
        if (targetType === 'person') {
            const person = await API.getPerson(parseInt(targetId));
            titleEl.textContent = `Revision History: ${person.name || 'Unknown'}`;
            document.title = `History: ${person.name} – WhoWasWhereWhen`;
        } else {
            const w = await API.getWhereabout(parseInt(targetId));
            titleEl.textContent = `Revision History: ${w.place_name || 'Unknown'} (whereabout)`;
            document.title = `History: ${w.place_name} – WhoWasWhereWhen`;
        }

        const revisions = await API.getRevisions(targetType, parseInt(targetId));

        if (revisions.length === 0) {
            contentEl.innerHTML = '<p class="history-empty">No edits have been made yet.</p>';
            return;
        }

        revisions.forEach(rev => {
            const entry = document.createElement('div');
            entry.className = 'history-entry';

            const header = document.createElement('div');
            header.className = 'history-header';
            header.innerHTML = `
                <span class="history-date">${formatDate(rev.created_at)}</span>
                <span class="history-editor">${esc(rev.editor_name || 'Anonymous')}</span>
                ${rev.edit_summary ? `<span class="history-summary">${esc(rev.edit_summary)}</span>` : ''}
            `;
            entry.appendChild(header);

            if (rev.old_values && rev.new_values) {
                const diffTable = document.createElement('table');
                diffTable.className = 'revision-diff';
                diffTable.innerHTML = '<thead><tr><th>Field</th><th>Before</th><th>After</th></tr></thead>';
                const tbody = document.createElement('tbody');

                const fields = new Set([...Object.keys(rev.old_values), ...Object.keys(rev.new_values)]);
                fields.forEach(field => {
                    const tr = document.createElement('tr');
                    tr.className = 'diff-field';
                    const oldVal = rev.old_values[field];
                    const newVal = rev.new_values[field];
                    tr.innerHTML = `
                        <td class="diff-label">${esc(field)}</td>
                        <td class="diff-old">${oldVal != null ? esc(String(oldVal)) : '<em>empty</em>'}</td>
                        <td class="diff-new">${newVal != null ? esc(String(newVal)) : '<em>empty</em>'}</td>
                    `;
                    tbody.appendChild(tr);
                });
                diffTable.appendChild(tbody);
                entry.appendChild(diffTable);
            }

            contentEl.appendChild(entry);
        });
    });

    function formatDate(iso) {
        if (!iso) return '';
        const d = new Date(iso + 'Z');
        return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    }

    function esc(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
})();
