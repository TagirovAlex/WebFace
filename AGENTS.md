# WebFace - Agent Instructions

## Project Overview
Flask web interface for ComfyUI (AI image/video generation). Users can generate images, videos, and edit images through a web UI that communicates with a ComfyUI backend.

## Run Commands
```bash
python app.py          # Start dev server (port 5000)
python create_admin.py # Create admin user
```

## Working with Tasks
- See `TODO.md` for all tasks, priorities, and status
- After completing a task: update TODO.md status and verify the project compiles
- Use `python -m py_compile app.py models.py config.py` to verify syntax

## Required Setup
1. Copy `.env.example` to `.env`
2. Configure `SECRET_KEY` (min 32 chars) and `COMFY_URL` (default: `http://127.0.0.1:8188`)
3. Run `python create_admin.py` to create first admin user
4. Ensure ComfyUI is running at the configured URL
5. Run migration: `python migrate_db.py --backup`

## Database Migration
The `migrate_db.py` script handles upgrades from v1.x to v2.0:

**What it adds:**
- `token_balances` - User token balances
- `token_transactions` - Transaction history
- `pricing` - Generation pricing per module
- `token_rules` - Automatic token allocation rules
- `users.priority` - User priority (25/50/75/100)
- `users.token_period` - Token reset period (daily/weekly/monthly)
- `generations.hidden_from_user` - Hidden generation flag

**Usage:**
```bash
python migrate_db.py --status        # Show current status
python migrate_db.py --dry-run       # Preview changes
python migrate_db.py --backup        # Backup and migrate
python migrate_db.py --reset-db      # Reset database (WARNING!)
```

## Key Architecture
- **Database**: SQLite (default), switch to PostgreSQL via `DATABASE_URL` env var
- **Models**: `User` (id, username, email, password_hash, is_admin, theme), `Generation`, `GenerationType`
- **Modules**: `modules/` folder with modular generation types
- **Workflows**: JSON files in `workflows/` or inside modules
- **First registered user** automatically becomes admin
- **Generation types**: Can be toggled on/off via admin panel (`/admin/generation-types`)

## Module System
Modules in `modules/` folder:
- `modules/__init__.py` - BaseModule class, ModuleRegistry
- Each module: `__init__.py` with module class + `workflow.json`

Add new module:
1. Create folder `modules/<type>/`
2. Create `__init__.py` with module class extending BaseModule
3. Copy workflow JSON as `workflow.json`
4. Register with `@register_module('id', 'type', 'category')`

## Important Routes
| Route | Description |
|-------|-------------|
| `/` | Main generation UI |
| `/login`, `/register`, `/logout` | Auth |
| `/admin` | Admin dashboard |
| `/api/generate-image` | Text-to-image |
| `/api/generate-video` | Text-to-video |
| `/api/edit-images` | Image editing (multipart) |

## Security Features
- CSRF protection via Flask-WTF
- Rate limiting (Flask-Limiter): 200/day, 50/hour default
- Password hashing with Bcrypt
- Secure session cookies
- File upload validation (MIME type + magic bytes)
- Path traversal protection

## Env Variables
| Variable | Default | Notes |
|----------|---------|-------|
| SECRET_KEY | auto-generated | REQUIRED for production |
| COMFY_URL | http://127.0.0.1:8188 | ComfyUI API endpoint |
| FLASK_ENV | development | Set to "production" for prod |
| DATABASE_URL | sqlite:///webface.db | PostgreSQL supported |

## Testing
- Uses in-memory SQLite when `FLASK_ENV=testing`
- CSRF disabled in test config

## Active Tasks
See `TODO.md` for the current task list with priorities and status tracking.
