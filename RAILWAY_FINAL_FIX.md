# Railway Deployment - FINAL FIX

## Error You're Seeing

```
django.db.utils.OperationalError: could not translate host name "postgres.railway.internal"
to address: Name or service not known
```

**During:** BUILD phase (Dockerfile RUN command)

## Root Cause

Railway's **Nixpacks auto-detection** for Django projects automatically adds a build phase that runs:
```bash
python manage.py migrate --noinput && python manage.py collectstatic --noinput
```

**Problem:** Database is NOT available during BUILD phase, only during DEPLOY phase.

## The Fix - Applied ✅

Created `nixpacks.toml` that **explicitly prevents build phase**:

```toml
[phases.setup]
nixPkgs = ["python311", "postgresql"]

[phases.install]
cmds = ["pip install --upgrade pip", "pip install -r requirements.txt"]

# NO [phases.build] section - prevents auto-generated migrations
# Database operations happen in start.sh during DEPLOY phase

[start]
cmd = "./start.sh"
```

## How It Works Now

### BUILD Phase (Database NOT Available)
```
1. Setup Python 3.11 environment
2. Install dependencies from requirements.txt
3. ✅ Build complete (NO database operations)
```

### DEPLOY Phase (Database Available)
```
1. Execute start.sh:
   ├─ python manage.py migrate --noinput
   ├─ python manage.py collectstatic --noinput
   └─ gunicorn mysite.wsgi:application
2. ✅ App running
```

## Files in This Configuration

1. **`nixpacks.toml`** (NEW) - Prevents auto-build phase
2. **`start.sh`** - Runs migrations during deploy
3. **`railway.json`** - Build and deploy settings
4. **`Procfile`** - Alternative configuration (not used with nixpacks)
5. **`runtime.txt`** - Python 3.11.9
6. **`requirements.txt`** - Dependencies

## Deploy Steps

### 1. Commit and Push
```bash
git add .
git commit -m "Fix Railway build phase database error with nixpacks.toml"
git push origin main
```

### 2. Railway Configuration

**In Railway Dashboard:**

**Services to Add:**
- Web service (your GitHub repo)
- PostgreSQL database
- Redis database

**Environment Variables to Set:**
```bash
SECRET_KEY=<generate-random-string>
DEBUG=False
ALLOWED_HOSTS=your-app.railway.app
SITE_URL=https://your-app.railway.app
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=<app-password>
DEFAULT_FROM_EMAIL=YourApp <noreply@yourdomain.com>
```

**Generate SECRET_KEY:**
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

**Auto-Set by Railway:**
- `DATABASE_URL` (when you add PostgreSQL)
- `REDIS_URL` (when you add Redis)

### 3. Deploy

Railway auto-deploys when you push to GitHub.

**Watch the build logs - you should see:**
```
✓ Setup phase: Installing Python 3.11
✓ Install phase: pip install -r requirements.txt
✓ Build complete (no database operations)
✓ Deploy phase: Running start.sh
✓ Migrations complete
✓ Static files collected
✓ Gunicorn started
✓ Deployment successful
```

### 4. Create Admin User

```bash
# Railway Dashboard → Service → Shell
python manage.py createsuperuser
```

## Why This Works

**Before (ERROR):**
- Nixpacks auto-detected Django
- Added `[phases.build]` with migrations
- Tried to connect to database during build
- ❌ Database not available → ERROR

**After (SUCCESS):**
- Explicit `nixpacks.toml` configuration
- NO `[phases.build]` section
- Migrations run in `start.sh` during deploy
- ✅ Database IS available → SUCCESS

## Alternative: Without nixpacks.toml

If you prefer Railway auto-detection:

1. **Delete these files:**
   ```bash
   rm nixpacks.toml
   rm railway.json
   ```

2. **In Railway Dashboard → Service Settings:**
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `./start.sh`

3. **Push and deploy**

## Verification Checklist

After deployment succeeds:

- [ ] Build logs show NO database connection attempts during build
- [ ] Deploy logs show migrations running successfully
- [ ] Deploy logs show collectstatic running successfully
- [ ] App loads at `https://your-app.railway.app`
- [ ] Static files (CSS/JS) load correctly
- [ ] Can login/signup
- [ ] Admin panel works at `/admin/`
- [ ] No errors in Railway runtime logs

## Troubleshooting

### Build Still Fails with Database Error

**Check:**
1. `nixpacks.toml` exists in project root
2. `nixpacks.toml` has NO `[phases.build]` section
3. Railway is detecting `nixpacks.toml` (check build logs)

**Try:**
- Delete Railway service and recreate
- Clear Railway build cache (Settings → Clear Cache)
- Verify file permissions: `chmod +x start.sh`

### Migrations Run But Fail

**Check:**
1. PostgreSQL service is running
2. `DATABASE_URL` environment variable is set
3. No conflicting migrations in code

**Try:**
```bash
# Railway shell
python manage.py migrate --fake-initial
```

### Collectstatic Fails

**Check:**
1. `STATIC_ROOT` is set in settings.py
2. `static` directory exists
3. No database dependencies in static files

**Disable temporarily:**
```bash
# In start.sh, comment out collectstatic
# python manage.py collectstatic --noinput
```

## Success Indicators

✅ Build completes without database errors
✅ Migrations run during deploy (not build)
✅ Static files collected during deploy
✅ Gunicorn starts successfully
✅ App accessible via Railway URL
✅ No runtime errors in logs

## Cost Estimate

**Minimal:**
- Web: $5/month
- PostgreSQL: $5/month
- Redis: $5/month (optional)
- **Total: $10-15/month**

**With Celery:**
- + Worker: $5/month
- + Beat: $5/month
- **Total: $20-25/month**

## Support

- **Railway Docs:** https://docs.railway.app
- **Nixpacks Docs:** https://nixpacks.com
- **Django Deployment:** https://docs.djangoproject.com/en/4.2/howto/deployment/

## Summary

The fix is simple: **Prevent Nixpacks from running database operations during build.**

**Solution:** Explicit `nixpacks.toml` with no build phase + `start.sh` for deploy-time operations.

**Result:** Database operations run during DEPLOY when database IS available.

---

**Status:** ✅ Fixed and ready to deploy
**Next Step:** `git push origin main`
