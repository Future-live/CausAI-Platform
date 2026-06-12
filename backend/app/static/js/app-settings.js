(function () {
    const STORAGE_KEY = 'causai:ui-settings';

    const themes = {
        light: {
            zh: '经典蓝',
            en: 'Classic Blue',
            noteZh: '保持当前系统默认风格。',
            noteEn: 'Keeps the current default appearance.',
            vars: {
                '--sidebar-bg': '#273c75',
                '--content-bg': '#ffffff',
                '--button-bg': '#273c75',
                '--table-header-bg': '#273c75',
                '--text-color': '#ffffff',
                '--body-bg': '#f4f4f9',
                '--upload-button-bg': '#1e2b52',
                '--search-button-bg': '#1e2b52'
            }
        },
        ocean: {
            zh: '深海蓝',
            en: 'Deep Ocean',
            noteZh: '更清爽的专业蓝，适合长时间数据分析。',
            noteEn: 'A calmer analytical blue for long working sessions.',
            vars: {
                '--sidebar-bg': '#1d4e89',
                '--content-bg': '#ffffff',
                '--button-bg': '#2563eb',
                '--table-header-bg': '#1d4e89',
                '--text-color': '#ffffff',
                '--body-bg': '#f3f7fb',
                '--upload-button-bg': '#173b66',
                '--search-button-bg': '#173b66'
            }
        },
        emerald: {
            zh: '松石绿',
            en: 'Emerald Lab',
            noteZh: '偏研究工作台气质，稳定、清晰、不过度跳脱。',
            noteEn: 'A composed research-workbench palette with strong clarity.',
            vars: {
                '--sidebar-bg': '#165a4a',
                '--content-bg': '#ffffff',
                '--button-bg': '#21886c',
                '--table-header-bg': '#1f7661',
                '--text-color': '#ffffff',
                '--body-bg': '#f2f8f5',
                '--upload-button-bg': '#12483b',
                '--search-button-bg': '#12483b'
            }
        },
        graphite: {
            zh: '石墨灰',
            en: 'Graphite',
            noteZh: '更克制的中性主题，适合展示和报告场景。',
            noteEn: 'A restrained neutral theme for demos and reporting.',
            vars: {
                '--sidebar-bg': '#1f2937',
                '--content-bg': '#ffffff',
                '--button-bg': '#334155',
                '--table-header-bg': '#334155',
                '--text-color': '#ffffff',
                '--body-bg': '#f3f5f8',
                '--upload-button-bg': '#111827',
                '--search-button-bg': '#111827'
            }
        },
        ruby: {
            zh: '玫瑰红',
            en: 'Ruby Insight',
            noteZh: '更有强调感的分析主题，适合汇报和重点洞察场景。',
            noteEn: 'A sharper insight palette for presentations and highlighted findings.',
            vars: {
                '--sidebar-bg': '#6f1d46',
                '--content-bg': '#ffffff',
                '--button-bg': '#a72f62',
                '--table-header-bg': '#893057',
                '--text-color': '#ffffff',
                '--body-bg': '#fff5f8',
                '--upload-button-bg': '#5a173a',
                '--search-button-bg': '#5a173a'
            }
        }
    };

    const labels = {
        zh: {
            settingsTitle: '显示设置',
            settingsIntro: '调整语言、主题和主色调。默认主题会保持当前系统风格不变。',
            language: '界面语言',
            theme: '主题方案',
            accent: '主色调',
            preview: '主题预览',
            apply: '保存设置',
            clear: '清理临时缓存',
            restore: '恢复默认',
            profile: '账号信息',
            system: '系统信息',
            signOut: '退出登录',
            saved: '设置已保存',
            previewing: '正在预览，点击保存后长期生效',
            restored: '已恢复默认设置',
            cacheCleared: '临时缓存已清理',
            systemInfo: 'CausAI 数据分析与因果推断平台 · 本地部署版本',
            profileText: '已打开个人信息页',
            note: '英文模式会同步调整侧栏、用户菜单和设置面板文案。',
            nav: {
                'index.html': '主页',
                'data-upload.html': '数据上传',
                'data-preparation.html': '数据准备',
                'statistical-analysis.html': '统计分析',
                'causal-analysis.html': '数据驱动因果',
                'big-model-analysis.html': '语义理解因果',
                'favorites.html': '收藏夹',
                'profile.html': '个人信息',
                'logout.html': '退出系统'
            },
            online: '在线'
        },
        en: {
            settingsTitle: 'Display Settings',
            settingsIntro: 'Tune language, theme, and accent color. The default theme preserves the current product style.',
            language: 'Language',
            theme: 'Theme',
            accent: 'Accent',
            preview: 'Theme Preview',
            apply: 'Save Settings',
            clear: 'Clear Temporary Cache',
            restore: 'Restore Default',
            profile: 'Account',
            system: 'System Info',
            signOut: 'Sign Out',
            saved: 'Settings saved',
            previewing: 'Previewing now. Save to keep these settings.',
            restored: 'Default settings restored',
            cacheCleared: 'Temporary cache cleared',
            systemInfo: 'CausAI Data Analytics and Causal Inference Platform · Local deployment',
            profileText: 'Opening account profile',
            note: 'English mode also adapts sidebar, user menu, and settings labels.',
            nav: {
                'index.html': 'Home',
                'data-upload.html': 'Upload Data',
                'data-preparation.html': 'Data Preparation',
                'statistical-analysis.html': 'Statistics',
                'causal-analysis.html': 'Causal Discovery',
                'big-model-analysis.html': 'Semantic Causality',
                'favorites.html': 'Favorites',
                'profile.html': 'Profile',
                'logout.html': 'Sign Out'
            },
            online: 'Online'
        }
    };

    function readSettings() {
        try {
            return normalizeSettings({ language: 'zh', theme: 'light', accent: '#273c75', ...JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') });
        } catch (error) {
            return { language: 'zh', theme: 'light', accent: '#273c75' };
        }
    }

    function writeSettings(settings) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    }

    function normalizeSettings(settings) {
        const theme = themes[settings.theme] ? settings.theme : 'light';
        const language = settings.language === 'en' ? 'en' : 'zh';
        const accent = settings.accent || themes[theme].vars['--button-bg'];
        return { language, theme, accent };
    }

    function applyTheme(settings) {
        const nextSettings = normalizeSettings(settings);
        const theme = themes[nextSettings.theme] || themes.light;
        Object.entries(theme.vars).forEach(([key, value]) => {
            document.documentElement.style.setProperty(key, value);
        });
        if (nextSettings.accent && nextSettings.accent !== theme.vars['--button-bg']) {
            document.documentElement.style.setProperty('--sidebar-bg', nextSettings.accent);
            document.documentElement.style.setProperty('--button-bg', nextSettings.accent);
            document.documentElement.style.setProperty('--table-header-bg', nextSettings.accent);
            document.documentElement.style.setProperty('--upload-button-bg', nextSettings.accent);
            document.documentElement.style.setProperty('--search-button-bg', nextSettings.accent);
        }
        document.documentElement.lang = nextSettings.language === 'en' ? 'en' : 'zh-CN';
        document.body.classList.toggle('lang-en', nextSettings.language === 'en');
    }

    function currentLabels(settings) {
        return labels[settings.language === 'en' ? 'en' : 'zh'];
    }

    function showToast(message) {
        const old = document.querySelector('.settings-toast');
        if (old) {
            old.remove();
        }
        const toast = document.createElement('div');
        toast.className = 'settings-toast';
        toast.textContent = message;
        document.body.appendChild(toast);
        window.setTimeout(() => toast.remove(), 1800);
    }

    function translateNavigation(settings) {
        const lang = currentLabels(settings);
        document.querySelectorAll('.sidebar a[href]').forEach(link => {
            const href = link.getAttribute('href') || '';
            const key = Object.keys(lang.nav).find(item => href.endsWith(item));
            const span = link.querySelector('span');
            if (key && span) {
                span.textContent = lang.nav[key];
            }
        });
        const role = document.querySelector('.user-role');
        if (role) {
            const roleName = role.textContent.split('·')[0].trim() || 'user';
            role.textContent = `${roleName} · ${lang.online}`;
        }
        const menuLabels = [
            ['.user-dropdown a[href$="profile.html"] span', lang.profile],
            ['.user-menu-settings span', lang.settingsTitle],
            ['.user-dropdown a[href$="logout.html"] span', lang.signOut]
        ];
        menuLabels.forEach(([selector, text]) => {
            const node = document.querySelector(selector);
            if (node) {
                node.textContent = text;
            }
        });
    }

    function optionHtml(settings) {
        const lang = currentLabels(settings);
        return Object.entries(themes).map(([key, theme]) => {
            const text = settings.language === 'en' ? theme.en : theme.zh;
            return `<option value="${key}" ${settings.theme === key ? 'selected' : ''}>${text}</option>`;
        }).join('');
    }

    function renderPreview(settings) {
        const theme = themes[settings.theme] || themes.light;
        const lang = currentLabels(settings);
        const swatches = [
            theme.vars['--sidebar-bg'],
            settings.accent || theme.vars['--button-bg'],
            theme.vars['--body-bg'],
            theme.vars['--content-bg']
        ];
        const note = settings.language === 'en' ? theme.noteEn : theme.noteZh;
        return `
            <div class="theme-preview">
                <div class="theme-preview-title">${lang.preview}</div>
                <div class="theme-swatches">
                    ${swatches.map(color => `<span class="theme-swatch" style="background:${color}"></span>`).join('')}
                </div>
                <div class="settings-note">${note}</div>
            </div>
        `;
    }

    function renderSettingsPanel(settings) {
        const lang = currentLabels(settings);
        return `
            <span class="close" data-settings-close>&times;</span>
            <div class="settings-panel">
                <div class="settings-hero">
                    <h2>${lang.settingsTitle}</h2>
                    <p>${lang.settingsIntro}</p>
                </div>
                <div class="settings-grid">
                    <section class="settings-section">
                        <div class="settings-field">
                            <label for="language-select">${lang.language}</label>
                            <select id="language-select">
                                <option value="zh" ${settings.language === 'zh' ? 'selected' : ''}>中文</option>
                                <option value="en" ${settings.language === 'en' ? 'selected' : ''}>English</option>
                            </select>
                        </div>
                        <div class="settings-field">
                            <label for="theme-select">${lang.theme}</label>
                            <select id="theme-select">${optionHtml(settings)}</select>
                        </div>
                        <div class="settings-field">
                            <label for="color-select">${lang.accent}</label>
                            <input type="color" id="color-select" value="${settings.accent || themes[settings.theme].vars['--button-bg']}">
                        </div>
                        <p class="settings-note">${lang.note}</p>
                    </section>
                    <section class="settings-section" id="theme-preview-wrap">
                        ${renderPreview(settings)}
                    </section>
                </div>
                <div class="settings-actions">
                    <button class="primary" id="settings-save">${lang.apply}</button>
                    <button id="clear-cache">${lang.clear}</button>
                    <button id="restore-defaults">${lang.restore}</button>
                    <button id="view-account">${lang.profile}</button>
                    <button id="view-system-info">${lang.system}</button>
                    <button id="logout">${lang.signOut}</button>
                </div>
            </div>
        `;
    }

    function collectPanelSettings() {
        const theme = document.getElementById('theme-select')?.value || 'light';
        const themeAccent = themes[theme]?.vars['--button-bg'] || '#273c75';
        return {
            language: document.getElementById('language-select')?.value || 'zh',
            theme,
            accent: document.getElementById('color-select')?.value || themeAccent
        };
    }

    function refreshPanel(settings) {
        const modalContent = document.querySelector('#settings-modal .modal-content');
        if (!modalContent) {
            return;
        }
        modalContent.classList.add('settings-enhanced');
        modalContent.innerHTML = renderSettingsPanel(settings);
        bindPanelEvents();
    }

    function bindPanelEvents() {
        const modal = document.getElementById('settings-modal');
        const close = document.querySelector('[data-settings-close]');
        const language = document.getElementById('language-select');
        const theme = document.getElementById('theme-select');
        const color = document.getElementById('color-select');

        if (close && modal) {
            close.addEventListener('click', () => {
                modal.style.display = 'none';
            });
        }

        if (language) {
            language.addEventListener('change', () => {
                const settings = collectPanelSettings();
                applyTheme(settings);
                translateNavigation(settings);
                refreshPanel(settings);
                showToast(currentLabels(settings).previewing);
            });
        }

        if (theme) {
            theme.addEventListener('change', () => {
                const chosenTheme = theme.value || 'light';
                const settings = {
                    ...collectPanelSettings(),
                    theme: chosenTheme,
                    accent: themes[chosenTheme]?.vars['--button-bg'] || '#273c75'
                };
                applyTheme(settings);
                translateNavigation(settings);
                refreshPanel(settings);
                showToast(currentLabels(settings).previewing);
            });
        }

        if (color) {
            color.addEventListener('input', () => {
                const settings = collectPanelSettings();
                applyTheme(settings);
                translateNavigation(settings);
                const preview = document.getElementById('theme-preview-wrap');
                if (preview) {
                    preview.innerHTML = renderPreview(settings);
                }
            });
            color.addEventListener('change', () => {
                showToast(currentLabels(collectPanelSettings()).previewing);
            });
        }

        document.getElementById('settings-save')?.addEventListener('click', () => {
            const settings = collectPanelSettings();
            writeSettings(settings);
            applyTheme(settings);
            translateNavigation(settings);
            showToast(currentLabels(settings).saved);
        });

        document.getElementById('restore-defaults')?.addEventListener('click', () => {
            const settings = { language: 'zh', theme: 'light', accent: '#273c75' };
            writeSettings(settings);
            applyTheme(settings);
            translateNavigation(settings);
            refreshPanel(settings);
            showToast(labels.zh.restored);
        });

        document.getElementById('clear-cache')?.addEventListener('click', () => {
            sessionStorage.removeItem('causai:favoriteChart');
            showToast(currentLabels(collectPanelSettings()).cacheCleared);
        });

        document.getElementById('view-account')?.addEventListener('click', () => {
            showToast(currentLabels(collectPanelSettings()).profileText);
            window.location.href = 'profile.html';
        });

        document.getElementById('view-system-info')?.addEventListener('click', () => {
            showToast(currentLabels(collectPanelSettings()).systemInfo);
        });

        document.getElementById('logout')?.addEventListener('click', () => {
            window.location.href = 'logout.html';
        });
    }

    function bindModalOpeners() {
        const modal = document.getElementById('settings-modal');
        const settingsButton = document.getElementById('settings-button');
        if (!modal || !settingsButton) {
            return;
        }
        settingsButton.addEventListener('click', event => {
            event.preventDefault();
            event.stopPropagation();
            refreshPanel(readSettings());
            modal.style.display = 'block';
        });
        window.addEventListener('click', event => {
            if (event.target === modal) {
                modal.style.display = 'none';
            }
        });
    }

    function init() {
        const settings = readSettings();
        applyTheme(settings);
        translateNavigation(settings);
        if (document.getElementById('settings-modal')) {
            refreshPanel(settings);
            bindModalOpeners();
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
