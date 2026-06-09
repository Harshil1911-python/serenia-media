# Serenia Media

A professional, secure media-sharing platform built with Python Flask. Share images, videos, audio, documents, and more with a beautiful white & sky-blue UI.

---

## Features

- **File Upload** — Drag & drop multi-file uploads with progress bars
- **All File Types** — Images, Video, Audio, PDF, Documents, Archives, Text, Code
- **Secure Sharing** — Expiring links, access limits, QR codes
- **File Preview** — In-browser preview for images, video, audio, PDF, text
- **Text Snippets** — Create and share copyable code/text snippets
- **Favorites** — Star files for quick access
- **Search & Filter** — Instant search by name, tag, type, date
- **Activity Timeline** — Full history of uploads, downloads, shares
- **Storage Analytics** — Per-user quotas with visual usage bars
- **Dark Mode** — Toggleable light/dark theme
- **Admin Panel** — User management, storage cleanup, system logs

---

## Local Setup

### 1. Clone and install

```bash
git clone https://github.com/yourname/serenia-media.git
cd serenia-media
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your settings
```

Minimum `.env` for local dev (SQLite):

```
SECRET_KEY=change-this-to-a-random-string
FLASK_ENV=development
```

### 3. Run

```bash
python app.py
```

Visit `http://localhost:5000`. The first registered user becomes admin.

---

## Deploy to Render

### Option A — One-click with render.yaml

1. Push repo to GitHub
2. Go to [render.com](https://render.com) → New → Blueprint
3. Connect your repo — Render reads `render.yaml` automatically
4. It creates a PostgreSQL DB and web service for you
5. Set any extra env vars (MAIL_*, etc.) in the Render dashboard

### Option B — Manual

1. Create a **PostgreSQL** database on Render, copy the connection string
2. Create a **Web Service** → Python → connect your repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn app:app --workers 2 --timeout 120 --bind 0.0.0.0:$PORT`
5. Add environment variables:
   - `DATABASE_URL` — your PostgreSQL connection string
   - `SECRET_KEY` — a long random string
   - `FLASK_ENV` — `production`

### Database migrations

```bash
flask db init
flask db migrate -m "initial"
flask db upgrade
```

Or just let `app.py` call `db.create_all()` on startup (default behavior).

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `SECRET_KEY` | ✅ | — | Flask secret key |
| `DATABASE_URL` | ✅ | SQLite (dev) | PostgreSQL connection string |
| `FLASK_ENV` | — | `development` | `production` or `development` |
| `MAX_CONTENT_LENGTH` | — | `104857600` | Max upload size in bytes (100MB) |
| `UPLOAD_FOLDER` | — | `static/uploads` | Where files are stored |
| `MAIL_SERVER` | — | `smtp.gmail.com` | SMTP server |
| `MAIL_USERNAME` | — | — | SMTP username |
| `MAIL_PASSWORD` | — | — | SMTP app password |

---

## Project Structure

```
serenia-media/
├── app.py                 # App factory, extensions, error handlers
├── config.py              # Config classes (dev/prod/test)
├── requirements.txt
├── render.yaml            # Render deployment blueprint
├── .env.example
│
├── models/
│   ├── __init__.py        # db, login_manager
│   ├── user.py            # User model
│   └── file.py            # File, Share, TextSnippet, Favorite, Activity
│
├── routes/
│   ├── __init__.py        # Blueprint definitions
│   ├── auth.py            # Register, login, logout, password reset
│   ├── main.py            # Dashboard, search, snippets, favorites
│   ├── files.py           # Upload, download, share, preview, manage
│   ├── admin.py           # Admin panel, user management, storage cleanup
│   └── api.py             # JSON API endpoints
│
├── static/
│   ├── css/main.css       # Complete design system
│   ├── js/main.js         # UI interactions, toasts, modals
│   └── uploads/           # Uploaded files (gitignored)
│
└── templates/
    ├── base.html           # Sidebar layout + public layout
    ├── auth/               # Login, register, profile, password reset
    ├── main/               # Dashboard, search, snippets, activity, favorites
    ├── files/              # Upload, list, detail, shared, shares
    ├── admin/              # Dashboard, users, files, logs
    └── errors/             # 403, 404, 410, 413, 500
```

---

## Security

- Passwords hashed with Werkzeug (PBKDF2-SHA256)
- CSRF protection on all forms (Flask-WTF)
- File type validation on upload (extension + MIME)
- Secure filename handling (werkzeug.utils.secure_filename)
- Unique token-based share links (secrets.token_urlsafe)
- Session management via Flask-Login
- Admin-only routes protected by decorator

---

## Admin Panel

The **first registered user** is automatically made admin. Access the admin panel at `/admin`.

Admin features:
- View all users, enable/disable, delete
- View all files across all users
- System activity logs
- **Clean Storage** — removes soft-deleted files and expired share links
- **Delete All Media** — requires typing `DELETE ALL MEDIA` to confirm

---

## License

MIT
