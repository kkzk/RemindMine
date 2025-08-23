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

    // Issue作成機能は廃止されたためイベントリスナー削除

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

        // Cache management events
        document.getElementById('refresh-cache-stats').addEventListener('click', () => {
            this.loadCacheStats();
        });

        document.getElementById('clear-cache').addEventListener('click', () => {
            this.clearCache();
        });

        // Pending advice events (removed - no longer needed)

        // Dashboard pending advice events (removed - no longer needed)

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
                this.loadSettings(),
                this.loadCacheStats()
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
            // create-issue タブは削除済み
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

            // Load issues and pending advice simultaneously
            const [issuesResponse, pendingResponse] = await Promise.all([
                fetch(`/api/web/issues?${params}`),
                fetch('/api/web/pending-advice')
            ]);

            if (!issuesResponse.ok) throw new Error('Failed to fetch issues');
            if (!pendingResponse.ok) throw new Error('Failed to fetch pending advice');

            const issuesData = await issuesResponse.json();
            const pendingData = await pendingResponse.json();
            
            this.renderIssuesWithPendingAdvice(issuesData.issues, pendingData.pending_advice || []);
            this.updatePagination(issuesData.pagination);

        } catch (error) {
            console.error('Failed to load issues:', error);
            this.showNotification('Issue一覧の読み込みに失敗しました', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    renderIssuesWithPendingAdvice(issues, pendingAdvice) {
        const container = document.getElementById('issues-container');
        
        if (issues.length === 0 && pendingAdvice.length === 0) {
            container.innerHTML = `
                <div class="text-center text-muted">
                    <i class="fas fa-inbox"></i>
                    <p>該当するIssueが見つかりませんでした</p>
                </div>
            `;
            return;
        }

        // Create a map of pending advice by issue ID for quick lookup
        // Only keep the latest advice for each issue
        const pendingByIssueId = {};
        pendingAdvice.forEach(advice => {
            const issueId = advice.issue_id;
            if (!pendingByIssueId[issueId] || 
                new Date(advice.created_at) > new Date(pendingByIssueId[issueId].created_at)) {
                pendingByIssueId[issueId] = advice;
            }
        });

        // Render issues with their pending advice
        container.innerHTML = issues.map(issue => 
            this.renderIssueCardWithAdvice(issue, pendingByIssueId[issue.id] ? [pendingByIssueId[issue.id]] : [])
        ).join('');
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
        const hasSummary = issue.content_summary && issue.content_summary.trim();
        const hasJournalSummary = issue.journal_summary && issue.journal_summary.trim();
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
                    ${issue.has_journals ? `
                        <span class="issue-meta-item">
                            <i class="fas fa-comments"></i> ${issue.journal_count}件のコメント
                        </span>
                    ` : ''}
                </div>

                ${hasSummary ? `
                    <div class="issue-summary">
                        <div class="summary-header">
                            <i class="fas fa-file-text"></i>
                            <strong>内容要約</strong>
                        </div>
                        <div class="summary-content scrollable">
                            ${this.escapeHtml(issue.content_summary)}
                        </div>
                    </div>
                ` : truncatedDescription ? `
                    <div class="issue-description">
                        ${this.escapeHtml(truncatedDescription)}
                    </div>
                ` : ''}

                ${hasJournalSummary ? `
                    <div class="journal-summary">
                        <div class="summary-header">
                            <i class="fas fa-comments"></i>
                            <strong>コメント要約</strong>
                        </div>
                        <div class="summary-content">
                            ${this.escapeHtml(issue.journal_summary)}
                        </div>
                    </div>
                ` : ''}

                ${hasAdvice ? `
                    <div class="ai-advice">
                        <div class="ai-advice-header">
                            <i class="fas fa-robot"></i>
                            AIアドバイス
                        </div>
                        <div class="ai-advice-content scrollable" id="ai-advice-${issue.id}">
                            ${this.escapeHtml(issue.ai_advice || '')}
                        </div>
                    </div>
                ` : ''}

                <div class="issue-actions">
                    ${hasAdvice ? `
                        <button class="btn btn-secondary" onclick="app.showAdviceModal('${issue.id}', \`${this.escapeForJs(issue.ai_advice)}\`)">
                            <i class="fas fa-eye"></i> アドバイス詳細
                        </button>
                    ` : ''}
                    <button class="btn btn-secondary" onclick="app.regenerateSummaries('${issue.id}')">
                        <i class="fas fa-sync"></i> サマリ再作成
                    </button>
                    <button class="btn btn-primary" onclick="app.generateAdvice('${issue.id}')">
                        <i class="fas fa-redo"></i> アドバイス再作成
                    </button>
                    <a href="${issue.redmine_url}" target="_blank" rel="noopener" class="btn btn-secondary">
                        <i class="fas fa-external-link-alt"></i> Redmineで開く
                    </a>
                </div>
            </div>
        `;
    }

    renderIssueCardWithAdvice(issue, pendingAdviceList) {
        const hasAdvice = issue.ai_advice && issue.ai_advice.trim();
        const hasSummary = issue.content_summary && issue.content_summary.trim();
        const hasJournalSummary = issue.journal_summary && issue.journal_summary.trim();
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
                    ${issue.has_journals ? `
                        <span class="issue-meta-item">
                            <i class="fas fa-comments"></i> ${issue.journal_count}件のコメント
                        </span>
                    ` : ''}
                </div>

                ${hasSummary ? `
                    <div class="issue-summary">
                        <div class="summary-header">
                            <i class="fas fa-file-text"></i>
                            <strong>内容要約</strong>
                        </div>
                        <div class="summary-content scrollable">
                            ${this.escapeHtml(issue.content_summary)}
                        </div>
                    </div>
                ` : truncatedDescription ? `
                    <div class="issue-description">
                        ${this.escapeHtml(truncatedDescription)}
                    </div>
                ` : ''}

                ${hasJournalSummary ? `
                    <div class="journal-summary">
                        <div class="summary-header">
                            <i class="fas fa-comments"></i>
                            <strong>コメント要約</strong>
                        </div>
                        <div class="summary-content">
                            ${this.escapeHtml(issue.journal_summary)}
                        </div>
                    </div>
                ` : ''}

                ${hasAdvice ? `
                    <div class="ai-advice">
                        <div class="ai-advice-header">
                            <i class="fas fa-robot"></i>
                            AIアドバイス (投稿済み)
                        </div>
                        <div class="ai-advice-content scrollable" id="ai-advice-${issue.id}">
                            ${this.escapeHtml(issue.ai_advice || '')}
                        </div>
                    </div>
                ` : ''}

                ${pendingAdviceList.length > 0 ? `
                    <div class="pending-advice-section">
                        <div class="pending-advice-header">
                            <i class="fas fa-clock"></i>
                            <strong>問題解決のためのAIアドバイス (承認待ち)</strong>
                        </div>
                        ${pendingAdviceList.map(advice => `
                            <div class="pending-advice-item-inline" data-advice-id="${this.escapeHtml(advice.id)}">
                                <div class="advice-content-inline">
                                    <div class="advice-text scrollable" id="advice-${advice.id}">
                                        ${this.escapeHtml(advice.advice_content || '')}
                                    </div>
                                </div>
                                <div class="advice-actions-inline">
                                    <button class="btn btn-success btn-sm" onclick="app.approveAdvice('${advice.id}')">
                                        <i class="fas fa-check"></i> 承認
                                    </button>
                                    <button class="btn btn-danger btn-sm" onclick="app.rejectAdvice('${advice.id}')">
                                        <i class="fas fa-times"></i> 却下
                                    </button>
                                </div>
                            </div>
                        `).join('')}
                    </div>
                ` : ''}

                <div class="issue-actions">
                    ${hasAdvice ? `
                        <button class="btn btn-secondary" onclick="app.showAdviceModal('${issue.id}', \`${this.escapeForJs(issue.ai_advice)}\`)">
                            <i class="fas fa-eye"></i> アドバイス詳細
                        </button>
                    ` : ''}
                    <button class="btn btn-secondary" onclick="app.regenerateSummaries('${issue.id}')">
                        <i class="fas fa-sync"></i> サマリ再作成
                    </button>
                    <button class="btn btn-primary" onclick="app.generateAdvice('${issue.id}')">
                        <i class="fas fa-redo"></i> アドバイス再作成
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
        } catch (error) {
            console.error('Failed to load projects:', error);
        }
    }

    async loadTrackers() {
        try {
            const response = await fetch('/api/web/trackers');
            if (!response.ok) throw new Error('Failed to fetch trackers');
            
            const trackers = await response.json();
            // issue-tracker セレクトは廃止
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
            // issue-assignee セレクトは廃止
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

    // createIssue 機能は削除されました

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

    async regenerateSummaries(issueId) {
        try {
            this.showNotification('サマリ再生成中...', 'info');

            const response = await fetch(`/api/web/issues/${issueId}/summaries/regenerate`, { method: 'POST' });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || 'Failed to regenerate summaries');
            }

            this.showNotification('サマリを再生成しました', 'success');
            // 再取得
            this.loadIssues();
        } catch (error) {
            console.error('Failed to regenerate summaries:', error);
            this.showNotification(`サマリ再生成に失敗しました: ${error.message}`, 'error');
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

    // Pending Advice Methods
    async loadPendingAdvice() {
        try {
            this.showPendingLoading(true);
            
            const response = await fetch('/api/web/pending-advice');
            const data = await response.json();
            
            if (response.ok) {
                this.renderPendingAdvice(data.pending_advice);
                this.updatePendingAdviceCount();
            } else {
                throw new Error(data.detail || 'Failed to load pending advice');
            }
        } catch (error) {
            console.error('Error loading pending advice:', error);
            this.showNotification('保留アドバイスの読み込みに失敗しました', 'error');
        } finally {
            this.showPendingLoading(false);
        }
    }

    async updatePendingAdviceCount() {
        try {
            const response = await fetch('/api/web/pending-advice');
            const data = await response.json();
            
            if (response.ok) {
                const count = data.count || 0;
                const badge = document.getElementById('pending-count');
                if (badge) {
                    badge.textContent = count;
                    if (count > 0) {
                        badge.classList.add('show');
                    } else {
                        badge.classList.remove('show');
                    }
                }
            }
        } catch (error) {
            console.error('Error updating pending advice count:', error);
        }
    }

    renderPendingAdvice(pendingList) {
        const container = document.getElementById('pending-advice-container');
        const emptyState = document.getElementById('pending-empty');
        
        if (!container || !emptyState) return;
        
        if (!pendingList || pendingList.length === 0) {
            container.innerHTML = '';
            emptyState.style.display = 'block';
            return;
        }
        
        emptyState.style.display = 'none';
        
        container.innerHTML = pendingList.map(advice => {
            return this.createPendingAdviceCard(advice);
        }).join('');
        
        // Add event listeners for action buttons
        this.setupPendingAdviceEventListeners();
    }

    createPendingAdviceCard(advice) {
        const createdDate = new Date(advice.created_at).toLocaleString('ja-JP');
        const shortDescription = this.truncateText(advice.issue_description, 150);
        const shortAdvice = this.truncateText(advice.advice_content, 300);
        
        return `
            <div class="pending-advice-item" data-advice-id="${this.escapeHtml(advice.id)}">
                <div class="pending-advice-header">
                    <h3>
                        <i class="fas fa-exclamation-triangle"></i>
                        Issue #${advice.issue_id}: ${this.escapeHtml(advice.issue_subject)}
                    </h3>
                    <div class="pending-advice-meta">
                        <span><i class="fas fa-folder"></i> ${this.escapeHtml(advice.project_name)}</span>
                        <span><i class="fas fa-tag"></i> ${this.escapeHtml(advice.tracker_name)}</span>
                        <span><i class="fas fa-flag"></i> ${this.escapeHtml(advice.priority_name)}</span>
                        <span><i class="fas fa-clock"></i> ${createdDate}</span>
                    </div>
                </div>
                
                <div class="pending-advice-body">
                    <div class="issue-info">
                        <h4>Issue詳細</h4>
                        <div class="issue-description" id="desc-${advice.id}">
                            ${this.escapeHtml(shortDescription)}
                            ${advice.issue_description.length > 150 ? 
                                `<button class="expand-toggle" onclick="app.toggleExpand('desc-${advice.id}', '${this.escapeForJs(advice.issue_description)}')">続きを読む</button>` : 
                                ''
                            }
                        </div>
                    </div>
                    
                    <div class="advice-content">
                        <h4><i class="fas fa-robot"></i> 生成されたAIアドバイス</h4>
                        <div class="advice-text" id="advice-${advice.id}">
                            ${this.escapeHtml(shortAdvice)}
                            ${advice.advice_content.length > 300 ? 
                                `<button class="expand-toggle" onclick="app.toggleExpand('advice-${advice.id}', '${this.escapeForJs(advice.advice_content)}')">続きを読む</button>` : 
                                ''
                            }
                        </div>
                    </div>
                </div>
                
                <div class="pending-advice-actions">
                    <div class="advice-actions-left">
                        <a href="${advice.issue_url}" target="_blank" class="btn btn-secondary">
                            <i class="fas fa-external-link-alt"></i> Redmineで確認
                        </a>
                    </div>
                    <div class="advice-actions-right">
                        <button class="btn btn-approve" onclick="app.approveAdvice('${advice.id}')">
                            <i class="fas fa-check"></i> 承認・投稿
                        </button>
                        <button class="btn btn-reject" onclick="app.rejectAdvice('${advice.id}')">
                            <i class="fas fa-times"></i> 却下
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    setupPendingAdviceEventListeners() {
        // Event listeners are set up via onclick attributes in the HTML
        // This method can be used for additional event setup if needed
    }

    async approveAdvice(adviceId) {
        if (!confirm('このAIアドバイスをRedmineに投稿しますか？')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/web/pending-advice/${adviceId}/approve`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showNotification(`Issue #${data.issue_id}にアドバイスを投稿しました`, 'success');
                this.loadIssues(); // Reload dashboard with updated data
            } else {
                throw new Error(data.detail || 'Failed to approve advice');
            }
        } catch (error) {
            console.error('Error approving advice:', error);
            this.showNotification('アドバイスの承認に失敗しました', 'error');
        }
    }

    async rejectAdvice(adviceId) {
        if (!confirm('このAIアドバイスを却下しますか？\n※一度却下すると復元できません。')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/web/pending-advice/${adviceId}/reject`, {
                method: 'POST'
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.showNotification(`Issue #${data.issue_id}のアドバイスを却下しました`, 'info');
                this.loadIssues(); // Reload dashboard with updated data
            } else {
                throw new Error(data.detail || 'Failed to reject advice');
            }
        } catch (error) {
            console.error('Error rejecting advice:', error);
            this.showNotification('アドバイスの却下に失敗しました', 'error');
        }
    }

    toggleExpand(elementId, fullText) {
        const element = document.getElementById(elementId);
        if (!element) return;
        
        const isExpanded = element.classList.contains('expanded');
        
        if (isExpanded) {
            // Collapse
            const shortText = this.truncateText(fullText, elementId.startsWith('desc-') ? 150 : 300);
            element.innerHTML = this.escapeHtml(shortText) + 
                `<button class="expand-toggle" onclick="app.toggleExpand('${elementId}', '${this.escapeForJs(fullText)}')">続きを読む</button>`;
            element.classList.remove('expanded');
        } else {
            // Expand
            element.innerHTML = this.escapeHtml(fullText) + 
                `<button class="expand-toggle" onclick="app.toggleExpand('${elementId}', '${this.escapeForJs(fullText)}')">折りたたむ</button>`;
            element.classList.add('expanded');
        }
    }

    showPendingLoading(show) {
        const loading = document.getElementById('pending-loading');
        if (loading) {
            loading.style.display = show ? 'block' : 'none';
        }
    }

    truncateText(text, maxLength) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength) + '...';
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

    async loadCacheStats() {
        try {
            const response = await fetch('/api/web/cache/stats');
            const data = await response.json();
            
            if (data.success) {
                const stats = data.stats;
                document.getElementById('cache-count').textContent = stats.total_cached_issues || 0;
                document.getElementById('cache-file-path').textContent = stats.cache_file_path || 'N/A';
            } else {
                console.error('Failed to load cache stats:', data.error);
                document.getElementById('cache-count').textContent = 'Error';
                document.getElementById('cache-file-path').textContent = 'Error';
            }
        } catch (error) {
            console.error('Error loading cache stats:', error);
            document.getElementById('cache-count').textContent = 'Error';
            document.getElementById('cache-file-path').textContent = 'Error';
        }
    }

    async clearCache() {
        if (!confirm('キャッシュをクリアしますか？次回要約生成時に再作成されます。')) {
            return;
        }

        try {
            const response = await fetch('/api/web/cache/clear', {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                this.showNotification(data.message, 'success');
                await this.loadCacheStats(); // Refresh stats
            } else {
                this.showNotification(`キャッシュクリアに失敗しました: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error('Error clearing cache:', error);
            this.showNotification('キャッシュクリア中にエラーが発生しました', 'error');
        }
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new RemindMineApp();
});