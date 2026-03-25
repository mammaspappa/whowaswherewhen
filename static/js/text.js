(() => {
    const params = new URLSearchParams(window.location.search);
    const personId = params.get('id');
    if (!personId) {
        document.getElementById('article-content').innerHTML = '<p>No person specified.</p>';
        return;
    }

    document.addEventListener('DOMContentLoaded', async () => {
        const article = await API.getPersonArticle(parseInt(personId));
        if (article.error) {
            document.getElementById('article-content').innerHTML = '<p>Person not found.</p>';
            return;
        }

        const p = article.person;
        document.title = `${p.name} – WhoWasWhereWhen`;

        // Tabs
        document.getElementById('tab-links').innerHTML = `
            <a href="/static/person.html?id=${personId}">Map View</a>
            <a href="/static/text.html?id=${personId}" class="active">Text View</a>
            <a href="/static/history.html?type=person&id=${personId}">History (${article.revision_count})</a>
        `;

        const content = document.getElementById('article-content');
        content.innerHTML = '';

        // Person header
        const header = document.createElement('div');
        header.className = 'text-header';
        let meta = '';
        if (p.birth_date_display) meta += p.birth_date_display;
        if (p.death_date_display) meta += ' &ndash; ' + esc(p.death_date_display);
        header.innerHTML = `
            <h2>${esc(p.name)}</h2>
            <div class="text-meta">${meta}${p.wikipedia_url ? ` | <a href="${esc(p.wikipedia_url)}" target="_blank">Wikipedia</a>` : ''}</div>
        `;
        content.appendChild(header);

        // Description
        if (p.description) {
            const desc = document.createElement('div');
            desc.className = 'text-description';
            desc.textContent = p.description;
            content.appendChild(desc);
        }

        // Whereabouts section
        if (article.whereabouts.length > 0) {
            const section = document.createElement('div');
            section.className = 'text-whereabouts';
            section.innerHTML = '<h3>Known Whereabouts</h3>';

            article.whereabouts.forEach(w => {
                const entry = document.createElement('div');
                entry.className = 'text-whereabout';

                let sourcesHtml = '';
                if (w.sources && w.sources.length > 0) {
                    const links = w.sources.map(s =>
                        s.url ? `<a href="${esc(s.url)}" target="_blank">${esc(s.title)}</a>` : esc(s.title)
                    );
                    sourcesHtml = `<div class="text-sources">Sources: ${links.join(', ')}</div>`;
                }

                entry.innerHTML = `
                    <h4><a href="/static/whereabout.html?id=${w.id}">${esc(w.place_name)}</a> <span class="text-date">(${esc(w.date_display || '')})</span></h4>
                    <p>${esc(w.description || '')}</p>
                    <div class="text-meta-line">
                        <span class="text-confidence">Confidence: ${w.confidence}</span>
                        <a href="/static/history.html?type=whereabout&id=${w.id}" class="text-history-link">history</a>
                        <button class="discussion-toggle-btn" data-wid="${w.id}">discuss</button>
                    </div>
                    ${sourcesHtml}
                    <div class="inline-discussion" id="disc-w-${w.id}"></div>
                `;
                section.appendChild(entry);
            });
            content.appendChild(section);

            // Wire up discussion toggles
            content.querySelectorAll('.discussion-toggle-btn').forEach(btn => {
                btn.addEventListener('click', () => {
                    const wid = btn.dataset.wid;
                    const container = document.getElementById(`disc-w-${wid}`);
                    if (container.dataset.loaded) {
                        container.style.display = container.style.display === 'none' ? 'block' : 'none';
                    } else {
                        container.dataset.loaded = '1';
                        container.style.display = 'block';
                        Discussion.init(`disc-w-${wid}`, 'whereabout', parseInt(wid));
                    }
                });
            });
        } else {
            const empty = document.createElement('p');
            empty.className = 'text-empty';
            empty.textContent = 'No whereabouts recorded yet.';
            content.appendChild(empty);
        }

        // Person-level discussion
        const discSection = document.createElement('div');
        discSection.className = 'text-discussion-section';
        discSection.innerHTML = `<h3>Discussion (${article.discussion_count})</h3><div id="person-discussion"></div>`;
        content.appendChild(discSection);
        Discussion.init('person-discussion', 'person', parseInt(personId));
    });

    function esc(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
})();
