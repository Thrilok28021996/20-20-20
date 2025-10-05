# Docker Deployment to Railway

## Why Docker Instead of Nixpacks?

### Problems with Nixpacks:
- ❌ Auto-generates Dockerfile with unpredictable behavior
- ❌ Procfile `release:` command runs during BUILD (wrong phase)
- ❌ Hard to debug what's actually happening
- ❌ Config priority unclear (Procfile vs nixpacks.toml vs railway.json)

### Benefits of Docker:
- ✅ **Complete control** over build process
- ✅ **Explicit** - you see exactly what runs when
- ✅ **Predictable** - same behavior locally and on Railway
- ✅ **Industry standard** - works everywhere
- ✅ **Easy to debug** - just read the Dockerfile

---

## Configuration Files

### 1. `Dockerfile` (Production)
Multi-stage build for optimized image:
- **Builder stage:** Installs dependencies with build tools
- **Production stage:** Copies only runtime dependencies
- **Security:** Runs as non-root user
- **Size:** Smaller final image (~200MB vs ~500MB)

### 2. `docker-compose.yml` (Local Development)
Complete local environment:
- Web server (Django)
- PostgreSQL database
- Redis cache
- Celery worker
- Celery beat scheduler

### 3. `.env.docker` (Local Environment Template)
Template for local development variables.

### 4. `railway.json` (Railway Config)
```json
{
  "build": {
    "builder": "DOCKERFILE"
  }
}
```

---

## Deployment Process

### BUILD Phase (Dockerfile):
```dockerfile
# 1. Install system dependencies
RUN apt-get install libpq-dev

# 2. Install Python dependencies
RUN pip install -r requirements.txt

# 3. Copy application code
COPY . /app/

# ✅ NO migrations, NO collectstatic during build!
```

### DEPLOY Phase (start.sh):
```bash
# 1. Run migrations (database IS available)
python manage.py migrate --noinput

# 2. Collect static files
python manage.py collectstatic --noinput

# 3. Start Gunicorn
gunicorn mysite.wsgi:application
```

---

## Railway Deployment Steps

### 1. Push Code to GitHub
```bash
git add .
git commit -m "Switch to Docker deployment"
git push origin main
```

### 2. Railway Configuration

**In Railway Dashboard:**

1. **Create New Project** → Deploy from GitHub
2. **Add Services:**
   - PostgreSQL database
   - Redis database

3. **Environment Variables:**
   ```bash
   SECRET_KEY=<generate-random-50-chars>
   DEBUG=False
   ALLOWED_HOSTS=your-app.railway.app
   SITE_URL=https://your-app.railway.app

   # Email
   EMAIL_HOST_USER=your-email@gmail.com
   EMAIL_HOST_PASSWORD=<app-password>
   DEFAULT_FROM_EMAIL=YourApp <noreply@yourdomain.com>

   # CORS (set your actual domain)
   CORS_ALLOWED_ORIGINS=https://yourdomain.com

   # Auto-set by Railway when you add services:
   DATABASE_URL=<auto-set>
   REDIS_URL=<auto-set>
   ```

4. **Deploy Settings:**
   - Builder: Dockerfile (auto-detected from railway.json)
   - Root Directory: /
   - Dockerfile Path: Dockerfile

### 3. Deploy
Railway auto-deploys when you push to GitHub.

**Build logs will show:**
```
✓ Building Docker image...
✓ Installing system dependencies
✓ Installing Python dependencies
✓ Copying application code
✓ Creating non-root user
✓ Build complete
```

**Deploy logs will show:**
```
✓ Running ./start.sh
✓ Running database migrations...
✓ Collecting static files...
✓ Starting Gunicorn server...
✓ Deployment successful
```

### 4. Create Admin User
```bash
# In Railway Dashboard → Service → Shell
python manage.py createsuperuser
```

---

## Local Development with Docker

### First Time Setup:
```bash
# 1. Copy environment template
cp .env.docker .env

# 2. Update .env with your values
# Edit SECRET_KEY, EMAIL settings, etc.

# 3. Build and start all services
docker-compose up --build
```

### Daily Development:
```bash
# Start services
docker-compose up

# Or run in background
docker-compose up -d

# View logs
docker-compose logs -f web

# Stop services
docker-compose down

# Run migrations
docker-compose exec web python manage.py migrate

# Create superuser
docker-compose exec web python manage.py createsuperuser

# Run Django shell
docker-compose exec web python manage.py shell

# Run tests
docker-compose exec web pytest
```

### Useful Commands:
```bash
# Rebuild after requirements.txt changes
docker-compose build

# Remove all data (fresh start)
docker-compose down -v

# View running containers
docker-compose ps

# Access database directly
docker-compose exec db psql -U postgres -d eyehealth

# Access Redis CLI
docker-compose exec redis redis-cli
```

