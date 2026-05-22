const state = {
    currentSessionId: null,
    sessions: [],
    messages: [],
    pendingImage: null,
    pendingImageBase64: null,
    isLoading: false,
    sidebarOpen: false
};

const elements = {
    sidebar: document.getElementById('sidebar'),
    sessionList: document.getElementById('session-list'),
    newChatBtn: document.getElementById('new-chat-btn'),
    chatArea: document.getElementById('chat-area'),
    menuToggle: document.getElementById('menu-toggle'),
    sidebarOverlay: document.getElementById('sidebar-overlay'),
    welcomeScreen: document.getElementById('welcome-screen'),
    messagesContainer: document.getElementById('messages-container'),
    messageInput: document.getElementById('message-input'),
    sendBtn: document.getElementById('send-btn'),
    uploadBtn: document.getElementById('upload-btn'),
    imageInput: document.getElementById('image-input'),
    imagePreview: document.getElementById('image-preview'),
    previewImg: document.getElementById('preview-img'),
    removeImageBtn: document.getElementById('remove-image-btn'),
    suggestionBtns: document.querySelectorAll('.suggestion-btn')
};

async function init() {
    await fetchSessions();
    if (state.sessions.length > 0) {
        await loadSession(state.sessions[0].id);
    } else {
        await createNewSession();
    }
    setupEventListeners();
    configureMarked();
}

function configureMarked() {
    marked.setOptions({
        breaks: true,
        gfm: true
    });
}

function setupEventListeners() {
    elements.newChatBtn.addEventListener('click', createNewSession);
    elements.menuToggle.addEventListener('click', toggleSidebar);
    elements.sidebarOverlay.addEventListener('click', closeSidebar);
    elements.sendBtn.addEventListener('click', handleSend);
    elements.uploadBtn.addEventListener('click', () => elements.imageInput.click());
    elements.imageInput.addEventListener('change', handleImageUpload);
    elements.removeImageBtn.addEventListener('click', clearImage);
    elements.messageInput.addEventListener('keydown', handleKeyDown);
    elements.messageInput.addEventListener('input', autoResizeTextarea);
    elements.suggestionBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const prompt = btn.dataset.prompt;
            elements.messageInput.value = prompt;
            handleSend();
        });
    });
}

async function fetchSessions() {
    try {
        const res = await fetch('/api/sessions');
        state.sessions = await res.json();
        renderSessionList();
    } catch (error) {
        console.error('Error fetching sessions:', error);
    }
}

function renderSessionList() {
    elements.sessionList.innerHTML = '';
    state.sessions.forEach(session => {
        const item = document.createElement('div');
        item.className = `session-item ${session.id === state.currentSessionId ? 'active' : ''}`;
        item.innerHTML = `
            <span class="session-title">${escapeHtml(session.title)}</span>
            <button class="delete-session-btn" data-id="${session.id}" title="Xóa">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
            </button>
        `;
        item.querySelector('.session-title').addEventListener('click', () => loadSession(session.id));
        item.querySelector('.delete-session-btn').addEventListener('click', (e) => {
            e.stopPropagation();
            deleteSession(session.id);
        });
        elements.sessionList.appendChild(item);
    });
}

async function createNewSession() {
    try {
        const res = await fetch('/api/sessions', { method: 'POST' });
        const data = await res.json();
        state.currentSessionId = data.session_id;
        state.messages = [];
        renderMessages();
        await fetchSessions();
        closeSidebar();
    } catch (error) {
        console.error('Error creating session:', error);
    }
}

async function loadSession(sessionId) {
    try {
        state.currentSessionId = sessionId;
        const res = await fetch(`/api/sessions/${sessionId}`);
        state.messages = await res.json();
        renderSessionList();
        renderMessages();
        closeSidebar();
    } catch (error) {
        console.error('Error loading session:', error);
    }
}

async function deleteSession(sessionId) {
    if (!confirm('Bạn có chắc muốn xóa cuộc hội thoại này?')) return;
    try {
        await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' });
        await fetchSessions();
        if (state.currentSessionId === sessionId) {
            if (state.sessions.length > 0) {
                await loadSession(state.sessions[0].id);
            } else {
                await createNewSession();
            }
        }
    } catch (error) {
        console.error('Error deleting session:', error);
    }
}

function renderMessages() {
    elements.messagesContainer.innerHTML = '';
    const hasMessages = state.messages.length > 0;
    elements.welcomeScreen.style.display = hasMessages ? 'none' : 'flex';
    elements.messagesContainer.classList.toggle('has-messages', hasMessages);

    state.messages.forEach(msg => {
        const messageEl = createMessageElement(msg);
        elements.messagesContainer.appendChild(messageEl);
    });

    scrollToBottom();
}

