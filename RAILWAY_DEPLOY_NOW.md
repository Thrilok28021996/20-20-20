# 🚀 Deploy to Railway NOW - Quick Guide

## ✅ All Issues Fixed!

Your project is now **100% ready** for Railway deployment. Both errors have been resolved:

1. ✅ **pip command not found** - Fixed
2. ✅ **Database connection during build** - Fixed

## 🎯 Current Configuration

### Files Created/Updated:
- ✅ `start.sh` - Startup script (runs migrations in deploy phase)
- ✅ `railway.json` - Build/deploy configuration
- ✅ `runtime.txt` - Python 3.11.9
- ✅ `requirements.txt` - All dependencies
- ✅ `Procfile` - Process definitions

### How It Works:
```
BUILD PHASE (no database access):
└─ pip install -r requirements.txt

DEPLOY PHASE (database available):
├─ python manage.py migrate --noinput
├─ python manage.py collectstatic --noinput
└─ gunicorn mysite.wsgi:application (start server)
```

## 📋 Deploy Steps

### 1. Push to GitHub
```bash
git push origin main
```

### 2. Railway Setup

**A. Create Project:**
1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository
5. Click "Deploy Now"

**B. Add Databases:**
1. Click "+ New" → "Database" → "Add PostgreSQL"
2. Click "+ New" → "Database" → "Add Redis"

### 3. Set Environment Variables

In Railway Dashboard → Your Service → Variables tab, add:

```bash
# Required
SECRET_KEY=<generate-this>
DEBUG=False
ALLOWED_HOSTS=<your-app>.railway.app
SITE_URL=https://<your-app>.railway.app

# Email (Required for password reset, etc.)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=<app-password>
DEFAULT_FROM_EMAIL=YourApp <noreply@yourdomain.com>

# Optional but Recommended
SUPPORT_EMAIL=support@yourdomain.com
LOG_LEVEL=INFO
```

**Generate SECRET_KEY locally:**
```bash
python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
```

**Note:** `DATABASE_URL` and `REDIS_URL` are auto-set by Railway when you add the databases.

### 4. Deploy

Railway auto-deploys on every push to main. Watch the logs:

```
Railway Dashboard → Deployments → View Logs
```

You should see:
```
✓ Installing dependencies...
✓ Running database migrations...
✓ Collecting static files...
✓ Starting Gunicorn server...
✓ Deployment successful
```

### 5. Create Admin User

Once deployed, access Railway shell:

```bash
# In Railway Dashboard
Settings → Deploy → "Run Command"

# Or use Railway CLI
railway run python manage.py createsuperuser
```

## ✅ Post-Deployment Checklist

- [ ] App loads at `https://<your-app>.railway.app`
- [ ] Static files load correctly (CSS/JS)
- [ ] User signup works
- [ ] User login works
- [ ] Password reset email sends
- [ ] Admin panel accessible at `/admin/`
- [ ] No errors in Railway logs
- [ ] Database migrations completed

## 🔧 If You Need Celery Workers

Celery workers handle background tasks (emails, analytics).

**Add Worker Service:**
1. Railway Dashboard → "+ New" → "Empty Service"
2. Link to same GitHub repo
3. Settings → Start Command:
   ```
   celery -A mysite worker --loglevel=info --concurrency=2
   ```
4. Use same environment variables as web service
5. Deploy

**Add Celery Beat (Scheduled Tasks):**
1. Railway Dashboard → "+ New" → "Empty Service"
2. Start Command:
   ```
   celery -A mysite beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
   ```

## 🐛 Troubleshooting

### Build Fails
- Check Railway logs for specific error
- Verify `requirements.txt` is valid
- Ensure `runtime.txt` specifies Python 3.11.9

### Database Connection Error
- Verify PostgreSQL service is added
- Check `DATABASE_URL` is set (should be automatic)
- Migrations should run during deploy, NOT build

### Static Files Not Loading
- Check `ALLOWED_HOSTS` includes your Railway domain
- Verify `STATIC_ROOT` and `STATIC_URL` in settings.py
- Check Railway logs for collectstatic output

### Migrations Fail
- Check database credentials
- Verify PostgreSQL service is running
- Check for migration conflicts

## 📊 Cost Estimate

### Minimal Setup:
- Web service: $5/month
- PostgreSQL: $5/month
- Redis: $5/month (optional if not using Celery)
- **Total: ~$10-15/month**

### With Celery:
- Add $5 for worker
- Add $5 for beat
- **Total: ~$20-25/month**

**Note:** Railway offers free trial credits for testing.

## 📚 Resources

- Full guide: `DEPLOYMENT.md`
- Troubleshooting: `RAILWAY_FIX.md`
- Railway docs: https://docs.railway.app
- Django deployment: https://docs.djangoproject.com/en/4.2/howto/deployment/

## 🎉 Success!

Your app is configured correctly. Just:
1. `git push origin main`
2. Add databases in Railway
3. Set environment variables
4. Watch it deploy!

---

**Current Status:** ✅ Ready to deploy
**Configuration:** ✅ Complete
**Documentation:** ✅ Complete
**Next Step:** Push to GitHub and deploy!
