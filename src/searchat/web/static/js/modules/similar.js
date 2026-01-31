// Similar conversations functionality

import { applySnapshotParam } from './dataset.js';

/**
 * Load and display similar conversations
 */
export async function loadSimilarConversations(conversationId, container) {
    container.innerHTML = '<div class="loading">Finding similar conversations...</div>';

    try {
        const params = applySnapshotParam(new URLSearchParams({ limit: '5' }));
        const response = await fetch(`/api/conversation/${conversationId}/similar?${params.toString()}`);
        if (!response.ok) {
            const payload = await response.json().catch(() => null);
            const msg = payload && payload.detail ? payload.detail : 'Failed to load similar conversations';
            container.innerHTML = `<div style="color: var(--text-muted); padding: 20px; text-align: center;">${msg}</div>`;
            return;
        }

        const data = await response.json();

        if (!data.similar_conversations || data.similar_conversations.length === 0) {
            container.innerHTML = `
                <div style="
                    text-align: center;
                    padding: 40px 20px;
                    color: var(--text-muted);
                ">
                    <div style="font-size: 48px; margin-bottom: 16px;">🔍</div>
                    <div style="font-size: 16px; margin-bottom: 8px;">No similar conversations found</div>
                    <div style="font-size: 13px;">This conversation appears to be unique</div>
                </div>
            `;
            return;
        }

        let html = `
            <div style="
                margin-bottom: 20px;
                padding: 12px 16px;
                background: var(--bg-surface);
                border-radius: 8px;
                border: 1px solid var(--border-default);
            ">
                <div style="font-size: 16px; font-weight: 500; color: var(--text-primary); margin-bottom: 4px;">
                    🔗 ${data.similar_count} Related Conversation${data.similar_count !== 1 ? 's' : ''}
                </div>
                <div style="font-size: 13px; color: var(--text-muted);">
                    Found using semantic similarity analysis
                </div>
            </div>
        `;

        data.similar_conversations.forEach((conv, index) => {
            const toolLabel = conv.tool === 'opencode' ? 'OpenCode' : (conv.tool === 'vibe' ? 'Vibe' : 'Claude Code');
            const similarityPercent = Math.round(conv.similarity_score * 100);
            const createdDate = new Date(conv.created_at).toLocaleDateString();

            // Color code similarity score
            let scoreColor = 'var(--success)';
            if (similarityPercent < 70) scoreColor = 'var(--warning)';
            if (similarityPercent < 50) scoreColor = 'var(--text-muted)';

            html += `
                <div class="similar-conversation-item" data-conversation-id="${conv.conversation_id}" style="
                    background: var(--bg-elevated);
                    border: 1px solid var(--border-default);
                    border-radius: 8px;
                    padding: 14px 16px;
                    margin-bottom: 12px;
                    cursor: pointer;
                    transition: all 0.2s;
                " onmouseover="this.style.borderColor='var(--accent-primary)'; this.style.transform='translateY(-2px)'" onmouseout="this.style.borderColor='var(--border-default)'; this.style.transform='translateY(0)'">
                    <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 8px;">
                        <div style="flex: 1;">
                            <div style="font-size: 15px; font-weight: 500; color: var(--text-primary); margin-bottom: 4px;">
                                ${conv.title}
                            </div>
                            <div style="font-size: 12px; color: var(--text-muted);">
                                <span class="tool-badge ${conv.tool}" style="font-size: 11px; padding: 2px 6px;">${toolLabel}</span>
                                <span style="margin-left: 8px;">${conv.project_id}</span>
                                <span style="margin-left: 8px;">•</span>
                                <span style="margin-left: 8px;">${conv.message_count} messages</span>
                                <span style="margin-left: 8px;">•</span>
                                <span style="margin-left: 8px;">${createdDate}</span>
                            </div>
                        </div>
                        <div style="
                            background: ${scoreColor};
                            color: white;
                            padding: 4px 10px;
                            border-radius: 4px;
                            font-size: 12px;
                            font-weight: 600;
                            white-space: nowrap;
                            margin-left: 12px;
                        ">
                            ${similarityPercent}% match
                        </div>
                    </div>
                </div>
            `;
        });

        container.innerHTML = html;

        // Add click handlers to navigate to similar conversations
        container.querySelectorAll('.similar-conversation-item').forEach(item => {
            item.addEventListener('click', () => {
                const convId = item.dataset.conversationId;
                window.location.href = `/conversation/${convId}`;
            });
        });

    } catch (error) {
        container.innerHTML = `<div style="color: #f44336;">Error: ${error.message}</div>`;
    }
}
