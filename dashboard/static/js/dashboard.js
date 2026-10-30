async function fetchJSON(url) {
    try {
        const res = await fetch(url);
        if (!res.ok) return null;
        return await res.json();
    } catch (e) {
        console.error('Fetch error:', e);
        return null;
    }
}

function statusBadgeClass(status) {
    switch (status) {
        case 'proposed': return 'bg-warning text-dark';
        case 'approved': return 'bg-info';
        case 'executing': return 'bg-primary';
        case 'completed': return 'bg-success';
        case 'rejected': return 'bg-danger';
        case 'failed': return 'bg-danger';
        case 'expired': return 'bg-secondary';
        default: return 'bg-secondary';
    }
}

function severityBadgeClass(severity) {
    switch ((severity || '').toUpperCase()) {
        case 'CRITICAL': return 'bg-danger';
        case 'HIGH': return 'bg-warning text-dark';
        case 'MEDIUM': return 'bg-info';
        case 'LOW': return 'bg-secondary';
        case 'WARNING': return 'bg-warning text-dark';
        default: return 'bg-secondary';
    }
}

function formatTime(isoStr) {
    if (!isoStr) return '—';
    try {
        const d = new Date(isoStr);
        return d.toLocaleTimeString([], {hour: '2-digit', minute: '2-digit', second: '2-digit'});
    } catch (e) {
        return isoStr;
    }
}

function truncate(str, len) {
    if (!str) return '';
    return str.length > len ? str.substring(0, len) + '...' : str;
}

// Update nav badge for pending actions
async function updateNavBadge() {
    const stats = await fetchJSON('/api/stats');
    const badge = document.getElementById('nav-pending-badge');
    if (badge && stats) {
        if (stats.pending_actions > 0) {
            badge.textContent = stats.pending_actions;
            badge.classList.remove('d-none');
        } else {
            badge.classList.add('d-none');
        }
    }
}

updateNavBadge();
setInterval(updateNavBadge, 5000);
