/**
 * A2A Client for Brand Concierge Test UI
 *
 * Handles JSON-RPC 2.0 communication with the A2A endpoint.
 */

class A2AClient {
    constructor() {
        this.baseUrl = window.location.origin;
        this.token = null;
        this.contextId = null;
        this.requestId = 0;
    }

    /**
     * Set the IMS Bearer token for authentication.
     */
    setToken(token) {
        this.token = token;
        sessionStorage.setItem('ims_token', token);
    }

    /**
     * Get token from storage.
     */
    loadToken() {
        this.token = sessionStorage.getItem('ims_token');
        return this.token;
    }

    /**
     * Clear the token.
     */
    clearToken() {
        this.token = null;
        sessionStorage.removeItem('ims_token');
    }

    /**
     * Set context ID for conversation continuity.
     */
    setContextId(contextId) {
        this.contextId = contextId;
        sessionStorage.setItem('context_id', contextId);
    }

    /**
     * Load context ID from storage.
     */
    loadContextId() {
        this.contextId = sessionStorage.getItem('context_id');
        return this.contextId;
    }

    /**
     * Clear context ID.
     */
    clearContextId() {
        this.contextId = null;
        sessionStorage.removeItem('context_id');
    }

    /**
     * Make a JSON-RPC 2.0 request to the A2A endpoint.
     */
    async rpcRequest(method, params = {}) {
        if (!this.token) {
            throw new AuthenticationError('No authentication token set');
        }

        this.requestId++;

        const response = await fetch(`${this.baseUrl}/a2a`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${this.token}`,
                'X-Adobe-Surface': 'web',
            },
            body: JSON.stringify({
                jsonrpc: '2.0',
                id: String(this.requestId),
                method: method,
                params: params,
            }),
        });

        // Handle HTTP-level auth errors
        if (response.status === 401) {
            const data = await response.json();
            throw new AuthenticationError(data.error || 'Authentication failed');
        }

        const data = await response.json();

        // Handle JSON-RPC errors
        if (data.error) {
            throw new RPCError(data.error.code, data.error.message);
        }

        return data.result;
    }

    /**
     * Fetch the agent card (no auth required).
     */
    async getAgentCard() {
        const response = await fetch(`${this.baseUrl}/.well-known/agent.json`);
        if (!response.ok) {
            throw new Error('Failed to fetch agent card');
        }
        return response.json();
    }

    /**
     * Send a message to the agent.
     */
    async sendMessage(text) {
        const params = {
            message: {
                role: 'user',
                parts: [{ kind: 'text', text: text }],
            },
        };

        // Include contextId for conversation continuity
        if (this.contextId) {
            params.configuration = { contextId: this.contextId };
        }

        const task = await this.rpcRequest('message/send', params);

        // Store contextId from response for future messages
        if (task.contextId) {
            this.setContextId(task.contextId);
        }

        return task;
    }

    /**
     * Get a task by ID.
     */
    async getTask(taskId) {
        return this.rpcRequest('tasks/get', { taskId });
    }

    /**
     * List tasks, optionally filtered by context.
     */
    async listTasks(contextId = null) {
        const params = contextId ? { contextId } : {};
        return this.rpcRequest('tasks/list', params);
    }

    /**
     * Cancel a task.
     */
    async cancelTask(taskId) {
        return this.rpcRequest('tasks/cancel', { taskId });
    }
}

/**
 * Custom error classes for better error handling.
 */
class AuthenticationError extends Error {
    constructor(message) {
        super(message);
        this.name = 'AuthenticationError';
    }
}

class RPCError extends Error {
    constructor(code, message) {
        super(message);
        this.name = 'RPCError';
        this.code = code;
    }
}

/**
 * Chat UI Controller
 */
class ChatUI {
    constructor() {
        this.client = new A2AClient();
        this.isConnected = false;

        // DOM Elements
        this.elements = {
            tokenInput: document.getElementById('ims-token'),
            connectBtn: document.getElementById('connect-btn'),
            clearTokenBtn: document.getElementById('clear-token-btn'),
            authPanel: document.getElementById('auth-panel'),
            authError: document.getElementById('auth-error'),
            chatContainer: document.getElementById('chat-container'),
            messages: document.getElementById('messages'),
            messageForm: document.getElementById('message-form'),
            messageInput: document.getElementById('message-input'),
            sendBtn: document.getElementById('send-btn'),
            contextIdDisplay: document.getElementById('context-id'),
            newConversationBtn: document.getElementById('new-conversation-btn'),
            connectionStatus: document.getElementById('connection-status'),
            taskPanel: document.getElementById('task-panel'),
            taskList: document.getElementById('task-list'),
        };

        this.init();
    }

    init() {
        // Try to restore session from storage
        const token = this.client.loadToken();
        this.client.loadContextId();

        if (token) {
            this.elements.tokenInput.value = token;
            this.validateAndConnect();
        }

        // Event listeners
        this.elements.connectBtn.addEventListener('click', () => this.connect());
        this.elements.clearTokenBtn.addEventListener('click', () => this.clearSession());
        this.elements.messageForm.addEventListener('submit', (e) => this.handleSendMessage(e));
        this.elements.newConversationBtn.addEventListener('click', () => this.startNewConversation());

        // Allow pressing Enter to connect when in token input
        this.elements.tokenInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.connect();
            }
        });
    }

    async connect() {
        const token = this.elements.tokenInput.value.trim();
        if (!token) {
            this.showAuthError('Please enter an IMS token');
            return;
        }

        this.client.setToken(token);
        await this.validateAndConnect();
    }

    async validateAndConnect() {
        this.setLoading(true);
        this.hideAuthError();

        try {
            // Test the connection by listing tasks (requires auth)
            await this.client.listTasks();

            this.isConnected = true;
            this.updateConnectionStatus(true);
            this.showChatInterface();

            // Update context display
            this.updateContextDisplay();

            // Load conversation history if we have a contextId
            if (this.client.contextId) {
                await this.loadConversationHistory();
            }
        } catch (error) {
            this.isConnected = false;
            this.updateConnectionStatus(false);

            if (error instanceof AuthenticationError) {
                this.showAuthError(`Authentication failed: ${error.message}`);
                this.client.clearToken();
                this.elements.tokenInput.value = '';
            } else {
                this.showAuthError(`Connection error: ${error.message}`);
            }
        } finally {
            this.setLoading(false);
        }
    }

    async handleSendMessage(event) {
        event.preventDefault();

        const text = this.elements.messageInput.value.trim();
        if (!text || !this.isConnected) return;

        // Clear input and disable send
        this.elements.messageInput.value = '';
        this.setSending(true);

        // Add user message to UI immediately
        this.addMessage('user', text);

        try {
            const task = await this.client.sendMessage(text);

            // Update context display
            this.updateContextDisplay();

            // Extract and display agent response
            const agentMessages = task.messages.filter(m => m.role === 'agent');
            if (agentMessages.length > 0) {
                const lastResponse = agentMessages[agentMessages.length - 1];
                const responseText = this.extractTextFromMessage(lastResponse);
                this.addMessage('agent', responseText, task);
            }

            // Handle task state
            if (task.status.state === 'failed') {
                this.addSystemMessage(`Task failed: ${task.status.error?.message || 'Unknown error'}`);
            }

            // Refresh task list
            await this.refreshTaskList();

        } catch (error) {
            this.addSystemMessage(`Error: ${error.message}`);

            if (error instanceof AuthenticationError) {
                this.disconnect();
            }
        } finally {
            this.setSending(false);
            this.elements.messageInput.focus();
        }
    }

    extractTextFromMessage(message) {
        const parts = message.parts || [];
        return parts
            .filter(p => p.kind === 'text')
            .map(p => p.text)
            .join(' ');
    }

    addMessage(role, text, task = null) {
        // Remove welcome message if present
        const welcomeMsg = this.elements.messages.querySelector('.welcome-message');
        if (welcomeMsg) {
            welcomeMsg.remove();
        }

        const messageDiv = document.createElement('div');
        messageDiv.className = `flex ${role === 'user' ? 'justify-end' : 'justify-start'} message-bubble`;

        const bubble = document.createElement('div');
        bubble.className = role === 'user'
            ? 'max-w-[70%] bg-blue-600 text-white rounded-lg px-4 py-2'
            : 'max-w-[70%] bg-gray-200 text-gray-800 rounded-lg px-4 py-2';

        bubble.innerHTML = this.formatMessage(text);

        // Add task metadata if available
        if (task && role === 'agent') {
            const meta = document.createElement('div');
            meta.className = 'text-xs opacity-70 mt-1';
            meta.textContent = `Task: ${task.id.substring(0, 8)}... | Status: ${task.status.state}`;
            bubble.appendChild(meta);
        }

        messageDiv.appendChild(bubble);
        this.elements.messages.appendChild(messageDiv);
        this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
    }

    addSystemMessage(text) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'flex justify-center message-bubble';

        const bubble = document.createElement('div');
        bubble.className = 'bg-yellow-100 text-yellow-800 rounded-lg px-4 py-2 text-sm';
        bubble.textContent = text;

        messageDiv.appendChild(bubble);
        this.elements.messages.appendChild(messageDiv);
        this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
    }

    formatMessage(text) {
        // Basic escaping and formatting
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/\n/g, '<br>');
    }

    async loadConversationHistory() {
        try {
            const tasks = await this.client.listTasks(this.client.contextId);

            if (tasks.length === 0) return;

            // Clear current messages
            this.elements.messages.innerHTML = '';

            // Render all messages from tasks in order
            for (const task of tasks) {
                for (const message of task.messages) {
                    const text = this.extractTextFromMessage(message);
                    if (text) {
                        this.addMessage(message.role, text, message.role === 'agent' ? task : null);
                    }
                }
            }

            await this.refreshTaskList();
        } catch (error) {
            console.error('Failed to load conversation history:', error);
        }
    }

    async refreshTaskList() {
        try {
            const tasks = await this.client.listTasks(this.client.contextId);
            this.renderTaskList(tasks);
            this.elements.taskPanel.classList.remove('hidden');
        } catch (error) {
            console.error('Failed to refresh task list:', error);
        }
    }

    renderTaskList(tasks) {
        this.elements.taskList.innerHTML = '';

        if (tasks.length === 0) {
            this.elements.taskList.innerHTML = '<p class="text-gray-500 text-sm">No tasks yet.</p>';
            return;
        }

        // Show last 10, newest first
        for (const task of tasks.slice(-10).reverse()) {
            const taskDiv = document.createElement('div');
            taskDiv.className = 'p-3 bg-gray-50 rounded-lg text-sm';

            const statusColor = {
                'completed': 'text-green-600',
                'working': 'text-blue-600',
                'failed': 'text-red-600',
                'canceled': 'text-gray-600',
            }[task.status.state] || 'text-gray-600';

            taskDiv.innerHTML = `
                <div class="flex justify-between items-center">
                    <code class="text-xs bg-gray-200 px-2 py-1 rounded">${task.id.substring(0, 12)}...</code>
                    <span class="${statusColor} font-medium">${task.status.state}</span>
                </div>
                <div class="text-gray-500 text-xs mt-1">
                    Updated: ${new Date(task.updatedAt).toLocaleString()}
                </div>
            `;

            this.elements.taskList.appendChild(taskDiv);
        }
    }

    startNewConversation() {
        this.client.clearContextId();
        this.elements.messages.innerHTML = `
            <div class="welcome-message text-center text-gray-500 py-8">
                <p>Start a new conversation with the agent.</p>
                <p class="text-sm mt-2">Try asking about products, navigation, or brand information.</p>
            </div>
        `;
        this.updateContextDisplay();
        this.elements.taskPanel.classList.add('hidden');
        this.elements.taskList.innerHTML = '';
    }

    clearSession() {
        this.client.clearToken();
        this.client.clearContextId();
        this.elements.tokenInput.value = '';
        this.disconnect();
    }

    disconnect() {
        this.isConnected = false;
        this.updateConnectionStatus(false);
        this.elements.chatContainer.classList.add('hidden');
        this.elements.taskPanel.classList.add('hidden');
        this.elements.authPanel.classList.remove('hidden');
    }

    showChatInterface() {
        this.elements.chatContainer.classList.remove('hidden');
        this.elements.messageInput.focus();
    }

    updateConnectionStatus(connected) {
        const dot = this.elements.connectionStatus.querySelector('.status-dot');
        const text = this.elements.connectionStatus.querySelector('.status-text');

        if (connected) {
            dot.className = 'status-dot w-3 h-3 rounded-full bg-green-500 mr-2';
            text.textContent = 'Connected';
            text.className = 'status-text text-sm text-green-600';
        } else {
            dot.className = 'status-dot w-3 h-3 rounded-full bg-gray-400 mr-2';
            text.textContent = 'Not Connected';
            text.className = 'status-text text-sm text-gray-500';
        }
    }

    updateContextDisplay() {
        const contextId = this.client.contextId;
        this.elements.contextIdDisplay.textContent = contextId
            ? `${contextId.substring(0, 8)}...`
            : '-';
    }

    showAuthError(message) {
        this.elements.authError.textContent = message;
        this.elements.authError.classList.remove('hidden');
    }

    hideAuthError() {
        this.elements.authError.classList.add('hidden');
    }

    setLoading(loading) {
        this.elements.connectBtn.disabled = loading;
        this.elements.connectBtn.textContent = loading ? 'Connecting...' : 'Connect';
    }

    setSending(sending) {
        this.elements.sendBtn.disabled = sending;
        this.elements.messageInput.disabled = sending;
        this.elements.sendBtn.textContent = sending ? 'Sending...' : 'Send';
    }
}

// Initialize on DOM load
document.addEventListener('DOMContentLoaded', () => {
    window.chatUI = new ChatUI();
});
