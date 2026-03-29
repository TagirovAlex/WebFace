// ==================== GLOBAL VARIABLES ====================
let uploadedFiles = [];
const MAX_FILES = 3;
let pollIntervalId = null;

// ==================== INITIALIZATION ====================
document.addEventListener('DOMContentLoaded', () => {
    initModeSelector();
    initFileUpload();
    console.log('ComfyUI Web Interface initialized');
});

// ==================== MODE SELECTOR ====================
function initModeSelector() {
    document.querySelectorAll('.mode-card').forEach(card => {
        card.addEventListener('click', function() {
            // Remove active class from all cards
            document.querySelectorAll('.mode-card').forEach(c => c.classList.remove('active'));
            this.classList.add('active');
            
            // Hide all content areas
            document.querySelectorAll('.content-area').forEach(area => area.classList.remove('active'));
            
            // Show selected content area
            const mode = this.dataset.mode;
            const contentArea = document.getElementById(mode);
            if (contentArea) {
                contentArea.classList.add('active');
            }
            
            // Hide results
            document.getElementById('result-area').classList.remove('active');
        });
    });
}

// ==================== FILE UPLOAD ====================
function initFileUpload() {
    const uploadArea = document.getElementById('file-upload-area');
    if (!uploadArea) return;
    
    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });
    
    // Highlight drop area
    ['dragenter', 'dragover'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.classList.add('drag-over');
        });
    });
    
    ['dragleave', 'drop'].forEach(eventName => {
        uploadArea.addEventListener(eventName, () => {
            uploadArea.classList.remove('drag-over');
        });
    });
    
    // Handle dropped files
    uploadArea.addEventListener('drop', e => {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    });
}

function preventDefaults(e) {
    e.preventDefault();
    e.stopPropagation();
}

function handleFiles(files) {
    const previewArea = document.getElementById('preview-area');
    
    Array.from(files).forEach(file => {
        // Check file limit
        if (uploadedFiles.length >= MAX_FILES) {
            showToast(`Максимум ${MAX_FILES} файлов за раз`, 'warning');
            return;
        }
        
        // Check file type
        if (!file.type.startsWith('image/')) {
            showToast(`${file.name} не является изображением`, 'error');
            return;
        }
        
        // Check file size (10MB)
        if (file.size > 10 * 1024 * 1024) {
            showToast(`${file.name} превышает 10MB`, 'error');
            return;
        }
        
        // Add to array
        uploadedFiles.push(file);
        
        // Create preview
        const reader = new FileReader();
        reader.onload = e => {
            const div = document.createElement('div');
            div.className = 'preview-item';
            div.innerHTML = `
                <img src="${e.target.result}" alt="Preview">
                <button class="remove-btn" onclick="removeFile(${uploadedFiles.length - 1})" type="button">×</button>
            `;
            previewArea.appendChild(div);
            updateFileCount();
        };
        reader.readAsDataURL(file);
    });
}

function removeFile(index) {
    uploadedFiles.splice(index, 1);
    
    // Rebuild preview
    const previewArea = document.getElementById('preview-area');
    previewArea.innerHTML = '';
    
    uploadedFiles.forEach((file, i) => {
        const reader = new FileReader();
        reader.onload = e => {
            const div = document.createElement('div');
            div.className = 'preview-item';
            div.innerHTML = `
                <img src="${e.target.result}" alt="Preview">
                <button class="remove-btn" onclick="removeFile(${i})" type="button">×</button>
            `;
            previewArea.appendChild(div);
        };
        reader.readAsDataURL(file);
    });
    
    updateFileCount();
}

function updateFileCount() {
    const countElement = document.getElementById('file-count');
    if (countElement) {
        countElement.textContent = uploadedFiles.length;
    }
}

// ==================== DURATION SLIDER ====================
function updateDurationLabel() {
    const slider = document.getElementById('video-duration');
    const label = document.getElementById('duration-label');
    if (slider && label) {
        label.textContent = slider.value + ' сек';
    }
}

// ==================== GENERATION FUNCTIONS ====================