---

## File Structure

```
your-project/
├── Dockerfile              # Production Docker image
├── docker-compose.yml      # Local development setup
├── .env.docker            # Environment template
├── .dockerignore          # Files to exclude from build
├── railway.json           # Railway configuration
├── start.sh              # Startup script
├── requirements.txt      # Python dependencies
├── runtime.txt           # Python version (for reference)
└── mysite/
    └── settings.py       # Django settings
```

---

## Advantages of This Setup

### 1. **Consistency**
- Same Docker image locally and in production
- "Works on my machine" actually means it works in production

### 2. **Simplicity**
- One Dockerfile defines everything
- No magic auto-detection
- Clear separation: BUILD vs DEPLOY

### 3. **Flexibility**
- Easy to add system dependencies
- Easy to customize build process
- Easy to optimize image size

### 4. **Debuggability**
- Read Dockerfile to understand what happens
- Test locally with `docker build`
- No hidden auto-generated files

### 5. **Portability**
- Works on Railway
- Works on Render, Fly.io, DigitalOcean, AWS, etc.
- Standard Docker = works everywhere

---

## Troubleshooting

### Build Fails
```bash
# Test build locally
docker build -t myapp .

# Check specific stage
docker build --target builder -t myapp-builder .
```

### Start Fails
```bash
# Run container interactively
docker run -it --rm myapp /bin/bash

# Check start script
docker run -it --rm myapp cat /app/start.sh
```

### Permission Issues
```bash
# The Dockerfile creates 'appuser' for security
# If you need to debug as root:
docker run -it --rm --user root myapp /bin/bash
```

### Database Connection
```bash
# Check DATABASE_URL is set correctly
docker run --rm -e DATABASE_URL=$DATABASE_URL myapp env | grep DATABASE_URL

# Test database connection
docker-compose exec web python manage.py dbshell
```

---

## Optimization Tips

### Reduce Image Size:
```dockerfile
# Already implemented:
- Multi-stage build (removes build tools from final image)
- Slim Python image (python:3.11-slim vs python:3.11)
- Clean apt cache (rm -rf /var/lib/apt/lists/*)
- Non-root user (security + smaller layer)
```

### Faster Builds:
```dockerfile
# Copy requirements.txt first (layer caching)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy code last (changes most frequently)
COPY . /app/
```

### Security:
```dockerfile
# Already implemented:
- Non-root user
- No unnecessary packages
- Latest security patches (apt-get update)
- No secrets in image
```

---

## Environment Variables Reference

### Required:
```bash
SECRET_KEY              # Django secret (50+ random chars)
DEBUG                   # False in production
ALLOWED_HOSTS          # your-app.railway.app
DATABASE_URL           # Auto-set by Railway PostgreSQL
SITE_URL              # https://your-app.railway.app
```

### Email (Required for features):
```bash
EMAIL_HOST_USER        # your-email@gmail.com
EMAIL_HOST_PASSWORD    # Gmail app password
DEFAULT_FROM_EMAIL     # Display name <email>
```

### Optional but Recommended:
```bash
REDIS_URL             # Auto-set by Railway Redis
CORS_ALLOWED_ORIGINS  # Frontend domains (HTTPS only in prod)
SUPPORT_EMAIL         # Support contact
LOG_LEVEL            # INFO or DEBUG
SENTRY_DSN           # Error tracking
```

---

## Verification Checklist

After deployment:

- [ ] Build logs show Docker image built successfully
- [ ] No migrations during build phase
- [ ] Deploy logs show migrations running
- [ ] Deploy logs show collectstatic running
- [ ] App loads at Railway URL
- [ ] Static files (CSS/JS) load correctly
- [ ] User signup works
- [ ] User login works
- [ ] Password reset email sends
- [ ] Admin panel accessible at `/admin/`
- [ ] No errors in Railway logs

---

## Cost Estimate

Same as before:
- Web service: $5/month
- PostgreSQL: $5/month
- Redis: $5/month
- **Total: $15/month**

With Celery workers: Add $10/month

---

## Support Resources

- **Railway Docs:** https://docs.railway.app/deploy/dockerfiles
- **Docker Docs:** https://docs.docker.com/
- **Django Docker:** https://docs.djangoproject.com/en/4.2/howto/deployment/
- **Compose Docs:** https://docs.docker.com/compose/

---

## Summary

### Before (Nixpacks):
- ❌ Unpredictable auto-generation
- ❌ Hard to debug
- ❌ Procfile conflicts

### After (Docker):
- ✅ Complete control
- ✅ Easy to understand
- ✅ Works everywhere
- ✅ Industry standard

**Status:** ✅ Ready to deploy with Docker

**Next step:** `git push origin main`
