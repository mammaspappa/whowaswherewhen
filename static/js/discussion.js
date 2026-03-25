const Discussion = (() => {
    function init(containerId, targetType, targetId) {
        const container = document.getElementById(containerId);
        if (!container) return;
        container.innerHTML = '<p class="loading">Loading discussion...</p>';
        render(container, targetType, targetId);
    }

    async function render(container, targetType, targetId) {
        const discussions = await API.getDiscussions(targetType, targetId);
        container.innerHTML = '';

        // Post form
        container.appendChild(buildPostForm(targetType, targetId, null, container));

        if (discussions.length === 0) {
            const empty = document.createElement('p');
            empty.className = 'discussion-empty';
            empty.textContent = 'No discussion yet. Be the first to comment.';
            container.appendChild(empty);
            return;
        }

        discussions.forEach(comment => {
            container.appendChild(buildComment(comment, targetType, targetId, container));
        });
    }

    function buildComment(comment, targetType, targetId, rootContainer) {
        const el = document.createElement('div');
        el.className = 'discussion-comment';
        el.dataset.id = comment.id;

        const header = document.createElement('div');
        header.className = 'discussion-header';
        header.innerHTML = `
            <span class="discussion-author">${esc(comment.author_name || 'Anonymous')}</span>
            <span class="discussion-date">${formatDate(comment.created_at)}${comment.updated_at !== comment.created_at ? ' (edited)' : ''}</span>
        `;
        el.appendChild(header);

        const body = document.createElement('div');
        body.className = 'discussion-body';
        body.textContent = comment.body;
        el.appendChild(body);

        const actions = document.createElement('div');
        actions.className = 'discussion-actions';

        // Reply button (only for top-level)
        if (!comment.parent_id) {
            const replyBtn = document.createElement('button');
            replyBtn.className = 'discussion-action-btn';
            replyBtn.textContent = 'Reply';
            replyBtn.addEventListener('click', () => {
                // Toggle reply form
                let existing = el.querySelector('.discussion-reply-form');
                if (existing) { existing.remove(); return; }
                const form = buildPostForm(targetType, targetId, comment.id, rootContainer);
                form.className = 'discussion-reply-form';
                el.appendChild(form);
            });
            actions.appendChild(replyBtn);
        }

        el.appendChild(actions);

        // Render replies
        if (comment.replies && comment.replies.length > 0) {
            const repliesContainer = document.createElement('div');
            repliesContainer.className = 'discussion-replies';
            comment.replies.forEach(reply => {
                repliesContainer.appendChild(buildComment(reply, targetType, targetId, rootContainer));
            });
            el.appendChild(repliesContainer);
        }

        return el;
    }

    function buildPostForm(targetType, targetId, parentId, rootContainer) {
        const form = document.createElement('form');
        form.className = 'discussion-form';
        form.innerHTML = `
            <input type="text" class="disc-author" placeholder="Your name (optional)">
            <textarea class="disc-body" placeholder="${parentId ? 'Write a reply...' : 'Start a new discussion topic...'}" required></textarea>
            <button type="submit" class="btn">${parentId ? 'Reply' : 'Post'}</button>
        `;
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const authorInput = form.querySelector('.disc-author');
            const bodyInput = form.querySelector('.disc-body');
            const btn = form.querySelector('button');

            if (!bodyInput.value.trim()) return;
            btn.disabled = true;
            btn.textContent = 'Posting...';

            const data = {
                target_type: targetType,
                target_id: targetId,
                body: bodyInput.value.trim(),
            };
            if (parentId) data.parent_id = parentId;
            if (authorInput.value.trim()) data.author_name = authorInput.value.trim();

            await API.postDiscussion(data);
            // Re-render the whole discussion
            render(rootContainer, targetType, targetId);
        });
        return form;
    }

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

    return { init };
})();
