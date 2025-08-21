/**
 * RemindMine AI Agent - Web UI JavaScript
 */

class RemindMineApp {
    constructor() {
        this.currentPage = 1;
        this.totalPages = 1;
        this.issuesPerPage = 20;
        this.currentFilters = {};
        this.init();
    }

    init() {
        this.setupTabs();
        this.setupEventListeners();
        this.loadInitialData();
    }

    setupTabs() {
        const tabButtons = document.querySelectorAll('.nav-btn');
        const tabContents = document.querySelectorAll('.tab-content');

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabId = button.dataset.tab;

                // Update active tab button
                tabButtons.forEach(btn => btn.classList.remove('active'));
                button.classList.add('active');

                // Update active tab content
                tabContents.forEach(content => content.classList.remove('active'));
                document.getElementById(tabId).classList.add('active');

                // Load tab-specific data
                this.handleTabChange(tabId);
            });
        });
    }

    setupEventListeners() {
        // Dashboard events
        document.getElementById('refresh-issues').addEventListener('click', () => {
            this.loadIssues();
        });

        // Filter events
        ['project-filter', 'status-filter', 'priority-filter'].forEach(filterId => {
            document.getElementById(filterId).addEventListener('change', (e) => {
                const filterType = filterId.replace('-filter', '');
                this.currentFilters[filterType] = e.target.value;
                this.currentPage = 1;
                this.loadIssues();
            });
        });

        // Pagination events
        document.getElementById('prev-page').addEventListener('click', () => {
            if (this.currentPage > 1) {
                this.currentPage--;
                this.loadIssues();
            }
        });

        document.getElementById('next-page').addEventListener('click', () => {
            if (this.currentPage < this.totalPages) {
                this.currentPage++;
                this.loadIssues();
            }
        });

        // Issue creation form
        document.getElementById('create-issue-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.createIssue();
        });

        // Settings events
        document.getElementById('auto-advice-toggle').addEventListener('change', (e) => {
            this.updateAutoAdviceSettings(e.target.checked);
        });

        document.getElementById('save-settings').addEventListener('click', () => {
            this.saveSettings();
        });

        document.getElementById('test-connection').addEventListener('click', () => {
            this.testConnection();
        });

        // Modal events
        this.setupModalEvents();

        // Notification events
        document.getElementById('notification-close').addEventListener('click', () => {
            this.hideNotification();
        });
    }

    setupModalEvents() {
        const modal = document.getElementById('advice-modal');
        const closeBtn = modal.querySelector('.modal-close');

        closeBtn.addEventListener('click', () => {
            this.hideModal();
        });

        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                this.hideModal();
            }
        });
    }

    async loadInitialData() {
        try {
            await Promise.all([
                this.loadProjects(),
                this.loadTrackers(),
                this.loadPriorities(),
                this.loadStatuses(),
                this.loadUsers(),
                this.loadSettings()
            ]);
            this.loadIssues();
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showNotification('初期データの読み込みに失敗しました', 'error');
        }
    }

    handleTabChange(tabId) {
        switch (tabId) {
            case 'dashboard':
                this.loadIssues();
                break;
            case 'create-issue':
                // Refresh form data if needed
                break;
            case 'settings':
                this.loadSystemInfo();
                break;
        }
    }

    async loadIssues() {
        try {
            this.showLoading(true);

            const params = new URLSearchParams({
                page: this.currentPage,
                limit: this.issuesPerPage,
                ...this.currentFilters
            });

            const response = await fetch(`/api/web/issues?${params}`);
            if (!response.ok) throw new Error('Failed to fetch issues');

            const data = await response.json();
            this.renderIssues(data.issues);
            this.updatePagination(data.pagination);

        } catch (error) {
            console.error('Failed to load issues:', error);
            this.showNotification('Issue一覧の読み込みに失敗しました', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    renderIssues(issues) {
        const container = document.getElementById('issues-container');
        
        if (issues.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted">
                    <i class="fas fa-inbox"></i>
                    <p>該当するIssueが見つかりませんでした</p>
                </div>
            `;
            return;
        }

        container.innerHTML = issues.map(issue => this.renderIssueCard(issue)).join('');
    }

    renderIssueCard(issue) {
        const hasAdvice = issue.ai_advice && issue.ai_advice.trim();
        const truncatedDescription = this.truncateText(issue.description || '', 150);
        
        return `
            <div class="issue-card">
                <div class="issue-header">
                    <div>
                        <div class="issue-title">
                            <a href="${issue.redmine_url}" target="_blank" rel="noopener">
                                ${this.escapeHtml(issue.subject)}
                            </a>
                        </div>
                        <div class="issue-id">#${issue.id}</div>
                    </div>
                </div>
                
                <div class="issue-meta">
                    <span class="issue-meta-item status-${this.normalizeStatus(issue.status)}">
                        ${this.escapeHtml(issue.status)}
                    </span>
                    <span class="issue-meta-item priority-${this.normalizePriority(issue.priority)}">
                        ${this.escapeHtml(issue.priority)}
                    </span>
                    <span class="issue-meta-item">
                        ${this.escapeHtml(issue.project)}
                    </span>
                    <span class="issue-meta-item">
                        ${this.escapeHtml(issue.tracker)}
                    </span>
                    ${issue.assigned_to ? `
                        <span class="issue-meta-item">
                            担当: ${this.escapeHtml(issue.assigned_to)}
                        </span>
                    ` : ''}
                </div>

                ${truncatedDescription ? `
                    <div class="issue-description">
                        ${this.escapeHtml(truncatedDescription)}
                    </div>
                ` : ''}

                ${hasAdvice ? `
                    <div class="ai-advice">
                        <div class="ai-advice-header">
                            <i class="fas fa-robot"></i>
                            AIアドバイス
                        </div>
                        <div class="ai-advice-content">
                            ${this.escapeHtml(this.truncateText(issue.ai_advice, 200))}
                        </div>
                    </div>
                ` : ''}

                <div class="issue-actions">
                    ${hasAdvice ? `
                        <button class="btn btn-secondary" onclick="app.showAdviceModal('${issue.id}', \`${this.escapeForJs(issue.ai_advice)}\`)">
                            <i class="fas fa-eye"></i> アドバイス詳細
                        </button>
                    ` : ''}
                    <button class="btn btn-primary" onclick="app.generateAdvice('${issue.id}')">
                        <i class="fas fa-magic"></i> アドバイス生成
                    </button>
                    <a href="${issue.redmine_url}" target="_blank" rel="noopener" class="btn btn-secondary">
                        <i class="fas fa-external-link-alt"></i> Redmineで開く
                    </a>
                </div>
            </div>
        `;
    }

    updatePagination(pagination) {
        this.currentPage = pagination.current_page;
        this.totalPages = pagination.total_pages;

        document.getElementById('page-info').textContent = 
            `${pagination.current_page} / ${pagination.total_pages}`;

        document.getElementById('prev-page').disabled = pagination.current_page <= 1;
        document.getElementById('next-page').disabled = pagination.current_page >= pagination.total_pages;
    }

    async loadProjects() {
        try {
            const response = await fetch('/api/web/projects');
            if (!response.ok) throw new Error('Failed to fetch projects');
            
            const projects = await response.json();
            this.populateSelect('project-filter', projects, 'id', 'name', '全プロジェクト');
            this.populateSelect('issue-project', projects, 'id', 'name');
        } catch (error) {
            console.error('Failed to load projects:', error);
        }
    }

    async loadTrackers() {
        try {
            const response = await fetch('/api/web/trackers');
            if (!response.ok) throw new Error('Failed to fetch trackers');
            
            const trackers = await response.json();
            this.populateSelect('issue-tracker', trackers, 'id', 'name');
        } catch (error) {
            console.error('Failed to load trackers:', error);
        }
    }

    async loadPriorities() {
        try {
            const response = await fetch('/api/web/priorities');
            if (!response.ok) throw new Error('Failed to fetch priorities');
            
            const priorities = await response.json();
            this.populateSelect('priority-filter', priorities, 'id', 'name', '全優先度');
            this.populateSelect('issue-priority', priorities, 'id', 'name');
        } catch (error) {
            console.error('Failed to load priorities:', error);
        }
    }

    async loadStatuses() {
        try {
            const response = await fetch('/api/web/statuses');
            if (!response.ok) throw new Error('Failed to fetch statuses');
            
            const statuses = await response.json();
            this.populateSelect('status-filter', statuses, 'id', 'name', '全ステータス');
        } catch (error) {
            console.error('Failed to load statuses:', error);
        }
    }

    async loadUsers() {
        try {
            const response = await fetch('/api/web/users');
            if (!response.ok) throw new Error('Failed to fetch users');
            
            const users = await response.json();
            this.populateSelect('issue-assignee', users, 'id', 'name', '未割り当て');
        } catch (error) {
            console.error('Failed to load users:', error);
        }
    }

    async loadSystemInfo() {
        try {
            const response = await fetch('/api/health');
            if (!response.ok) throw new Error('Failed to fetch system info');
            
            const info = await response.json();
            document.getElementById('redmine-url').textContent = info.redmine_url;
            document.getElementById('ollama-url').textContent = info.ollama_url;
            document.getElementById('chromadb-path').textContent = info.chromadb_path;
        } catch (error) {
            console.error('Failed to load system info:', error);
        }
    }

    async loadSettings() {
        try {
            const response = await fetch('/api/web/settings');
            if (!response.ok) throw new Error('Failed to fetch settings');
            
            const settings = await response.json();
            document.getElementById('auto-advice-toggle').checked = settings.auto_advice_enabled;
            document.getElementById('issues-per-page-setting').value = settings.issues_per_page;
            this.issuesPerPage = settings.issues_per_page;
        } catch (error) {
            console.error('Failed to load settings:', error);
        }
    }

    populateSelect(selectId, items, valueField, textField, defaultText = null) {
        const select = document.getElementById(selectId);
        if (!select) return;
        
        select.innerHTML = '';

        if (defaultText) {
            const defaultOption = document.createElement('option');
            defaultOption.value = '';
            defaultOption.textContent = defaultText;
            select.appendChild(defaultOption);
        }

        items.forEach(item => {
            const option = document.createElement('option');
            option.value = item[valueField];
            option.textContent = item[textField];
            select.appendChild(option);
        });
    }

    async createIssue() {
        try {
            const formData = new FormData(document.getElementById('create-issue-form'));
            const issueData = Object.fromEntries(formData.entries());

            // Remove empty fields
            Object.keys(issueData).forEach(key => {
                if (!issueData[key]) {
                    delete issueData[key];
                }
            });

            const response = await fetch('/api/web/issues', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(issueData)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to create issue');
            }

            this.showNotification('Issueが正常に作成されました', 'success');
            
            // Reset form
            document.getElementById('create-issue-form').reset();
            
            // Refresh issues if on dashboard
            if (document.getElementById('dashboard').classList.contains('active')) {
                this.loadIssues();
            }

        } catch (error) {
            console.error('Failed to create issue:', error);
            this.showNotification(`Issue作成に失敗しました: ${error.message}`, 'error');
        }
    }

    async generateAdvice(issueId) {
        try {
            this.showNotification('AIアドバイスを生成中...', 'info');

            const response = await fetch(`/api/web/issues/${issueId}/advice`, {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to generate advice');
            }

            this.showNotification('AIアドバイスが生成されました', 'success');
            this.loadIssues(); // Refresh to show new advice

        } catch (error) {
            console.error('Failed to generate advice:', error);
            this.showNotification(`アドバイス生成に失敗しました: ${error.message}`, 'error');
        }
    }

    showAdviceModal(issueId, advice) {
        const modal = document.getElementById('advice-modal');
        const content = document.getElementById('advice-content');
        
        content.innerHTML = `
            <div class="ai-advice-content">
                ${this.escapeHtml(advice).replace(/\n/g, '<br>')}
            </div>
        `;
        
        modal.classList.add('show');
    }

    hideModal() {
        const modal = document.getElementById('advice-modal');
        modal.classList.remove('show');
    }

    async updateAutoAdviceSettings(enabled) {
        try {
            const response = await fetch('/api/web/settings/auto-advice', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ enabled })
            });

            if (!response.ok) throw new Error('Failed to update settings');

            this.showNotification(
                enabled ? '自動アドバイス機能が有効になりました' : '自動アドバイス機能が無効になりました',
                'success'
            );

        } catch (error) {
            console.error('Failed to update auto-advice settings:', error);
            this.showNotification('設定の更新に失敗しました', 'error');
            
            // Revert toggle state
            document.getElementById('auto-advice-toggle').checked = !enabled;
        }
    }

    async saveSettings() {
        try {
            const issuesPerPage = document.getElementById('issues-per-page-setting').value;
            
            const response = await fetch('/api/web/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    issues_per_page: parseInt(issuesPerPage)
                })
            });

            if (!response.ok) throw new Error('Failed to save settings');

            this.issuesPerPage = parseInt(issuesPerPage);
            this.showNotification('設定が保存されました', 'success');

        } catch (error) {
            console.error('Failed to save settings:', error);
            this.showNotification('設定の保存に失敗しました', 'error');
        }
    }

    async testConnection() {
        try {
            this.showNotification('接続テスト中...', 'info');

            const response = await fetch('/api/health');
            if (!response.ok) throw new Error('Health check failed');

            this.showNotification('接続テストが成功しました', 'success');

        } catch (error) {
            console.error('Connection test failed:', error);
            this.showNotification('接続テストに失敗しました', 'error');
        }
    }

    showLoading(show) {
        const loading = document.getElementById('loading');
        if (loading) {
            loading.style.display = show ? 'block' : 'none';
        }
    }

    showNotification(message, type = 'info') {
        const notification = document.getElementById('notification');
        const messageEl = document.getElementById('notification-message');
        
        if (notification && messageEl) {
            messageEl.textContent = message;
            notification.className = `notification ${type}`;
            notification.classList.add('show');

            // Auto-hide after 5 seconds
            setTimeout(() => {
                this.hideNotification();
            }, 5000);
        }
    }

    hideNotification() {
        const notification = document.getElementById('notification');
        if (notification) {
            notification.classList.remove('show');
        }
    }

    // Utility methods
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    escapeForJs(text) {
        if (!text) return '';
        return text.replace(/`/g, '\\`').replace(/\$/g, '\\$').replace(/\\/g, '\\\\');
    }

    truncateText(text, maxLength) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
    }

    normalizeStatus(status) {
        if (!status) return 'unknown';
        const normalized = status.toLowerCase().replace(/\s+/g, '-');
        if (normalized.includes('新規') || normalized.includes('new')) return 'new';
        if (normalized.includes('進行中') || normalized.includes('progress')) return 'in-progress';
        if (normalized.includes('解決') || normalized.includes('resolved')) return 'resolved';
        if (normalized.includes('終了') || normalized.includes('closed')) return 'closed';
        return 'unknown';
    }

    normalizePriority(priority) {
        if (!priority) return 'normal';
        const normalized = priority.toLowerCase();
        if (normalized.includes('低') || normalized.includes('low')) return 'low';
        if (normalized.includes('高') || normalized.includes('high')) return 'high';
        if (normalized.includes('急') || normalized.includes('urgent')) return 'urgent';
        return 'normal';
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new RemindMineApp();
});