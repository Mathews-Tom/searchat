// Search Analytics Module
// Displays search patterns and statistics

export async function showAnalytics() {
    const resultsDiv = document.getElementById('results');
    const filtersDiv = document.getElementById('filters');
    const heroElements = [
        document.getElementById('heroTitle'),
        document.getElementById('heroSubtitle'),
        document.getElementById('search')
    ];

    // Hide search UI
    filtersDiv.style.display = 'none';
    heroElements.forEach(el => { if (el) el.style.display = 'none'; });

    // Show loading state
    resultsDiv.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-muted);">Loading analytics...</div>';

    try {
        // Fetch analytics data
        const [summaryResp, topQueriesResp, deadEndsResp] = await Promise.all([
            fetch('/api/stats/analytics/summary?days=30'),
            fetch('/api/stats/analytics/top-queries?limit=10&days=30'),
            fetch('/api/stats/analytics/dead-ends?limit=10&days=30')
        ]);

        const summary = await summaryResp.json();
        const topQueries = await topQueriesResp.json();
        const deadEnds = await deadEndsResp.json();

        // Render analytics dashboard
        resultsDiv.innerHTML = `
            <div style="max-width: 1200px; margin: 0 auto;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 32px;">
                    <h2 style="margin: 0; font-size: 28px; color: var(--text-primary);">Search Analytics</h2>
                    <a href="/" style="color: var(--accent-primary); text-decoration: none; font-weight: 500;">← Back to Search</a>
                </div>

                <!-- Summary Cards -->
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px;">
                    ${renderSummaryCard('Total Searches', summary.total_searches, '🔍')}
                    ${renderSummaryCard('Unique Queries', summary.unique_queries, '📝')}
                    ${renderSummaryCard('Avg Results', summary.avg_results, '📊')}
                    ${renderSummaryCard('Avg Time (ms)', summary.avg_time_ms, '⚡')}
                </div>

                <!-- Search Mode Distribution -->
                ${renderModeDistribution(summary.mode_distribution)}

                <!-- Top Queries -->
                <div style="background: var(--bg-surface); border: 1px solid var(--border-primary); border-radius: 12px; padding: 24px; margin-bottom: 24px;">
                    <h3 style="margin: 0 0 20px 0; font-size: 20px; color: var(--text-primary);">🔥 Top Searches (Last 30 Days)</h3>
                    ${renderTopQueries(topQueries.queries)}
                </div>

                <!-- Dead End Queries -->
                <div style="background: var(--bg-surface); border: 1px solid var(--border-primary); border-radius: 12px; padding: 24px;">
                    <h3 style="margin: 0 0 20px 0; font-size: 20px; color: var(--text-primary);">💀 Dead End Searches</h3>
                    <p style="color: var(--text-muted); margin: 0 0 16px 0; font-size: 14px;">Queries that returned 3 or fewer results</p>
                    ${renderDeadEndQueries(deadEnds.queries)}
                </div>
            </div>
        `;

    } catch (error) {
        resultsDiv.innerHTML = `
            <div style="text-align: center; padding: 40px; color: var(--error);">
                Failed to load analytics: ${error.message}
                <br><br>
                <a href="/" style="color: var(--accent-primary);">← Back to Search</a>
            </div>
        `;
    }
}

function renderSummaryCard(label, value, icon) {
    return `
        <div style="background: var(--bg-surface); border: 1px solid var(--border-primary); border-radius: 12px; padding: 20px; text-align: center;">
            <div style="font-size: 32px; margin-bottom: 8px;">${icon}</div>
            <div style="font-size: 28px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px;">${formatNumber(value)}</div>
            <div style="font-size: 13px; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px;">${label}</div>
        </div>
    `;
}

function renderModeDistribution(modeDistribution) {
    if (!modeDistribution || Object.keys(modeDistribution).length === 0) {
        return '';
    }

    const total = Object.values(modeDistribution).reduce((sum, count) => sum + count, 0);
    const modes = Object.entries(modeDistribution).map(([mode, count]) => ({
        mode,
        count,
        percentage: ((count / total) * 100).toFixed(1)
    }));

    const modeColors = {
        'hybrid': '#4a9eff',
        'semantic': '#ff9500',
        'keyword': '#9C27B0'
    };

    return `
        <div style="background: var(--bg-surface); border: 1px solid var(--border-primary); border-radius: 12px; padding: 24px; margin-bottom: 24px;">
            <h3 style="margin: 0 0 20px 0; font-size: 20px; color: var(--text-primary);">Search Mode Distribution</h3>
            <div style="display: flex; gap: 16px; flex-wrap: wrap;">
                ${modes.map(m => `
                    <div style="flex: 1; min-width: 150px; background: var(--bg-primary); border: 1px solid var(--border-muted); border-radius: 8px; padding: 16px;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                            <div style="width: 12px; height: 12px; border-radius: 50%; background: ${modeColors[m.mode] || '#888'};"></div>
                            <div style="font-weight: 600; color: var(--text-primary); text-transform: capitalize;">${m.mode}</div>
                        </div>
                        <div style="font-size: 24px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px;">${m.count}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">${m.percentage}% of searches</div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;
}

function renderTopQueries(queries) {
    if (!queries || queries.length === 0) {
        return '<div style="color: var(--text-muted); font-style: italic;">No data available yet. Start searching to see analytics!</div>';
    }

    return `
        <div style="display: grid; gap: 12px;">
            ${queries.map((q, index) => `
                <div style="display: flex; align-items: center; gap: 16px; padding: 12px; background: var(--bg-primary); border: 1px solid var(--border-muted); border-radius: 8px;">
                    <div style="font-size: 18px; font-weight: 700; color: var(--text-muted); min-width: 30px;">#${index + 1}</div>
                    <div style="flex: 1;">
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 14px; color: var(--text-primary); margin-bottom: 4px;">${escapeHtml(q.query)}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">
                            ${q.search_count} searches · ${q.avg_results} avg results · ${q.avg_time_ms}ms avg time
                        </div>
                    </div>
                    <button onclick="window.location.href = '/?q=${encodeURIComponent(q.query)}'" style="background: var(--accent-primary); color: white; border: none; border-radius: 6px; padding: 8px 16px; cursor: pointer; font-size: 12px; font-weight: 500;">
                        Search Again
                    </button>
                </div>
            `).join('')}
        </div>
    `;
}

function renderDeadEndQueries(queries) {
    if (!queries || queries.length === 0) {
        return '<div style="color: var(--text-muted); font-style: italic;">No dead ends found!</div>';
    }

    return `
        <div style="display: grid; gap: 12px;">
            ${queries.map((q, index) => `
                <div style="display: flex; align-items: center; gap: 16px; padding: 12px; background: var(--bg-primary); border: 1px solid var(--border-muted); border-radius: 8px;">
                    <div style="font-size: 18px; font-weight: 700; color: var(--text-muted); min-width: 30px;">#${index + 1}</div>
                    <div style="flex: 1;">
                        <div style="font-family: 'JetBrains Mono', monospace; font-size: 14px; color: var(--text-primary); margin-bottom: 4px;">${escapeHtml(q.query)}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">
                            ${q.search_count} searches · ${q.avg_results} avg results
                        </div>
                    </div>
                    <div style="background: var(--warning); color: var(--text-primary); border-radius: 6px; padding: 4px 12px; font-size: 12px; font-weight: 500;">
                        Low Results
                    </div>
                </div>
            `).join('')}
        </div>
    `;
}

function formatNumber(num) {
    if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'k';
    }
    return num.toString();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
