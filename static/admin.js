let authToken = localStorage.getItem('admin_token');

const elements = {
    loginScreen: document.getElementById('login-screen'),
    adminPanel: document.getElementById('admin-panel'),
    loginForm: document.getElementById('login-form'),
    passwordInput: document.getElementById('password-input'),
    loginError: document.getElementById('login-error'),
    logoutBtn: document.getElementById('logout-btn'),

    statProductsCache: document.getElementById('stat-products-cache'),
    statChunks: document.getElementById('stat-chunks'),
    statEmbeddings: document.getElementById('stat-embeddings'),
    statNeo4j: document.getElementById('stat-neo4j'),
    statSessions: document.getElementById('stat-sessions'),

    btnCrawl: document.getElementById('btn-crawl'),
    btnCrawlDetails: document.getElementById('btn-crawl-details'),
    btnChunk: document.getElementById('btn-chunk'),
    btnEmbed: document.getElementById('btn-embed'),
    btnFullPipeline: document.getElementById('btn-full-pipeline'),
    pipelineStatus: document.getElementById('pipeline-status'),

    productSearch: document.getElementById('product-search'),
    btnRefreshProducts: document.getElementById('btn-refresh-products'),
    productsTbody: document.getElementById('products-tbody'),

    btnRefreshSessions: document.getElementById('btn-refresh-sessions'),
    sessionsTbody: document.getElementById('sessions-tbody'),
};

async function init() {
    if (authToken) {
        try {
            await fetchWithAuth('/api/admin/stats');
            showAdminPanel();
            loadAllData();
        } catch (e) {
            authToken = null;
            localStorage.removeItem('admin_token');
            showLogin();
        }
    } else {
        showLogin();
    }
    setupEventListeners();
}

function setupEventListeners() {
    elements.loginForm.addEventListener('submit', handleLogin);
    elements.logoutBtn.addEventListener('click', handleLogout);

    elements.btnCrawl.addEventListener('click', () => runPipeline('crawl', { total_pages: 7 }));
    elements.btnCrawlDetails.addEventListener('click', () => runPipeline('crawl_details', {}));
    elements.btnChunk.addEventListener('click', () => runPipeline('chunking', { batch_size: 10 }));
    elements.btnEmbed.addEventListener('click', () => runPipeline('embedding', {}));
    elements.btnFullPipeline.addEventListener('click', () => runPipeline('full_pipeline', { total_pages: 7, batch_size: 10 }));

    elements.btnRefreshProducts.addEventListener('click', loadProducts);
    elements.btnRefreshSessions.addEventListener('click', loadSessions);
    elements.productSearch.addEventListener('input', filterProducts);
}

function showLogin() {
    elements.loginScreen.style.display = 'flex';
    elements.adminPanel.style.display = 'none';
}

function showAdminPanel() {
    elements.loginScreen.style.display = 'none';
    elements.adminPanel.style.display = 'block';
}

async function handleLogin(e) {
    e.preventDefault();
    const password = elements.passwordInput.value;
    elements.loginError.style.display = 'none';

    try {
        const res = await fetch('/api/admin/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password }),
        });

        if (!res.ok) {
            const data = await res.json();
            throw new Error(data.detail || 'Login failed');
        }

        const data = await res.json();
        authToken = data.token;
        localStorage.setItem('admin_token', authToken);
        showAdminPanel();
        loadAllData();
    } catch (error) {
        elements.loginError.textContent = error.message;
        elements.loginError.style.display = 'block';
    }
}

function handleLogout() {
    authToken = null;
    localStorage.removeItem('admin_token');
    showLogin();
    elements.passwordInput.value = '';
}

async function fetchWithAuth(url, options = {}) {
    const res = await fetch(url, {
        ...options,
        headers: {
            ...options.headers,
            'Authorization': `Bearer ${authToken}`,
        },
    });

    if (res.status === 401) {
        handleLogout();
        throw new Error('Unauthorized');
    }

    return res;
}

async function loadAllData() {
    await Promise.all([
        loadStats(),
        loadPipelineStatus(),
        loadProducts(),
        loadSessions(),
    ]);
}

