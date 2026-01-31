// Dataset (active vs snapshot) selector

const STORAGE_KEY = 'searchatSnapshotName';

export function getSnapshotName() {
    const value = localStorage.getItem(STORAGE_KEY);
    return value ? String(value) : '';
}

export function isSnapshotActive() {
    return Boolean(getSnapshotName());
}

export function setSnapshotName(name) {
    const value = name ? String(name) : '';
    if (!value) {
        localStorage.removeItem(STORAGE_KEY);
        return;
    }
    localStorage.setItem(STORAGE_KEY, value);
}

export function applySnapshotParam(params) {
    const snapshot = getSnapshotName();
    if (!snapshot) return params;
    params.set('snapshot', snapshot);
    return params;
}

function _setBanner(snapshotName) {
    const banner = document.getElementById('datasetBanner');
    if (!banner) return;

    if (!snapshotName) {
        banner.style.display = 'none';
        banner.innerHTML = '';
        return;
    }

    banner.style.display = 'block';
    banner.innerHTML = `
        <div class="dataset-banner-title">Viewing snapshot: <strong>${escapeHtml(snapshotName)}</strong> (read-only)</div>
        <button id="datasetReturnActive" type="button" class="secondary">Return to active</button>
    `;

    const btn = document.getElementById('datasetReturnActive');
    if (btn) {
        btn.addEventListener('click', function () {
            setSnapshotName('');
            window.location.href = '/';
        });
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function _disableWhileSnapshot(snapshotName) {
    const ids = [
        'indexMissingButton',
        'createBackupButton',
        'manageBackupsButton',
        'analyticsButton',
        'dashboardsButton',
        'chatSend',
        'chatStop',
        'semanticHighlights',
        'saveQueryButtonInline',
    ];
    for (const id of ids) {
        const el = document.getElementById(id);
        if (!el) continue;
        el.disabled = true;
        el.title = `Disabled in snapshot mode (${snapshotName})`;
    }

    const chatPanel = document.getElementById('chatPanel');
    if (chatPanel) {
        chatPanel.style.display = 'none';
    }
}

async function _loadSnapshotOptions(select) {
    const response = await fetch('/api/backup/list');
    if (!response.ok) {
        return [];
    }
    const data = await response.json();
    const backups = Array.isArray(data.backups) ? data.backups : [];
    return backups
        .map(function (b) {
            const path = String(b.backup_path || '');
            const name = path.split(/[/\\]/).pop();
            return name;
        })
        .filter(Boolean);
}

export async function initDatasetSelector() {
    const select = document.getElementById('datasetSelect');
    if (!select) return;

    // If snapshots are disabled, hide the selector.
    try {
        const featuresResp = await fetch('/api/status/features');
        if (featuresResp.ok) {
            const features = await featuresResp.json();
            const enabled = Boolean(features && features.snapshots && features.snapshots.enabled);
            if (!enabled) {
                const container = document.getElementById('datasetPanel');
                if (container) container.style.display = 'none';
                return;
            }
        }
    } catch (_e) {
        // If status is unavailable, keep the selector visible.
    }

    const snapshotName = getSnapshotName();

    select.innerHTML = '';
    const activeOpt = document.createElement('option');
    activeOpt.value = '';
    activeOpt.textContent = 'Active index';
    select.appendChild(activeOpt);

    try {
        const names = await _loadSnapshotOptions(select);
        for (const name of names) {
            const opt = document.createElement('option');
            opt.value = name;
            opt.textContent = name;
            select.appendChild(opt);
        }
    } catch (_e) {
        // Ignore backup loading failures.
    }

    select.value = snapshotName;
    _setBanner(snapshotName);
    if (snapshotName) {
        _disableWhileSnapshot(snapshotName);
    }

    select.addEventListener('change', function () {
        setSnapshotName(select.value);
        window.location.href = '/';
    });
}
