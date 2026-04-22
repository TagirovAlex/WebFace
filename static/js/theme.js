document.addEventListener('DOMContentLoaded', () => {
    const themeToggle = document.getElementById('theme-toggle');
    const body = document.body;

    if (!themeToggle) return;

    const updateIcon = (isDark) => {
        themeToggle.textContent = isDark ? '☀️' : '🌙';
    };

    // Переключение темы
    themeToggle.addEventListener('click', async () => {
        const currentTheme = body.classList.contains('dark-theme') ? 'dark-theme' : 'light';
        const newTheme = currentTheme === 'dark-theme' ? 'light' : 'dark-theme';

        try {
            const response = await fetch('/api/theme', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({theme: newTheme})
            });

            const data = await response.json();
            if (data.success) {
                body.classList.toggle('dark-theme');
                updateIcon(newTheme === 'dark');
            }
        } catch (err) {
            console.error('Failed to save theme:', err);
            // Fallback to localStorage
            localStorage.setItem('theme', newTheme);
            body.classList.toggle('dark-theme');
            updateIcon(newTheme === 'dark');
        }
    });

    // Инициализация - синхронизация с сервером при загрузке
    fetch('/api/theme')
        .then(r => r.json())
        .then(data => {
            if (data.success && data.theme === 'dark-theme') {
                body.classList.add('dark-theme');
            }
            updateIcon(data.theme === 'dark');
        })
        .catch(() => {
            // Fallback: localStorage
            const saved = localStorage.getItem('theme');
            if (saved === 'dark-theme') {
                body.classList.add('dark-theme');
            }
            updateIcon(saved === 'dark');
        });
});