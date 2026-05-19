// ===== AI 对话系统 - 前端交互 =====

// ---- 默认角色设定 ----
var DEFAULT_CHARACTER = {
    name: '小言',
    personality: '温和友善、知识渊博、乐于助人',
    appearance: '一位身着素雅长袍的年轻学者，目光清澈而沉静',
    background: '在图书馆中沉睡了千年的书灵，通晓古今，擅长用浅显的语言解释复杂的问题'
};

// ---- API 封装 ----
var API = {
    chat: function (sessionId, message, character) {
        var body = { session_id: sessionId, message: message };
        if (!sessionId && character) {
            body.character = character;
        }
        return fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        }).then(function (r) { return r.json(); });
    },
    getSessions: function () {
        return fetch('/api/sessions').then(function (r) { return r.json(); });
    },
    getSession: function (sessionId) {
        return fetch('/api/sessions/' + sessionId).then(function (r) { return r.json(); });
    },
    deleteSession: function (sessionId) {
        return fetch('/api/sessions/' + sessionId, { method: 'DELETE' }).then(function (r) { return r.json(); });
    },
    updateCharacter: function (sessionId, character) {
        return fetch('/api/sessions/' + sessionId + '/character', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(character)
        }).then(function (r) { return r.json(); });
    }
};

// ---- 状态 ----
var state = {
    currentSessionId: '',       // 空 = 新对话
    currentTitle: '',
    currentCharName: '',        // 用于头像显示
    originalCharacter: null,    // 当前会话加载时的原始角色设定（用于变更检测）
    characterConfirmed: false,  // 本次会话是否已确认过角色修改
    pendingCharacter: null      // 待确认的角色修改值
};

// ---- DOM 引用 ----
function $(sel) { return document.querySelector(sel); }

var dom = {
    gameList: $('#gameList'),
    chatMessages: $('#chatMessages'),
    welcomeScreen: $('#welcomeScreen'),
    messageInput: $('#messageInput'),
    btnSend: $('#btnSend'),
    sessionLabel: $('#sessionLabel'),
    chatTitle: $('#chatTitle'),
    btnToggleSidebar: $('#btnToggleSidebar'),
    btnToggleRight: $('#btnToggleRight'),
    sidebarLeft: $('#sidebarLeft'),
    sidebarRight: $('#sidebarRight'),
    charName: $('#charName'),
    charPersonality: $('#charPersonality'),
    charAppearance: $('#charAppearance'),
    charBackground: $('#charBackground'),
    modalOverlay: $('#modalOverlay'),
    modalCancel: $('#modalCancel'),
    modalConfirm: $('#modalConfirm'),
    btnNewChat: $('#btnNewChat')
};

// ---- 工具 ----
function toast(msg, type) {
    var el = document.createElement('div');
    el.className = 'toast ' + (type || '');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(function () { el.remove(); }, 2500);
}

function escapeHtml(str) {
    var d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
}

// ---- 角色表单操作 ----
function getCharacterConfig() {
    return {
        name: dom.charName.value.trim(),
        personality: dom.charPersonality.value.trim(),
        appearance: dom.charAppearance.value.trim(),
        background: dom.charBackground.value.trim()
    };
}

function setCharacterForm(ch) {
    dom.charName.value = ch.name || '';
    dom.charPersonality.value = ch.personality || '';
    dom.charAppearance.value = ch.appearance || '';
    dom.charBackground.value = ch.background || '';
}

function cloneCharacter(ch) {
    return {
        name: ch.name,
        personality: ch.personality,
        appearance: ch.appearance,
        background: ch.background
    };
}

function isCharacterDifferent(a, b) {
    return (a.name !== b.name ||
            a.personality !== b.personality ||
            a.appearance !== b.appearance ||
            a.background !== b.background);
}

function snapshotOriginalCharacter() {
    state.originalCharacter = cloneCharacter(getCharacterConfig());
    state.characterConfirmed = false;
}

// ---- Modal ----
function showModal() {
    dom.modalOverlay.classList.add('show');
}

function hideModal() {
    dom.modalOverlay.classList.remove('show');
    state.pendingCharacter = null;
}

// ---- 角色修改检测 ----
function onCharacterFieldChange() {
    // 非活跃会话（新对话）无需警告
    if (!state.currentSessionId) return;
    // 已经确认过本次修改，无需重复警告
    if (state.characterConfirmed) return;

    var current = getCharacterConfig();
    if (isCharacterDifferent(current, state.originalCharacter)) {
        // 暂存当前值，弹出确认
        state.pendingCharacter = cloneCharacter(current);
        showModal();
    }
}