function createMessageElement(msg) {
    const div = document.createElement('div');
    div.className = `message ${msg.role}`;

    const avatarDiv = document.createElement('div');
    avatarDiv.className = `message-avatar ${msg.role}`;
    const avatarSrc = msg.role === 'user' ? '/static/img/user_ava.webp' : '/static/img/bot_ava.webp';
    const avatarFallback = msg.role === 'user' ? '👤' : '🤖';
    avatarDiv.innerHTML = `<img src="${avatarSrc}" alt="${msg.role}" onerror="this.parentElement.innerHTML='${avatarFallback}'">`;
    div.appendChild(avatarDiv);

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';

    if (msg.role === 'user') {
        if (msg.image) {
            const img = document.createElement('img');
            img.className = 'message-image';
            img.src = msg.image;
            contentDiv.appendChild(img);
        }
        const textSpan = document.createElement('span');
        textSpan.textContent = msg.content;
        contentDiv.appendChild(textSpan);
    } else {
        contentDiv.innerHTML = marked.parse(msg.content);
    }

    div.appendChild(contentDiv);

    if (msg.role === 'assistant' && msg.results && msg.results.length > 0) {
        const productSection = document.createElement('div');
        productSection.className = 'product-section';
        productSection.innerHTML = '<h4>Sản phẩm gợi ý:</h4>';

        const productGrid = document.createElement('div');
        productGrid.className = 'product-grid';

        msg.results.forEach(product => {
            productGrid.appendChild(createProductCard(product));
        });

        productSection.appendChild(productGrid);
        div.appendChild(productSection);
    }

    return div;
}

function createProductCard(product) {
    const card = document.createElement('div');
    card.className = 'product-card';

    let html = '';
    if (product.image) {
        html += `<img src="${escapeHtml(product.image)}" alt="${escapeHtml(product.name)}" onerror="this.style.display='none'">`;
    }
    html += `<div class="product-name">${escapeHtml(product.name)}</div>`;

    if (product.original_price && product.original_price !== product.price) {
        html += `<div class="product-original">${escapeHtml(product.original_price)}</div>`;
        html += `<div class="product-price">${escapeHtml(product.price)}</div>`;
        if (product.discount) {
            html += `<div class="product-discount">${escapeHtml(product.discount)}</div>`;
        }
    } else {
        html += `<div class="product-price">${escapeHtml(product.price)}</div>`;
    }

    if (product.categories && product.categories.length > 0) {
        html += `<div class="product-categories">${escapeHtml(product.categories.join(' | '))}</div>`;
    }

    html += `<a href="${escapeHtml(product.url)}" target="_blank" class="product-link">Xem sản phẩm →</a>`;

    card.innerHTML = html;
    return card;
}

function createLoadingMessage() {
    const div = document.createElement('div');
    div.className = 'message assistant';
    div.id = 'loading-message';
    div.innerHTML = `
        <div class="message-content">
            <div class="loading">
                <span></span>
                <span></span>
                <span></span>
            </div>
        </div>
    `;
    return div;
}

async function handleSend() {
    const message = elements.messageInput.value.trim();
    if (!message && !state.pendingImage) return;
    if (state.isLoading) return;

    state.isLoading = true;
    elements.sendBtn.disabled = true;

    const userMessage = {
        role: 'user',
        content: message || 'Phân tích ảnh',
        image: state.pendingImageBase64
    };

    state.messages.push(userMessage);
    renderMessages();

    elements.messageInput.value = '';
    autoResizeTextarea();
    clearImage();

    const loadingEl = createLoadingMessage();
    elements.messagesContainer.appendChild(loadingEl);
    scrollToBottom();

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: message,
                image: state.pendingImageBase64,
                session_id: state.currentSessionId
            })
        });

        const data = await res.json();

        const loadingMessage = document.getElementById('loading-message');
        if (loadingMessage) loadingMessage.remove();

        const assistantMessage = {
            role: 'assistant',
            content: data.answer,
            results: data.results || []
        };

        state.messages.push(assistantMessage);
        renderMessages();

        if (data.session_id) {
            state.currentSessionId = data.session_id;
            await fetchSessions();
        }
    } catch (error) {
        console.error('Error sending message:', error);
        const loadingMessage = document.getElementById('loading-message');
        if (loadingMessage) loadingMessage.remove();

        const errorMessage = {
            role: 'assistant',
            content: 'Có lỗi xảy ra. Vui lòng thử lại.',
            results: []
        };
        state.messages.push(errorMessage);
        renderMessages();
    } finally {
        state.isLoading = false;
        elements.sendBtn.disabled = false;
        elements.messageInput.focus();
    }
}

function handleImageUpload(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = function(event) {
        state.pendingImage = file;
        state.pendingImageBase64 = event.target.result;
        elements.previewImg.src = event.target.result;
        elements.imagePreview.style.display = 'inline-block';
        updateSendButton();
    };
    reader.readAsDataURL(file);
}

function clearImage() {
    state.pendingImage = null;
    state.pendingImageBase64 = null;
    elements.imagePreview.style.display = 'none';
    elements.imageInput.value = '';
    updateSendButton();
}

function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
    }
}

function autoResizeTextarea() {
    elements.messageInput.style.height = 'auto';
    elements.messageInput.style.height = Math.min(elements.messageInput.scrollHeight, 200) + 'px';
    updateSendButton();
}

function updateSendButton() {
    const hasText = elements.messageInput.value.trim().length > 0;
    const hasImage = state.pendingImage !== null;
    elements.sendBtn.disabled = !hasText && !hasImage;
}

function scrollToBottom() {
    elements.messagesContainer.scrollTop = elements.messagesContainer.scrollHeight;
}

function toggleSidebar() {
    state.sidebarOpen = !state.sidebarOpen;
    elements.sidebar.classList.toggle('open', state.sidebarOpen);
    elements.sidebarOverlay.classList.toggle('open', state.sidebarOpen);
}

function closeSidebar() {
    state.sidebarOpen = false;
    elements.sidebar.classList.remove('open');
    elements.sidebarOverlay.classList.remove('open');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

document.addEventListener('DOMContentLoaded', init);
