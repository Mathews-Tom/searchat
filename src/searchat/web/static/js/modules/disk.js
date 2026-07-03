// Disk Manager Module
// Read-only per-agent and Searchat self disk-usage dashboard.

export async function showDiskManager() {
    const resultsDiv = document.getElementById('results');
    const filtersDiv = document.getElementById('filters');
    const heroElements = [
        document.getElementById('heroTitle'),
        document.getElementById('heroSubtitle'),
        document.getElementById('search')
    ];

    filtersDiv.style.display = 'none';
    heroElements.forEach(el => { if (el) el.style.display = 'none'; });

    resultsDiv.innerHTML = '<div class="loading">Loading disk usage...</div>';

    await renderDiskManager(resultsDiv);
}

async function renderDiskManager(resultsDiv) {
    try {
        const resp = await fetch('/api/disk');
        if (!resp.ok) {
            throw new Error(`Request failed with status ${resp.status}`);
        }
        const report = await resp.json();

        resultsDiv.innerHTML = `
            <div style="max-width: 1200px; margin: 0 auto;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; gap: 12px; flex-wrap: wrap;">
                    <div style="display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;">
                        <h2 style="margin: 0; font-size: 28px; color: hsl(var(--text-primary));">Disk Manager</h2>
                        <button id="diskRefresh" class="glass-btn">Refresh</button>
                    </div>
                    <a href="/" style="color: hsl(var(--accent)); text-decoration: none; font-weight: 500;">&#8592; Back to Search</a>
                </div>

                <!-- Agents -->
                <div class="glass" style="margin-bottom: 24px;">
                    <div class="card-title">Registered Agents</div>
                    <p style="color: hsl(var(--text-secondary)); margin: 0 0 16px 0; font-size: 14px;">Per-connector disk usage: size on disk, conversation count, age, and indexed-vs-unindexed delta. Read-only.</p>
                    ${renderAgents(report.agents)}
                </div>

                <!-- Searchat self -->
                <div class="glass">
                    <div class="card-title">Searchat's Own Footprint</div>
                    <p style="color: hsl(var(--text-secondary)); margin: 0 0 16px 0; font-size: 14px;">Index, backups, models, and expertise storage under ${escapeHtml(report.searchat_self.search_dir)}.</p>
                    ${renderSelfUsage(report.searchat_self)}
                </div>
            </div>
        `;

        const refreshEl = document.getElementById('diskRefresh');
        if (refreshEl) {
            refreshEl.addEventListener('click', async () => {
                resultsDiv.innerHTML = '<div class="loading">Loading disk usage...</div>';
                await renderDiskManager(resultsDiv);
            });
        }
    } catch (error) {
        resultsDiv.innerHTML = `
            <div style="text-align: center; padding: 40px; color: hsl(var(--danger));">
                Failed to load disk usage: ${escapeHtml(error.message)}
                <br><br>
                <a href="/" style="color: hsl(var(--accent));">&#8592; Back to Search</a>
            </div>
        `;
    }
}

function renderAgents(agents) {
    if (!agents || agents.length === 0) {
        return '<div style="color: hsl(var(--text-tertiary)); font-style: italic;">No registered connectors discovered any files.</div>';
    }

    return `
        <div class="stat-grid" style="margin-bottom: 20px;">
            ${agents.map(a => renderAgentCard(a)).join('')}
        </div>
    `;
}

function renderAgentCard(agent) {
    const unindexedClass = agent.unindexed_file_count > 0 ? 'bad' : 'good';
    return `
        <div class="stat-card" style="min-width: 220px;">
            <div class="stat-label">${escapeHtml(agent.connector)}</div>
            <div class="stat-value neutral">${formatBytes(agent.total_size_bytes)}</div>
            <div class="stat-sub">${agent.total_file_count} files &middot; ${agent.conversation_file_count} conversations</div>
            <div style="margin-top: 8px; font-size: 12px; color: hsl(var(--text-tertiary));">
                <span class="badge badge-good">${agent.indexed_file_count} indexed</span>
                <span class="badge badge-${unindexedClass === 'bad' ? 'bad' : 'good'}" style="margin-left: 4px;">${agent.unindexed_file_count} unindexed</span>
            </div>
            <div style="margin-top: 6px; font-size: 12px; color: hsl(var(--text-tertiary));">
                Age: ${formatAge(agent.newest_conversation_age_days)} &ndash; ${formatAge(agent.oldest_conversation_age_days)}
            </div>
        </div>
    `;
}

function renderSelfUsage(selfUsage) {
    if (!selfUsage || !selfUsage.subdirectories || selfUsage.subdirectories.length === 0) {
        return '<div style="color: hsl(var(--text-tertiary)); font-style: italic;">No data available.</div>';
    }

    return `
        <div style="display: grid; gap: 8px; margin-bottom: 12px;">
            ${selfUsage.subdirectories.map(sub => `
                <div class="glass" style="display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 10px 14px;">
                    <div style="font-weight: 600; color: hsl(var(--text-primary)); text-transform: capitalize;">${escapeHtml(sub.label)}</div>
                    <div style="font-size: 13px; color: hsl(var(--text-tertiary));">
                        ${sub.exists ? `${formatBytes(sub.total_size_bytes)} &middot; ${sub.file_count} files` : '<span style="font-style: italic;">not present</span>'}
                    </div>
                </div>
            `).join('')}
        </div>
        <div style="font-weight: 700; color: hsl(var(--text-primary));">
            Total: ${formatBytes(selfUsage.total_size_bytes)} across ${selfUsage.total_file_count} files
        </div>
    `;
}

function formatBytes(numBytes) {
    let value = Number(numBytes) || 0;
    const units = ['B', 'KB', 'MB', 'GB', 'TB'];
    let unitIndex = 0;
    while (Math.abs(value) >= 1024 && unitIndex < units.length - 1) {
        value /= 1024;
        unitIndex += 1;
    }
    return `${value.toFixed(1)} ${units[unitIndex]}`;
}

function formatAge(ageDays) {
    if (ageDays === null || ageDays === undefined) {
        return '-';
    }
    if (ageDays < 1) {
        return `${Math.round(ageDays * 24)}h`;
    }
    return `${Math.round(ageDays)}d`;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text ?? '';
    return div.innerHTML;
}