async function generateImage() {
    const prompt = document.getElementById('prompt-image').value.trim();
    const negativePrompt = document.getElementById('negative-prompt-image').value.trim();
    
    if (!prompt) {
        showToast('Пожалуйста, введите промпт', 'error');
        return;
    }
    
    showLoading('Генерация изображения...');
    
    try {
        const response = await fetch('/api/generate-image', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: prompt,
                negative_prompt: negativePrompt,
                model: 'wan22'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            pollGenerationStatus(data.generation_id, false);
        } else {
            throw new Error(data.error || 'Неизвестная ошибка');
        }
    } catch (error) {
        hideLoading();
        showToast('Ошибка: ' + error.message, 'error');
    }
}

async function generateVideo() {
    const prompt = document.getElementById('prompt-video').value.trim();
    const negativePrompt = document.getElementById('negative-prompt-video').value.trim();
    const duration = document.getElementById('video-duration').value;
    
    if (!prompt) {
        showToast('Пожалуйста, введите промпт', 'error');
        return;
    }
    
    showLoading('Генерация видео... Это займёт несколько минут');
    
    try {
        const response = await fetch('/api/generate-video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                prompt: prompt,
                negative_prompt: negativePrompt,
                model: 'wan22_video',
                duration: duration
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            pollGenerationStatus(data.generation_id, true);
        } else {
            throw new Error(data.error || 'Неизвестная ошибка');
        }
    } catch (error) {
        hideLoading();
        showToast('Ошибка: ' + error.message, 'error');
    }
}

async function editImages() {
    if (uploadedFiles.length === 0) {
        showToast('Загрузите хотя бы одно изображение', 'error');
        return;
    }
    
    const prompt = document.getElementById('edit-prompt').value.trim();
    const negativePrompt = document.getElementById('edit-negative').value.trim();
    
    if (!prompt) {
        showToast('Пожалуйста, опишите желаемые изменения', 'error');
        return;
    }
    
    showLoading(`Редактирование ${uploadedFiles.length} изображени${uploadedFiles.length > 1 ? 'й' : 'я'}...`);
    
    try {
        const formData = new FormData();
        
        uploadedFiles.forEach(file => {
            formData.append('images', file);
        });
        
        formData.append('edit_type', 'qwen');
        formData.append('prompt', prompt);
        formData.append('negative_prompt', negativePrompt);
        
        const response = await fetch('/api/edit-images', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            pollGenerationStatus(data.generation_id, false);
        } else {
            throw new Error(data.error || 'Неизвестная ошибка');
        }
    } catch (error) {
        hideLoading();
        showToast('Ошибка: ' + error.message, 'error');
    }
}

// ==================== STATUS POLLING ====================

async function pollGenerationStatus(generationId, isVideo = false) {
    let attempts = 0;
    const maxAttempts = isVideo ? 450 : 300; // 15 min for video, 10 min for images
    
    pollIntervalId = setInterval(async () => {
        attempts++;
        
        if (attempts > maxAttempts) {
            clearInterval(pollIntervalId);
            hideLoading();
            showToast('Превышено время ожидания. Проверьте историю позже.', 'error');
            return;
        }
        
        try {
            const response = await fetch(`/api/generation/${generationId}/status`);
            
            if (!response.ok) {
                throw new Error('Failed to fetch status');
            }
            
            const data = await response.json();
            
            if (data.status === 'completed') {
                clearInterval(pollIntervalId);
                hideLoading();
                displayResults(data.output_files, isVideo);
                showToast('Генерация завершена успешно!', 'success');
            } else if (data.status === 'failed') {
                clearInterval(pollIntervalId);
                hideLoading();
                showToast('Ошибка генерации: ' + (data.error_message || 'Неизвестная ошибка'), 'error');
            } else if (data.status === 'processing') {
                updateLoadingProgress(attempts, maxAttempts);
            }
        } catch (error) {
            console.error('Polling error:', error);
            // Don't stop polling on temporary errors
        }
    }, 2000); // Poll every 2 seconds
}

