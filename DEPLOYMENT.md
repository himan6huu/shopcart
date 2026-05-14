# 🚀 ShopCart — Deployment Guide

## Step 1: Push to GitHub

```bash
cd shop_deploy
git init
git add .
git commit -m "Initial commit — ShopCart v3"
```

Go to https://github.com/new → create a new repo, then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/shopcart.git
git branch -M main
git push -u origin main
```

---

## Step 2: Deploy on Render (Free)

1. Go to https://render.com and sign up (use GitHub login)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repo
4. Fill in these settings:
   - **Name**: shopcart
   - **Runtime**: Python
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Click **"Advanced"** → **"Add Environment Variable"**:
   - Key: `SECRET_KEY` → Value: (any long random string e.g. `my-super-secret-key-12345`)
6. Click **"New +"** → **"PostgreSQL"** → create a free database named `shopcart-db`
7. Go back to your web service → Environment → add:
   - Key: `DATABASE_URL` → Value: (paste the Internal Database URL from your PostgreSQL service)
8. Click **"Create Web Service"**

Render will build and deploy automatically. Your site will be live at:
`https://shopcart.onrender.com`

---

## Environment Variables Required

| Variable | Description |
|---|---|
| `SECRET_KEY` | Any long random string for session security |
| `DATABASE_URL` | PostgreSQL connection string (auto-set by Render) |

---

## Admin Login (after deploy)
- URL: https://your-app.onrender.com/admin
- Email: admin@shopcart.com
- Password: admin123

**Change the admin password after first login!**

---

## Local Development
```bash
pip install -r requirements.txt
python app.py
# → http://127.0.0.1:5000
```
SQLite is used automatically when DATABASE_URL is not set.
