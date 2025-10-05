# Railway Deployment Fix Guide

## Problems Fixed

### 1. `pip: command not found`
Railway's nixpacks builder couldn't find pip command during build.

### 2. `could not translate host name "postgres.railway.internal"`
Database connection attempted during BUILD phase, but database is only available during DEPLOY phase.

## Key Solution

**Migrations and collectstatic MUST run during deploy, NOT build.**

Build phase: Install dependencies only
Deploy phase: Run migrations, collectstatic, then start server

## Solution Options

### Option 1: Use start.sh Script (RECOMMENDED - Current Setup)

**Already configured!** The project now uses:

- `start.sh` - Startup script that runs migrations → collectstatic → gunicorn
- `railway.json` - Specifies build command (pip install) and start command (./start.sh)

**How it works:**
1. **Build phase:** Only installs dependencies (`pip install -r requirements.txt`)
2. **Deploy phase:** Runs `start.sh` which:
   - Migrates database (database IS available now)
   - Collects static files
   - Starts Gunicorn

**No changes needed - just push and deploy!**

### Option 2: Use Procfile Only (Alternative)

Railway auto-detects Python projects. Remove custom build configs and use Procfile:

1. **Delete or rename these files:**
   ```bash
   mv nixpacks.toml nixpacks.toml.backup
   mv railway.json railway.json.backup
   ```

2. **Keep only:**
   - `runtime.txt` (specifies Python version)
   - `requirements.txt` (dependencies)
   - `Procfile` (already configured correctly)

3. **Railway Settings:**
   - Build Command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
   - Start Command: (leave empty, uses Procfile)
   - Or use the start command from Procfile if needed

### Option 2: Use railway.json Build Command

If you prefer railway.json:

```json
{
  "$schema": "https://railway.app/railway.schema.json",
  "build": {
    "builder": "NIXPACKS",
    "buildCommand": "pip install --upgrade pip && pip install -r requirements.txt && python manage.py collectstatic --noinput"
  },
  "deploy": {
    "startCommand": "gunicorn mysite.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --threads 2 --worker-class gthread --worker-tmp-dir /dev/shm --access-logfile - --error-logfile - --log-level info --timeout 120",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

### Option 3: Railway UI Configuration (EASIEST)

**In Railway Dashboard:**

1. Go to your service → Settings
2. **Build Settings:**
   - Build Command: `pip install -r requirements.txt && python manage.py collectstatic --noinput`
3. **Deploy Settings:**
   - Start Command: `gunicorn mysite.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --threads 2`
4. Click "Deploy"

### Option 4: Fixed nixpacks.toml

If you must use nixpacks.toml:

```toml
[phases.setup]
nixPkgs = ["python311", "postgresql"]

[phases.install]
cmds = ["python -m pip install --upgrade pip", "python -m pip install -r requirements.txt"]

[start]
cmd = "gunicorn mysite.wsgi:application --bind 0.0.0.0:$PORT --workers 4"
```

**Note:** Remove the `[phases.build]` section - migrations should run via Procfile's `release` command.

## Why This Happened

Railway's nixpacks builder creates a Python environment, but the `pip` command wasn't in PATH. Using `python -m pip` explicitly calls pip through Python's module system, which always works.

## Recommended Deployment Steps

### Step 1: Clean Up Config Files

```bash
# Backup or remove conflicting configs
mv nixpacks.toml nixpacks.toml.backup
mv railway.json railway.json.backup
```

### Step 2: Verify Required Files

Ensure these files exist:

✅ `runtime.txt`:
```
python-3.11.9
```

✅ `requirements.txt`:
(already correct)

✅ `Procfile`:
```
web: gunicorn mysite.wsgi:application --bind 0.0.0.0:$PORT --workers 4 --threads 2 --worker-class gthread --worker-tmp-dir /dev/shm --access-logfile - --error-logfile - --log-level info --timeout 120
release: python manage.py migrate --noinput && python manage.py collectstatic --noinput
```

### Step 3: Railway Dashboard Configuration

1. **Environment Variables** (must be set):
   ```
   SECRET_KEY=<generate-random-50-char-string>
   DEBUG=False
   ALLOWED_HOSTS=your-app.railway.app
   DATABASE_URL=<auto-set-by-railway>
   REDIS_URL=<auto-set-by-railway>
   SITE_URL=https://your-app.railway.app
   EMAIL_HOST_USER=your-email@gmail.com
   EMAIL_HOST_PASSWORD=<app-password>
   DEFAULT_FROM_EMAIL=YourApp <noreply@yourdomain.com>
   ```

2. **Build Settings** (in Railway UI):
   - Build Command: `pip install -r requirements.txt`
   - Start Command: (leave empty to use Procfile)

3. **Deploy:**
   - Push to GitHub
   - Railway auto-deploys

### Step 4: Post-Deployment

```bash
# Access Railway shell and create admin
railway run python manage.py createsuperuser
```

## Generate SECRET_KEY

Run locally:
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

## Troubleshooting

### If build still fails:

1. **Check Railway Logs:**
   - Look for specific error messages
   - Verify Python version is detected

2. **Simplify Procfile:**
   ```
   web: gunicorn mysite.wsgi:application --bind 0.0.0.0:$PORT
   release: python manage.py migrate --noinput
   ```

3. **Use Railway CLI for testing:**
   ```bash
   railway login
   railway link
   railway run python manage.py check --deploy
   ```

### If migrations fail:

Set environment variable:
```
DISABLE_COLLECTSTATIC=1
```

Then run migrations manually after deployment:
```bash
railway run python manage.py migrate
railway run python manage.py collectstatic --noinput
```

## Best Practice: Minimal Configuration

**Recommended file structure:**
- `runtime.txt` → Python version
- `requirements.txt` → Dependencies
- `Procfile` → Start commands
- Railway UI → Build/Start commands
- **NO** nixpacks.toml (let Railway auto-detect)
- **NO** railway.json (unless you need advanced features)

## Final Checklist

- [ ] `runtime.txt` specifies Python 3.11.9
- [ ] `requirements.txt` contains all dependencies
- [ ] `Procfile` has web and release commands
- [ ] nixpacks.toml removed or backed up
- [ ] railway.json removed or uses buildCommand
- [ ] Environment variables set in Railway
- [ ] PostgreSQL service added
- [ ] Redis service added (if using Celery)
- [ ] Deploy triggered

## Support

If issues persist:
1. Check Railway's build logs
2. Verify all environment variables are set
3. Try deploying with minimal Procfile only
4. Contact Railway support with build logs

---

**Quick Fix:** Delete `nixpacks.toml` and `railway.json`, keep only `runtime.txt`, `requirements.txt`, and `Procfile`. Railway will auto-detect and deploy correctly.