function updateLoadingProgress(current, max) {
    const progressElement = document.getElementById('loading-progress');
    if (!progressElement) return;
    
    const percent = Math.min((current / max) * 100, 100);
    const secondsElapsed = current * 2; // 2 seconds per poll
    const maxMinutes = Math.round((max * 2) / 60);
    
    progressElement.innerHTML = `
        <div style="width: 100%; background: #e0e0e0; border-radius: 4px; margin-top: 15px; overflow: hidden;">
            <div style="width: ${percent}%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                        height: 6px; transition: width 0.3s;"></div>
        </div>
        <p style="margin-top: 8px; font-size: 0.9em; color: #666;">
            ${Math.floor(secondsElapsed / 60)}:${String(secondsElapsed % 60).padStart(2, '0')} / ~${maxMinutes} мин макс
        </p>
    `;
}

// ==================== RESULTS DISPLAY ====================

function displayResults(files, isVideo = false) {
    const resultArea = document.getElementById('result-area');
    const resultContent = document.getElementById('result-content');
    
    if (!resultArea || !resultContent) return;
    
    resultContent.innerHTML = '';
    
    if (!files || files.length === 0) {
        resultContent.innerHTML = '<p style="text-align: center; color: #999; padding: 40px;">Нет результатов</p>';
        resultArea.classList.add('active');
        return;
    }
    
    files.forEach((filename, index) => {
        const div = document.createElement('div');
        div.className = 'result-item';
        
        if (isVideo) {
            div.innerHTML = `
                <video src="/results/${filename}" controls preload="metadata"></video>
                <div class="result-actions">
                    <a href="/results/${filename}" download class="btn btn-small btn-primary">
                        <span class="btn-icon">📥</span>
                        Скачать
                    </a>
                </div>
            `;
        } else {
            div.innerHTML = `
                <img src="/results/${filename}" alt="Result ${index + 1}" loading="lazy">
                <div class="result-actions">
                    <a href="/results/${filename}" download class="btn btn-small btn-primary">
                        <span class="btn-icon">📥</span>
                        Скачать
                    </a>
                </div>
            `;
        }
        
        resultContent.appendChild(div);
    });
    
    resultArea.classList.add('active');
    
    // Smooth scroll to results
    setTimeout(() => {
        resultArea.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 100);
}

function downloadAll() {
    const links = document.querySelectorAll('.result-item a[download]');
    links.forEach((link, index) => {
        setTimeout(() => {
            link.click();
        }, index * 500); // Delay between downloads
    });
}

// ==================== LOADING ====================

function showLoading(text = 'Загрузка...') {
    const loadingElement = document.getElementById('loading');
    const loadingText = document.getElementById('loading-text');
    const loadingProgress = document.getElementById('loading-progress');
    
    if (loadingText) {
        loadingText.textContent = text;
    }
    
    if (loadingProgress) {
        loadingProgress.innerHTML = '';
    }
    
    if (loadingElement) {
        loadingElement.classList.add('active');
    }
}

function hideLoading() {
    const loadingElement = document.getElementById('loading');
    if (loadingElement) {
        loadingElement.classList.remove('active');
    }
    
    if (pollIntervalId) {
        clearInterval(pollIntervalId);
        pollIntervalId = null;
    }
}

// ==================== TOAST NOTIFICATIONS ====================

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast-notification toast-${type}`;
    
    const icons = {
        success: '✓',
        error: '✗',
        warning: '⚠',
        info: 'ℹ'
    };
    
    const colors = {
        success: { bg: '#c6f6d5', color: '#276749' },
        error: { bg: '#fed7d7', color: '#c53030' },
        warning: { bg: '#fef3c7', color: '#92400e' },
        info: { bg: '#bee3f8', color: '#2c5282' }
    };
    
    const style = colors[type] || colors.info;
    
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 15px 20px;
        background: ${style.bg};
        color: ${style.color};
        border-radius: 8px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        z-index: 10000;
        max-width: 400px;
        font-weight: 500;
        animation: slideIn 0.3s ease;
        display: flex;
        align-items: center;
        gap: 10px;
    `;
    
    toast.innerHTML = `
        <span style="font-size: 1.2em;">${icons[type]}</span>
        <span>${message}</span>
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => {
            toast.remove();
        }, 300);
    }, 5000);
}

// Add animation styles
if (!document.getElementById('toast-animations')) {
    const style = document.createElement('style');
    style.id = 'toast-animations';
    style.textContent = `
        @keyframes slideIn {
            from { transform: translateX(400px); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(400px); opacity: 0; }
        }
    `;
    document.head.appendChild(style);
}