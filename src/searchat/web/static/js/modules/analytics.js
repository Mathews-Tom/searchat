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

    await renderAnalytics(resultsDiv, 30);
}

async function renderAnalytics(resultsDiv, days) {
    try {
        const [configResp, summaryResp, topQueriesResp, deadEndsResp, trendsResp, heatmapResp, toolsResp, topicsResp] = await Promise.all([
            fetch(`/api/stats/analytics/config`),
            fetch(`/api/stats/analytics/summary?days=${days}`),
            fetch(`/api/stats/analytics/top-queries?limit=10&days=${days}`),
            fetch(`/api/stats/analytics/dead-ends?limit=10&days=${days}`),
            fetch(`/api/stats/analytics/trends?days=${days}`),
            fetch(`/api/stats/analytics/heatmap?days=${days}`),
            fetch(`/api/stats/analytics/agent-comparison?days=${days}`),
            fetch(`/api/stats/analytics/topics?days=${days}&k=8`)
        ]);

        const config = await configResp.json();
        const summary = await summaryResp.json();
        const topQueries = await topQueriesResp.json();
        const deadEnds = await deadEndsResp.json();
        const trends = await trendsResp.json();
        const heatmap = await heatmapResp.json();
        const tools = await toolsResp.json();
        const topics = await topicsResp.json();

        resultsDiv.innerHTML = `
            <div style="max-width: 1200px; margin: 0 auto;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; gap: 12px; flex-wrap: wrap;">
                    <div style="display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap;">
                        <h2 style="margin: 0; font-size: 28px; color: var(--text-primary);">Search Analytics</h2>
                        <div style="display: inline-flex; align-items: center; gap: 8px; color: var(--text-muted); font-size: 13px;">
                            <span>Range:</span>
                            <select id="analyticsDays" style="background: var(--bg-primary); color: var(--text-primary); border: 1px solid var(--border-muted); border-radius: 8px; padding: 6px 10px; font-family: 'Space Grotesk', sans-serif;">
                                <option value="7" ${days === 7 ? 'selected' : ''}>7 days</option>
                                <option value="30" ${days === 30 ? 'selected' : ''}>30 days</option>
                                <option value="90" ${days === 90 ? 'selected' : ''}>90 days</option>
                            </select>
                            <button id="analyticsRefresh" style="background: transparent; color: var(--accent-primary); border: 1px solid var(--border-default); border-radius: 8px; padding: 6px 10px; cursor: pointer; font-size: 12px; font-weight: 600;">Refresh</button>
                        </div>
                    </div>
                    <a href="/" style="color: var(--accent-primary); text-decoration: none; font-weight: 500;">← Back to Search</a>
                </div>

                ${renderTrackingBanner(config)}

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
                    <h3 style="margin: 0 0 20px 0; font-size: 20px; color: var(--text-primary);">🔥 Top Searches (Last ${days} Days)</h3>
                    ${renderTopQueries(topQueries.queries)}
                </div>

                <!-- Dead End Queries -->
                <div style="background: var(--bg-surface); border: 1px solid var(--border-primary); border-radius: 12px; padding: 24px;">
                    <h3 style="margin: 0 0 20px 0; font-size: 20px; color: var(--text-primary);">💀 Dead End Searches</h3>
                    <p style="color: var(--text-muted); margin: 0 0 16px 0; font-size: 14px;">Queries that returned 3 or fewer results</p>
                    ${renderDeadEndQueries(deadEnds.queries)}
                </div>

                <!-- Trends -->
                <div style="background: var(--bg-surface); border: 1px solid var(--border-primary); border-radius: 12px; padding: 24px; margin-top: 24px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 20px; color: var(--text-primary);">📈 Trends (Last ${days} Days)</h3>
                    <p style="color: var(--text-muted); margin: 0 0 16px 0; font-size: 14px;">Daily searches and average latency</p>
                    ${renderTrends(trends.points)}
                </div>

                <!-- Heatmap -->
                <div style="background: var(--bg-surface); border: 1px solid var(--border-primary); border-radius: 12px; padding: 24px; margin-top: 24px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 20px; color: var(--text-primary);">🗓️ Heatmap</h3>
                    <p style="color: var(--text-muted); margin: 0 0 16px 0; font-size: 14px;">Search activity by day-of-week and hour-of-day (UTC)</p>
                    ${renderHeatmap(heatmap.cells)}
                </div>

                <!-- Agent Comparison -->
                <div style="background: var(--bg-surface); border: 1px solid var(--border-primary); border-radius: 12px; padding: 24px; margin-top: 24px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 20px; color: var(--text-primary);">🤖 Tool Filter Comparison</h3>
                    <p style="color: var(--text-muted); margin: 0 0 16px 0; font-size: 14px;">How often you search within a specific tool filter</p>
                    ${renderToolComparison(tools.tools)}
                </div>

                <!-- Topic Clusters -->
                <div style="background: var(--bg-surface); border: 1px solid var(--border-primary); border-radius: 12px; padding: 24px; margin-top: 24px;">
                    <h3 style="margin: 0 0 8px 0; font-size: 20px; color: var(--text-primary);">🧭 Topics</h3>
                    <p style="color: var(--text-muted); margin: 0 0 16px 0; font-size: 14px;">Clusters of repeated query themes</p>
                    ${renderTopics(topics.clusters)}
                </div>
            </div>
        `;

        const daysEl = document.getElementById('analyticsDays');
        const refreshEl = document.getElementById('analyticsRefresh');
        const rerender = async () => {
            const selected = daysEl ? Number.parseInt(daysEl.value, 10) : 30;
            resultsDiv.innerHTML = '<div style="text-align: center; padding: 40px; color: var(--text-muted);">Loading analytics...</div>';
            await renderAnalytics(resultsDiv, Number.isFinite(selected) ? selected : 30);
        };

        if (daysEl) {
            daysEl.addEventListener('change', rerender);
        }
        if (refreshEl) {
            refreshEl.addEventListener('click', rerender);
        }
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

function renderTrackingBanner(config) {
    if (!config || config.enabled !== false) {
        return '';
    }

    return `
        <div style="background: rgba(255, 149, 0, 0.12); border: 1px solid rgba(255, 149, 0, 0.35); border-radius: 12px; padding: 16px 18px; margin-bottom: 20px;">
            <div style="font-weight: 700; color: var(--text-primary); margin-bottom: 6px;">Analytics tracking is disabled</div>
            <div style="color: var(--text-muted); font-size: 13px; line-height: 1.4;">
                Searches are not being logged. Enable <code>[analytics].enabled = true</code> in <code>~/.searchat/config/settings.toml</code>
                (or set <code>SEARCHAT_ENABLE_ANALYTICS=1</code>) to start collecting analytics.
            </div>
        </div>
    `;
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

function renderTrends(points) {
    if (!points || points.length === 0) {
        return '<div style="color: var(--text-muted); font-style: italic;">No data available yet.</div>';
    }

    const maxSearches = Math.max(...points.map(p => p.searches || 0), 1);
    const width = 900;
    const height = 120;
    const padding = 10;
    const barWidth = Math.max(2, Math.floor((width - padding * 2) / points.length));
    const bars = points.map((p, idx) => {
        const h = Math.round(((p.searches || 0) / maxSearches) * (height - padding * 2));
        const x = padding + idx * barWidth;
        const y = height - padding - h;
        return `<rect x="${x}" y="${y}" width="${barWidth - 1}" height="${h}" fill="#4a9eff" opacity="0.85"></rect>`;
    }).join('');

    return `
        <div style="overflow-x: auto;">
            <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" role="img" aria-label="Search trend bars">
                ${bars}
            </svg>
        </div>
    `;
}

function renderHeatmap(cells) {
    if (!cells || cells.length === 0) {
        return '<div style="color: var(--text-muted); font-style: italic;">No data available yet.</div>';
    }

    const map = new Map();
    let max = 1;
    for (const c of cells) {
        const key = `${c.dow}-${c.hour}`;
        map.set(key, c.searches);
        if (c.searches > max) max = c.searches;
    }

    const dows = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const hours = Array.from({ length: 24 }, (_, i) => i);

    const header = `
        <div style="display: grid; grid-template-columns: 46px repeat(24, 1fr); gap: 3px; align-items: center; margin-bottom: 8px;">
            <div></div>
            ${hours.map(h => `<div style="font-size: 10px; color: var(--text-muted); text-align: center;">${h}</div>`).join('')}
        </div>
    `;

    const rows = dows.map((label, dow) => {
        const cellsHtml = hours.map((h) => {
            const v = map.get(`${dow}-${h}`) || 0;
            const alpha = v === 0 ? 0.08 : (0.15 + (0.75 * (v / max)));
            return `<div title="${label} ${h}:00 — ${v} searches" style="height: 14px; border-radius: 3px; background: rgba(74, 158, 255, ${alpha.toFixed(3)}); border: 1px solid rgba(255,255,255,0.04);"></div>`;
        }).join('');

        return `
            <div style="display: grid; grid-template-columns: 46px repeat(24, 1fr); gap: 3px; align-items: center; margin-bottom: 3px;">
                <div style="font-size: 11px; color: var(--text-muted);">${label}</div>
                ${cellsHtml}
            </div>
        `;
    }).join('');

    return `<div style="overflow-x: auto;">${header}${rows}</div>`;
}

function renderToolComparison(tools) {
    if (!tools || tools.length === 0) {
        return '<div style="color: var(--text-muted); font-style: italic;">No data available yet.</div>';
    }

    return `
        <div style="display: grid; gap: 10px;">
            ${tools.map((t) => `
                <div style="display: flex; align-items: center; justify-content: space-between; gap: 16px; padding: 12px; background: var(--bg-primary); border: 1px solid var(--border-muted); border-radius: 10px;">
                    <div>
                        <div style="font-weight: 700; color: var(--text-primary); text-transform: uppercase;">${escapeHtml(t.tool_filter)}</div>
                        <div style="font-size: 12px; color: var(--text-muted);">${t.searches} searches · ${t.avg_time_ms}ms avg time · ${t.avg_results} avg results</div>
                    </div>
                    <button onclick="window.location.href='${t.tool_filter === 'all' ? '/' : `/?tool=${encodeURIComponent(t.tool_filter)}`}'" style="background: transparent; color: var(--accent-primary); border: 1px solid var(--border-default); border-radius: 8px; padding: 8px 12px; cursor: pointer; font-size: 12px; font-weight: 600;">
                        Filter
                    </button>
                </div>
            `).join('')}
        </div>
    `;
}

function renderTopics(clusters) {
    if (!clusters || clusters.length === 0) {
        return '<div style="color: var(--text-muted); font-style: italic;">Not enough data to cluster topics yet.</div>';
    }

    return `
        <div style="display: grid; gap: 12px;">
            ${clusters.map((c) => `
                <div style="padding: 14px; background: var(--bg-primary); border: 1px solid var(--border-muted); border-radius: 12px;">
                    <div style="display: flex; justify-content: space-between; gap: 12px; align-items: baseline;">
                        <div style="font-weight: 800; color: var(--text-primary);">${escapeHtml((c.top_terms || []).join(', ') || 'topic')}</div>
                        <div style="color: var(--text-muted); font-size: 12px;">${c.searches} searches</div>
                    </div>
                    <div style="margin-top: 6px; font-family: 'JetBrains Mono', monospace; font-size: 12px; color: var(--text-muted);">
                        ${escapeHtml(c.representative_query || '')}
                    </div>
                    ${c.examples && c.examples.length ? `
                        <div style="margin-top: 8px; color: var(--text-muted); font-size: 12px;">
                            Examples: ${escapeHtml(c.examples.join(' · '))}
                        </div>
                    ` : ''}
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