async function loadStats() {
    try {
        const res = await fetchWithAuth('/api/admin/stats');
        const data = await res.json();
        elements.statProductsCache.textContent = data.products_in_cache || 0;
        elements.statChunks.textContent = data.chunks || 0;
        elements.statEmbeddings.textContent = data.embeddings || 0;
        elements.statNeo4j.textContent = data.neo4j_products || 0;
        elements.statSessions.textContent = data.total_sessions || 0;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

async function loadPipelineStatus() {
    try {
        const res = await fetchWithAuth('/api/admin/status');
        const data = await res.json();
        renderPipelineStatus(data);
    } catch (error) {
        console.error('Error loading pipeline status:', error);
    }
}

function renderPipelineStatus(status) {
    let html = '';
    const labels = {
        crawl: 'Crawl',
        crawl_details: 'Crawl Details',
        chunking: 'Chunking',
        embedding: 'Embedding',
        full_pipeline: 'Full Pipeline',
    };

    for (const [key, value] of Object.entries(status)) {
        const label = labels[key] || key;
        let msgClass = '';
        if (value.running) msgClass = 'running';
        else if (value.message?.startsWith('Lỗi')) msgClass = 'error';
        else if (value.message && !value.running) msgClass = 'success';

        html += `
            <div class="status-item">
                <span class="status-label">${label}</span>
                <span class="status-message ${msgClass}">
                    ${value.running ? '⏳ Đang chạy...' : (value.message || 'Chưa chạy')}
                    ${value.last_run ? `<br><small>${value.last_run}</small>` : ''}
                </span>
            </div>
        `;
    }

    elements.pipelineStatus.innerHTML = html || '<p class="loading">Không có dữ liệu</p>';

    for (const [key, value] of Object.entries(status)) {
        const btnMap = {
            crawl: elements.btnCrawl,
            crawl_details: elements.btnCrawlDetails,
            chunking: elements.btnChunk,
            embedding: elements.btnEmbed,
            full_pipeline: elements.btnFullPipeline,
        };
        const btn = btnMap[key];
        if (btn) {
            btn.disabled = value.running;
            btn.classList.toggle('running', value.running);
        }
    }
}

async function runPipeline(step, params) {
    try {
        const res = await fetchWithAuth(`/api/admin/${step === 'crawl_details' ? 'crawl-details' : step === 'full_pipeline' ? 'run-full-pipeline' : step}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(params),
        });

        const data = await res.json();
        if (data.status === 'started') {
            pollPipelineStatus();
        }
    } catch (error) {
        console.error('Error running pipeline:', error);
        alert('Lỗi: ' + error.message);
    }
}

function pollPipelineStatus() {
    const interval = setInterval(async () => {
        await loadPipelineStatus();
        const res = await fetchWithAuth('/api/admin/status');
        const data = await res.json();
        const anyRunning = Object.values(data).some(s => s.running);
        if (!anyRunning) {
            clearInterval(interval);
            loadStats();
        }
    }, 2000);
}

async function loadProducts() {
    try {
        const res = await fetchWithAuth('/api/admin/products');
        const products = await res.json();
        renderProducts(products);
    } catch (error) {
        elements.productsTbody.innerHTML = '<tr><td colspan="4" class="loading">Lỗi tải dữ liệu</td></tr>';
    }
}

function renderProducts(products) {
    if (!products || products.length === 0) {
        elements.productsTbody.innerHTML = '<tr><td colspan="4" class="loading">Không có sản phẩm</td></tr>';
        return;
    }

    elements.productsTbody.innerHTML = products.map(p => `
        <tr data-name="${escapeHtml(p.name)}">
            <td>${escapeHtml(p.name)}</td>
            <td>${p.price || '-'}</td>
            <td>${(p.categories || []).join(', ') || '-'}</td>
            <td>
                <button class="btn btn-danger btn-sm" onclick="deleteProduct('${escapeHtml(p.name)}')">Xóa</button>
            </td>
        </tr>
    `).join('');
}

function filterProducts() {
    const query = elements.productSearch.value.toLowerCase();
    const rows = elements.productsTbody.querySelectorAll('tr');
    rows.forEach(row => {
        const name = row.dataset.name || '';
        row.style.display = name.toLowerCase().includes(query) ? '' : 'none';
    });
}

async function deleteProduct(name) {
    if (!confirm(`Bạn có chắc muốn xóa sản phẩm "${name}"?`)) return;

    try {
        const res = await fetchWithAuth(`/api/admin/products/${encodeURIComponent(name)}`, {
            method: 'DELETE',
        });
        const data = await res.json();
        if (data.status === 'ok') {
            await loadProducts();
            await loadStats();
        }
    } catch (error) {
        alert('Lỗi: ' + error.message);
    }
}

async function loadSessions() {
    try {
        const res = await fetchWithAuth('/api/admin/sessions');
        const sessions = await res.json();
        renderSessions(sessions);
    } catch (error) {
        elements.sessionsTbody.innerHTML = '<tr><td colspan="4" class="loading">Lỗi tải dữ liệu</td></tr>';
    }
}

function renderSessions(sessions) {
    if (!sessions || sessions.length === 0) {
        elements.sessionsTbody.innerHTML = '<tr><td colspan="4" class="loading">Không có session</td></tr>';
        return;
    }

    elements.sessionsTbody.innerHTML = sessions.map(s => `
        <tr>
            <td>${escapeHtml(s.title)}</td>
            <td>${formatDate(s.created_at)}</td>
            <td>${s.message_count}</td>
            <td>
                <button class="btn btn-danger btn-sm" onclick="deleteSession('${s.id}')">Xóa</button>
            </td>
        </tr>
    `).join('');
}

async function deleteSession(id) {
    if (!confirm('Bạn có chắc muốn xóa session này?')) return;

    try {
        const res = await fetchWithAuth(`/api/admin/sessions/${id}`, {
            method: 'DELETE',
        });
        const data = await res.json();
        if (data.status === 'ok') {
            await loadSessions();
            await loadStats();
        }
    } catch (error) {
        alert('Lỗi: ' + error.message);
    }
}

function formatDate(isoString) {
    if (!isoString) return '-';
    const date = new Date(isoString);
    return date.toLocaleString('vi-VN');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

window.deleteProduct = deleteProduct;
window.deleteSession = deleteSession;

document.addEventListener('DOMContentLoaded', init);