// ---- 消息渲染 ----
function createMessageEl(text, role, charName) {
    var type = role === 'user' ? 'user' : 'bot';
    var avatarText;
    if (role === 'user') {
        avatarText = '我';
    } else {
        avatarText = charName || 'AI';
        if (avatarText.length > 2) avatarText = avatarText.substring(0, 2);
    }

    var div = document.createElement('div');
    div.className = 'message ' + type;
    div.innerHTML =
        '<div class="message-avatar">' + escapeHtml(avatarText) + '</div>' +
        '<div class="message-content">' +
            '<div class="message-bubble">' + escapeHtml(text) + '</div>' +
            '<div class="message-actions">' +
                '<button class="action-btn copy-btn">复制</button>' +
            '</div>' +
        '</div>';

    div.querySelector('.copy-btn').addEventListener('click', function () {
        navigator.clipboard.writeText(text).then(function () {
            toast('已复制', 'success');
        });
    });
    return div;
}

function createTypingEl(charName) {
    var name = charName || 'AI';
    if (name.length > 2) name = name.substring(0, 2);
    var div = document.createElement('div');
    div.className = 'message bot';
    div.id = 'typingIndicator';
    div.innerHTML =
        '<div class="message-avatar">' + escapeHtml(name) + '</div>' +
        '<div class="message-content">' +
            '<div class="message-bubble">' +
                '<div class="typing-dots"><span></span><span></span><span></span></div>' +
            '</div>' +
        '</div>';
    return div;
}

function removeTyping() {
    var el = document.getElementById('typingIndicator');
    if (el) el.remove();
}

function scrollToBottom() {
    dom.chatMessages.scrollTop = dom.chatMessages.scrollHeight;
}

// ---- 加载历史消息 ----
function loadMessages(sessionId) {
    dom.chatMessages.querySelectorAll('.message').forEach(function (m) { m.remove(); });
    dom.welcomeScreen.style.display = 'none';

    API.getSession(sessionId).then(function (res) {
        if (res.code !== 200) {
            toast('加载失败', 'error');
            return;
        }
        var data = res.data;
        var charConfig = data.character || {};
        state.currentCharName = charConfig.name || '';

        // 将该会话的角色设定加载到表单
        setCharacterForm(charConfig);
        snapshotOriginalCharacter();

        var messages = data.messages || [];
        messages.forEach(function (m) {
            dom.chatMessages.appendChild(createMessageEl(m.content, m.role, state.currentCharName));
        });
        scrollToBottom();
    });
}

// ---- 发送消息 ----
function sendMessage() {
    var text = dom.messageInput.value.trim();
    if (!text) return;

    var character = getCharacterConfig();
    var charName = character.name;

    dom.welcomeScreen.style.display = 'none';
    dom.chatMessages.appendChild(createMessageEl(text, 'user'));
    dom.messageInput.value = '';
    scrollToBottom();

    dom.chatMessages.appendChild(createTypingEl(charName));
    scrollToBottom();

    setInputEnabled(false);

    API.chat(state.currentSessionId, text, character).then(function (res) {
        removeTyping();
        setInputEnabled(true);
        dom.messageInput.focus();

        if (res.code !== 200) {
            toast('请求失败: ' + res.message, 'error');
            return;
        }

        var reply = res.data.reply;

        // 新对话：后端返回了 session_id 和 title
        if (!state.currentSessionId && res.data.session_id) {
            state.currentSessionId = res.data.session_id;
            state.currentTitle = res.data.title;
            state.currentCharName = charName;
            dom.sessionLabel.textContent = '会话: ' + res.data.title;
            dom.chatTitle.textContent = res.data.title;
            // 新会话建立，锁定当前角色为原始值
            snapshotOriginalCharacter();
        }

        dom.chatMessages.appendChild(createMessageEl(reply, 'assistant', state.currentCharName));
        scrollToBottom();
        refreshSessionList();
    }).catch(function (err) {
        removeTyping();
        setInputEnabled(true);
        toast('网络错误', 'error');
        console.error(err);
    });
}

function setInputEnabled(enabled) {
    dom.messageInput.disabled = !enabled;
    dom.btnSend.disabled = !enabled;
    dom.messageInput.placeholder = enabled ? '输入消息…' : 'AI 正在回复…';
}

