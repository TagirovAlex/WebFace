# WebFace v2.1 Release

## New Features
- **Swagger API** - API documentation at `/apidocs`
- **Progress Tracking** - Real-time progress 0-100% for generations
- **Public Galleries** - `/gallery`, `/user/<username>/gallery`
- **Generation Presets** - Save and reuse generation settings
- **Qwen Reference Images** - Proper enable/disable for 1-3 reference images
- **Module Auto-Scan** - Add new modules from admin panel
- **Telegram Notifications** - User notifications on generation complete

## New API Endpoints
- `/api/presets` - CRUD for presets
- `/api/admin/scan-modules` - Auto-register modules
- `/gallery` - Public gallery
- `/user/<name>/gallery` - User gallery

## Bug Fixes
- Qwen reference images properly disabled when not selected
- Multiple security improvements
- Better error handling

## Installation
```bash
pip install -r requirements.txt
python app.py
python create_admin.py
```

Then visit `/admin/generation-types` and click "Сканировать модули" to auto-register modules.