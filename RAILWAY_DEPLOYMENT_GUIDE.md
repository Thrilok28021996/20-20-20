# Railway Deployment Guide for 20-20-20 Django App

## Prerequisites
1. Railway account (sign up at railway.app)
2. GitHub repository with your code
3. Railway CLI installed (optional but recommended)

## Step 1: Create Railway Project

### Option A: Deploy from GitHub (Recommended)
1. Go to railway.app and click "New Project"
2. Select "Deploy from GitHub repo"
3. Connect your GitHub account and select this repository
4. Railway will automatically detect it's a Django project

### Option B: Deploy with Railway CLI
```bash
# Install Railway CLI
npm install -g @railway/cli

# Login to Railway
railway login

# Initialize project
railway init

# Deploy
railway up
```

## Step 2: Add Required Services

### PostgreSQL Database
1. In your Railway dashboard, click "New Service"
2. Select "PostgreSQL"
3. This will automatically set the `DATABASE_URL` environment variable

### Redis (Optional, for Celery)
1. In your Railway dashboard, click "New Service"
2. Select "Redis"
3. This will automatically set the `REDIS_URL` environment variable

## Step 3: Set Environment Variables

Go to your Railway project settings → Variables and add these:

### Required Variables
```
SECRET_KEY=your-django-secret-key-here
DEBUG=False
ALLOWED_HOSTS=your-app-name.railway.app
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com
CSRF_TRUSTED_ORIGINS=https://your-app-name.railway.app
```

### Security Variables
```
SECURE_SSL_REDIRECT=True
SECURE_BROWSER_XSS_FILTER=True
SECURE_CONTENT_TYPE_NOSNIFF=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
```

### Optional Variables (if using these features)
```
# Email
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-email-password

# Stripe Payments
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PRICE_ID=price_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Google Calendar
GOOGLE_CALENDAR_CLIENT_ID=your-google-client-id
GOOGLE_CALENDAR_CLIENT_SECRET=your-google-client-secret
GOOGLE_CALENDAR_PROJECT_ID=your-google-project-id
GOOGLE_CALENDAR_REDIRECT_URI=https://your-app-name.railway.app/calendars/auth/google/callback/
```

## Step 4: Configure Domain (Optional)

1. In Railway dashboard, go to Settings → Domains
2. Add your custom domain
3. Update `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` to include your domain

## Step 5: Deploy

Railway will automatically deploy when you push to your connected GitHub branch.

### Manual Deployment
If using Railway CLI:
```bash
railway up
```

## Step 6: Run Migrations

After deployment, run database migrations:

### Option A: Using Railway CLI
```bash
railway run python manage.py migrate
railway run python manage.py collectstatic --noinput
railway run python manage.py createsuperuser
```

### Option B: Using Railway Dashboard
1. Go to your service in Railway dashboard
2. Click on "Deployments" tab
3. Click on the latest deployment
4. Use the "Command" feature to run:
   - `python manage.py migrate`
   - `python manage.py collectstatic --noinput`
   - `python manage.py createsuperuser`

## Important Notes

### Static Files
- Static files are handled by WhiteNoise (already configured)
- No additional setup needed for static files

### Database
- Railway PostgreSQL is automatically configured via `DATABASE_URL`
- Your Django settings already support this via `dj-database-url`

### Logging
- Logs are available in Railway dashboard under your service
- Application logs are configured to output to stdout/stderr

### Environment Variables
- Reference Railway services using `${{ServiceName.VARIABLE_NAME}}`
- Example: `${{Postgres.DATABASE_URL}}` for PostgreSQL URL

### Health Checks
- Your app includes a `/health/` endpoint
- Railway will automatically monitor this for health checks

## Troubleshooting

### Common Issues

1. **Static files not loading**
   - Ensure `STATIC_ROOT` is set correctly
   - Run `python manage.py collectstatic --noinput`

2. **Database connection errors**
   - Verify PostgreSQL service is running
   - Check `DATABASE_URL` environment variable

3. **CORS issues**
   - Update `CORS_ALLOWED_ORIGINS` with your frontend domain
   - Update `CSRF_TRUSTED_ORIGINS` with your Railway domain

4. **SSL redirect issues**
   - Ensure `SECURE_SSL_REDIRECT=True` only in production
   - Check that Railway provides HTTPS

### Viewing Logs
```bash
railway logs
```

Or view them in the Railway dashboard under your service.

## Next Steps

1. Set up monitoring and alerts
2. Configure backup strategy for PostgreSQL
3. Set up CI/CD pipeline for automated testing before deployment
4. Configure custom domain with SSL
5. Set up Redis for Celery tasks (if needed)

## Cost Optimization

- Railway offers $5/month credit on hobby plan
- Use sleep mode for development environments
- Monitor resource usage in dashboard
- Scale workers based on traffic