// ---- 会话列表 ----
function refreshSessionList() {
    API.getSessions().then(function (res) {
        if (res.code !== 200) return;
        state.sessions = res.data || [];

        dom.gameList.innerHTML = '';
        state.sessions.forEach(function (s) {
            var li = document.createElement('li');
            li.className = 'game-item' + (s.id === state.currentSessionId ? ' active' : '');
            li.innerHTML =
                '<span class="session-name">' + escapeHtml(s.title) + '</span>' +
                '<button class="delete-btn" title="删除">&times;</button>';

            li.addEventListener('click', function (e) {
                if (e.target.classList.contains('delete-btn')) return;
                selectSession(s.id, s.title);
            });

            li.querySelector('.delete-btn').addEventListener('click', function (e) {
                e.stopPropagation();
                API.deleteSession(s.id).then(function () {
                    if (s.id === state.currentSessionId) {
                        resetToWelcome();
                    }
                    refreshSessionList();
                    toast('已删除', 'success');
                });
            });

            dom.gameList.appendChild(li);
        });
    });
}

function selectSession(sessionId, title) {
    state.currentSessionId = sessionId;
    state.currentTitle = title;
    dom.sessionLabel.textContent = '会话: ' + title;
    dom.chatTitle.textContent = title;
    setInputEnabled(true);
    loadMessages(sessionId);
    refreshSessionList();
    dom.sidebarLeft.classList.remove('open');
}

function resetToWelcome() {
    state.currentSessionId = '';
    state.currentTitle = '';
    state.currentCharName = '';
    dom.chatMessages.querySelectorAll('.message').forEach(function (m) { m.remove(); });
    dom.welcomeScreen.style.display = '';
    dom.sessionLabel.textContent = '';
    dom.chatTitle.textContent = 'AI 对话';
    // 恢复默认角色设定
    setCharacterForm(DEFAULT_CHARACTER);
    snapshotOriginalCharacter();
    setInputEnabled(true);
    dom.messageInput.value = '';
    refreshSessionList();
}

// ---- Modal 事件 ----

// 确认修改
dom.modalConfirm.addEventListener('click', function () {
    var ch = state.pendingCharacter;
    if (!ch) { hideModal(); return; }

    // 保存到后端
    API.updateCharacter(state.currentSessionId, ch).then(function (res) {
        if (res.code === 200) {
            setCharacterForm(ch);
            state.originalCharacter = cloneCharacter(ch);
            state.characterConfirmed = true;
            state.currentCharName = ch.name || '';
            toast('角色设定已更新', 'success');
        } else {
            // 失败则还原
            setCharacterForm(state.originalCharacter);
            toast('更新失败', 'error');
        }
        hideModal();
    }).catch(function () {
        setCharacterForm(state.originalCharacter);
        toast('网络错误', 'error');
        hideModal();
    });
});

// 取消修改
dom.modalCancel.addEventListener('click', function () {
    // 还原表单
    setCharacterForm(state.originalCharacter);
    hideModal();
});

// 点击遮罩关闭
dom.modalOverlay.addEventListener('click', function (e) {
    if (e.target === dom.modalOverlay) {
        setCharacterForm(state.originalCharacter);
        hideModal();
    }
});

// ---- 事件绑定 ----
dom.btnSend.addEventListener('click', sendMessage);
dom.messageInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

dom.btnToggleSidebar.addEventListener('click', function () {
    dom.sidebarLeft.classList.toggle('open');
});

dom.btnToggleRight.addEventListener('click', function () {
    dom.sidebarRight.classList.toggle('open');
});

// 新对话按钮
dom.btnNewChat.addEventListener('click', function () {
    resetToWelcome();
    dom.messageInput.focus();
    dom.sidebarLeft.classList.remove('open');
});

// 点击消息区关闭移动端面板
dom.chatMessages.addEventListener('click', function () {
    dom.sidebarLeft.classList.remove('open');
    dom.sidebarRight.classList.remove('open');
});

// 监听角色表单变更
var charFields = [dom.charName, dom.charPersonality, dom.charAppearance, dom.charBackground];
charFields.forEach(function (field) {
    field.addEventListener('input', onCharacterFieldChange);
});

// ---- 初始化 ----
setCharacterForm(DEFAULT_CHARACTER);
snapshotOriginalCharacter();
setInputEnabled(true);
refreshSessionList();
