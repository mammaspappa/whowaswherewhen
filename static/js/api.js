const API = {
    async searchPersons(query, limit = 10) {
        const res = await fetch(`/api/persons?q=${encodeURIComponent(query)}&limit=${limit}`);
        return res.json();
    },

    async getPerson(id) {
        const res = await fetch(`/api/persons/${id}`);
        return res.json();
    },

    async getTimelineData(personIds) {
        const res = await fetch(`/api/map/timeline?person_ids=${personIds.join(',')}`);
        return res.json();
    },

    async getWhereabout(id) {
        const res = await fetch(`/api/whereabouts/${id}`);
        return res.json();
    },

    async getSources(whereaboutId) {
        const res = await fetch(`/api/sources?whereabout_id=${whereaboutId}`);
        return res.json();
    },

    async geocode(query) {
        const res = await fetch(`/api/geocode?q=${encodeURIComponent(query)}`);
        return res.json();
    },

    async submitContribution(data) {
        const res = await fetch('/api/contributions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return res.json();
    },

    // Discussions
    async getDiscussions(targetType, targetId) {
        const res = await fetch(`/api/discussions?target_type=${targetType}&target_id=${targetId}`);
        return res.json();
    },

    async postDiscussion(data) {
        const res = await fetch('/api/discussions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return res.json();
    },

    async updateDiscussion(id, data) {
        const res = await fetch(`/api/discussions/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return res.json();
    },

    // Revisions
    async getRevisions(targetType, targetId) {
        const res = await fetch(`/api/revisions?target_type=${targetType}&target_id=${targetId}`);
        return res.json();
    },

    async getRevision(id) {
        const res = await fetch(`/api/revisions/${id}`);
        return res.json();
    },

    // Text view
    async getPersonArticle(personId) {
        const res = await fetch(`/api/persons/${personId}/text`);
        return res.json();
    },

    // Updates
    async updatePerson(id, data) {
        const res = await fetch(`/api/persons/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return res.json();
    },

    async updateWhereabout(id, data) {
        const res = await fetch(`/api/whereabouts/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        return res.json();
    },
};
