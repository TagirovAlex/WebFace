document.addEventListener('DOMContentLoaded', () => {
    const themeToggle = document.getElementById('theme-toggle');
    const body = document.body;

    // Переключение темы
    themeToggle.addEventListener('click', () => {
        body.classList.toggle('dark-theme');
        themeToggle.innerHTML = body.classList.contains('dark-theme') 
            ? '☀️' 
            : '🌃';
    });

    // Загрузка сохраненной темы
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        body.classList.add('dark-theme');
        themeToggle.innerHTML = '☀️';
    } else {
        body.classList.remove('dark-theme');
        themeToggle.innerHTML = '🌃';
    }

    // Сохранение темы при изменении
    body.addEventListener('click', (e) => {
        if (e.target === themeToggle) {
            localStorage.setItem('theme', body.classList.contains('dark-theme') ? 'dark' : 'light');
        }
    });
});