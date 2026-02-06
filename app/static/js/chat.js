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

        // Message history for arrow key navigation
        this.messageHistory = [];
        this.historyIndex = -1;
        this.currentDraft = '';

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
        };

        this.init();
    }

    init() {
        // Check for server-provided token (from env variable)
        const serverToken = window.__IMS_TOKEN__ || '';
        this.serverTokenProvided = serverToken.length > 0;

        this.client.loadContextId();

        if (this.serverTokenProvided) {
            // Token provided via environment — hide auth panel, auto-connect
            this.elements.authPanel.classList.add('hidden');
            this.client.setToken(serverToken);
            this.validateAndConnect();
        } else {
            // No server token — try to restore from session storage
            const storedToken = this.client.loadToken();
            if (storedToken) {
                this.elements.tokenInput.value = storedToken;
                this.validateAndConnect();
            }
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

        // Message history navigation with arrow keys
        this.elements.messageInput.addEventListener('keydown', (e) => this.handleHistoryNavigation(e));
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

            // If the server-provided token failed, reveal the auth panel with the error
            if (this.serverTokenProvided) {
                this.elements.authPanel.classList.remove('hidden');
            }

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

        // Add to message history
        this.messageHistory.push(text);
        this.historyIndex = this.messageHistory.length;
        this.currentDraft = '';

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

    handleHistoryNavigation(event) {
        // Handle arrow key navigation through message history
        if (event.key === 'ArrowUp') {
            event.preventDefault();

            if (this.messageHistory.length === 0) return;

            // Save current draft when first pressing up
            if (this.historyIndex === this.messageHistory.length) {
                this.currentDraft = this.elements.messageInput.value;
            }

            // Navigate backwards in history
            if (this.historyIndex > 0) {
                this.historyIndex--;
                this.elements.messageInput.value = this.messageHistory[this.historyIndex];
            }
        } else if (event.key === 'ArrowDown') {
            event.preventDefault();

            if (this.messageHistory.length === 0) return;

            // Navigate forwards in history
            if (this.historyIndex < this.messageHistory.length - 1) {
                this.historyIndex++;
                this.elements.messageInput.value = this.messageHistory[this.historyIndex];
            } else if (this.historyIndex === this.messageHistory.length - 1) {
                // Reached the end, restore draft or clear
                this.historyIndex = this.messageHistory.length;
                this.elements.messageInput.value = this.currentDraft;
            }
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

        // Check if agent message needs confirmation buttons
        console.log('[BUTTON DEBUG] Checking if buttons needed, role:', role);
        if (role === 'agent' && this.needsConfirmation(text)) {
            console.log('[BUTTON DEBUG] Creating buttons!');
            const buttonContainer = document.createElement('div');
            buttonContainer.className = 'flex gap-2 mt-3';

            const confirmBtn = document.createElement('button');
            confirmBtn.textContent = 'Confirm';
            confirmBtn.className = 'px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors';
            confirmBtn.onclick = () => this.handleConfirmation(true, buttonContainer);

            const cancelBtn = document.createElement('button');
            cancelBtn.textContent = 'Cancel';
            cancelBtn.className = 'px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors';
            cancelBtn.onclick = () => this.handleConfirmation(false, buttonContainer);

            buttonContainer.appendChild(confirmBtn);
            buttonContainer.appendChild(cancelBtn);
            bubble.appendChild(buttonContainer);
            console.log('[BUTTON DEBUG] Buttons appended to bubble');
        } else {
            console.log('[BUTTON DEBUG] No buttons needed');
        }

        messageDiv.appendChild(bubble);
        this.elements.messages.appendChild(messageDiv);
        this.elements.messages.scrollTop = this.elements.messages.scrollHeight;
    }

    needsConfirmation(text) {
        // Check if text indicates a pending change that needs confirmation
        const confirmationPatterns = [
            /will be changed to/i,
            /will be updated to/i,
            /address will be changed/i,
            /delivery date will be changed/i
        ];
        const result = confirmationPatterns.some(pattern => pattern.test(text));
        console.log('[BUTTON DEBUG] needsConfirmation called');
        console.log('[BUTTON DEBUG] text:', text);
        console.log('[BUTTON DEBUG] result:', result);
        return result;
    }

    async handleConfirmation(confirmed, buttonContainer) {
        // Disable buttons immediately
        buttonContainer.querySelectorAll('button').forEach(btn => {
            btn.disabled = true;
            btn.style.opacity = '0.5';
        });

        // Send confirmation or cancellation
        const message = confirmed ? 'confirm' : 'cancel';

        try {
            const task = await this.client.sendMessage(message);

            // Update context display
            this.updateContextDisplay();

            // Extract and display agent response
            const agentMessages = task.messages.filter(m => m.role === 'agent');
            if (agentMessages.length > 0) {
                const lastResponse = agentMessages[agentMessages.length - 1];
                const responseText = this.extractTextFromMessage(lastResponse);
                this.addMessage('agent', responseText, task);
            }

        } catch (error) {
            this.addSystemMessage(`Error: ${error.message}`);

            if (error instanceof AuthenticationError) {
                this.disconnect();
            }
        }
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

        } catch (error) {
            console.error('Failed to load conversation history:', error);
        }
    }

    startNewConversation() {
        this.client.clearContextId();

        // Reset message history
        this.messageHistory = [];
        this.historyIndex = -1;
        this.currentDraft = '';

        this.elements.messages.innerHTML = `
            <div class="welcome-message text-center text-gray-500 py-8">
                <p>Start a new conversation with the agent.</p>
                <p class="text-sm mt-2">Try asking about products, navigation, or brand information.</p>
            </div>
        `;
        this.updateContextDisplay();
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
        this.elements.authPanel.classList.remove('hidden');
    }

    showChatInterface() {
        this.elements.authPanel.classList.add('hidden');
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
