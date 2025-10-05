# EyeHealth 20-20-20 Railway Deployment Guide

This guide provides step-by-step instructions for deploying the EyeHealth 20-20-20 application to Railway.

## Prerequisites

- A Railway account (sign up at https://railway.app)
- Git repository with your code (GitHub, GitLab, or Bitbucket)
- Basic understanding of environment variables

## Required Services

For production deployment, you'll need:

1. **Web Service** - Django application
2. **PostgreSQL Database** - Primary data storage
3. **Redis** - Cache and Celery broker (optional but recommended)

## Deployment Steps

### 1. Create a New Railway Project

1. Log in to Railway: https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository

### 2. Add PostgreSQL Database

1. In your Railway project, click "New"
2. Select "Database" → "Add PostgreSQL"
3. Railway will automatically provision a PostgreSQL database
4. The `DATABASE_URL` environment variable will be automatically set

### 3. Add Redis (Optional but Recommended)

1. Click "New" → "Database" → "Add Redis"
2. Railway will automatically provision Redis
3. The `REDIS_URL` environment variable will be automatically set

### 4. Configure Environment Variables

In your Railway web service, add the following environment variables:

#### Required Environment Variables

```bash
# Django Secret Key - Generate with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'
SECRET_KEY=your-secret-key-here

# Debug Mode (MUST be False in production)
DEBUG=False

# Allowed Hosts (comma-separated, no spaces)
ALLOWED_HOSTS=your-app.railway.app

# Database URL (automatically set by Railway PostgreSQL)
DATABASE_URL=postgresql://...

# Redis URL (automatically set by Railway Redis, or use external)
REDIS_URL=redis://...
```

#### CORS Settings (if you have a frontend)

```bash
# CORS Allowed Origins (comma-separated, HTTPS only in production)
CORS_ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
CORS_ALLOW_CREDENTIALS=True
```

#### CSRF Settings

```bash
# CSRF Trusted Origins (comma-separated, must match your domains)
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

#### Email Configuration (Required for production)

```bash
# Email Backend
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend

# SMTP Configuration (example with Gmail)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-specific-password
DEFAULT_FROM_EMAIL=EyeHealth 20-20-20 <noreply@yourdomain.com>
```

**Note for Gmail:** You need to generate an App Password:
1. Enable 2-factor authentication on your Google account
2. Go to https://myaccount.google.com/apppasswords
3. Generate a new app password
4. Use this password in `EMAIL_HOST_PASSWORD`

#### Optional but Recommended

```bash
# Support Email
SUPPORT_EMAIL=support@yourdomain.com

# Sentry Error Tracking (optional)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

# Session Configuration
SESSION_COOKIE_AGE=86400

# Cache Version (increment to invalidate cache)
CACHE_VERSION=1

# Logging Level
LOG_LEVEL=INFO

# API Rate Limits
API_DEFAULT_RATE_LIMIT=100/h
API_AUTHENTICATED_RATE_LIMIT=1000/h
API_PREMIUM_RATE_LIMIT=5000/h
```

#### Calendar Integration (Optional)

```bash
# Google Calendar
GOOGLE_CALENDAR_CLIENT_ID=your-google-client-id
GOOGLE_CALENDAR_CLIENT_SECRET=your-google-client-secret
GOOGLE_CALENDAR_PROJECT_ID=your-google-project-id
GOOGLE_CALENDAR_REDIRECT_URI=https://your-app.railway.app/calendars/auth/google/callback/

# Microsoft Calendar
MICROSOFT_CALENDAR_CLIENT_ID=your-microsoft-client-id
MICROSOFT_CALENDAR_CLIENT_SECRET=your-microsoft-client-secret
MICROSOFT_CALENDAR_TENANT_ID=common
```

### 5. Deploy the Application

Railway will automatically deploy your application when you push to your repository.

#### Manual Deployment

You can also trigger a manual deployment:
1. Go to your Railway project
2. Click on your web service
3. Click "Deploy" in the top right

### 6. Run Database Migrations

After the first deployment, you need to run migrations:

1. In Railway, click on your web service
2. Go to the "Settings" tab
3. Under "Deploy", you'll see the Procfile configuration
4. Railway will automatically run the `release` command from Procfile:
   ```
   python manage.py migrate --noinput && python manage.py collectstatic --noinput
   ```

This happens automatically before each deployment.

### 7. Create a Superuser (Admin Account)

To create an admin account:

1. In Railway, go to your web service
2. Click on the "..." menu → "Shell"
3. Run:
   ```bash
   python manage.py createsuperuser
   ```
4. Follow the prompts to create your admin account

### 8. Verify Deployment

1. Visit your Railway app URL (e.g., `https://your-app.railway.app`)
2. Test the following:
   - Home page loads
   - Sign up works
   - Login works
   - Timer dashboard loads
   - Static files are served correctly
   - Admin panel works (`/admin/`)

### 9. Set Up Celery Workers (Optional)

If you need background tasks (email sending, analytics):

#### Option A: Railway Multiple Services

1. Create a new service in your Railway project
2. Use the same GitHub repository
3. In service settings, set a custom start command:
   ```bash
   celery -A mysite worker --loglevel=info --concurrency=2
   ```
4. Add another service for Celery Beat (scheduled tasks):
   ```bash
   celery -A mysite beat --loglevel=info --scheduler django_celery_beat.schedulers:DatabaseScheduler
   ```

#### Option B: Use Railway's One-Off Jobs

For now, you can run without Celery workers and use synchronous task execution.

## Post-Deployment Checklist

- [ ] Application loads without errors
- [ ] Static files (CSS, JS) are loading
- [ ] Database migrations completed successfully
- [ ] Admin panel accessible
- [ ] User registration and login working
- [ ] Email notifications working (test password reset)
- [ ] HTTPS is enforced (Railway does this automatically)
- [ ] Environment variables are properly set
- [ ] Error tracking configured (if using Sentry)
- [ ] CORS settings configured for your frontend
- [ ] CSRF settings configured
- [ ] Security headers are set (check with https://securityheaders.com)

## Monitoring and Maintenance

### View Logs

In Railway:
1. Click on your web service
2. Go to the "Logs" tab
3. Monitor application logs, errors, and requests

### Database Backups

Railway provides automatic backups for PostgreSQL:
1. Go to your PostgreSQL service
2. Click on "Backups" tab
3. Enable automatic backups

### Performance Monitoring

Monitor your application:
- Railway provides metrics (CPU, Memory, Network)
- Check response times in logs
- Use Sentry for error tracking (if configured)

### Scaling

Railway allows you to scale your application:
1. Click on your web service
2. Go to "Settings" → "Resources"
3. Adjust vCPU and RAM as needed

## Troubleshooting

### Common Issues

#### 1. Static Files Not Loading

**Problem:** CSS and images don't load after deployment.

**Solution:**
- Ensure `whitenoise` is in `requirements.txt`
- Check `STATIC_ROOT` is set in settings.py
- Verify `collectstatic` ran successfully in deployment logs
- Check middleware order (WhiteNoiseMiddleware should be after SecurityMiddleware)

#### 2. Database Connection Errors

**Problem:** Can't connect to database.

**Solution:**
- Verify `DATABASE_URL` environment variable is set
- Check PostgreSQL service is running in Railway
- Review database connection logs
- Ensure `psycopg2-binary` is in requirements.txt

#### 3. CSRF Token Errors

**Problem:** Forms show CSRF validation errors.

**Solution:**
- Add your Railway domain to `ALLOWED_HOSTS`
- Add your domain to `CSRF_TRUSTED_ORIGINS` (with `https://` prefix)
- Ensure `CSRF_COOKIE_SECURE=True` in production

#### 4. Email Not Sending

**Problem:** Password reset or notification emails not sending.

**Solution:**
- Verify all email environment variables are set
- Check email logs for errors
- Test SMTP credentials locally first
- For Gmail, ensure you're using an App Password, not your regular password

#### 5. Server Error (500)

**Problem:** Application shows 500 error.

**Solution:**
- Check Railway logs for the full error traceback
- Ensure `DEBUG=False` in production
- Verify all required environment variables are set
- Check database migrations have run
- Review Sentry for detailed error information (if configured)

#### 6. Redis Connection Errors (if using Celery)

**Problem:** Celery can't connect to Redis.

**Solution:**
- Verify `REDIS_URL` environment variable is set
- Check Redis service is running in Railway
- Ensure Celery workers are running (check logs)

### Getting Help

If you encounter issues:

1. **Check Railway Logs:** Most issues can be diagnosed from logs
2. **Review Django Documentation:** https://docs.djangoproject.com
3. **Check Railway Documentation:** https://docs.railway.app
4. **Search GitHub Issues:** Check if others had similar problems
5. **Contact Support:** support@yourdomain.com

## Updating the Application

To deploy updates:

1. Make changes to your code
2. Commit and push to your repository
3. Railway will automatically detect changes and redeploy
4. Migrations will run automatically via the `release` command

### Zero-Downtime Deployments

Railway provides zero-downtime deployments by default:
- New version is built while old version runs
- Traffic switches to new version when ready
- Old version is terminated

## Security Best Practices

1. **Never commit secrets** - Use environment variables
2. **Keep dependencies updated** - Run `pip list --outdated` regularly
3. **Monitor logs** - Check for suspicious activity
4. **Use strong SECRET_KEY** - Generate a new one for production
5. **Enable HTTPS only** - Railway does this automatically
6. **Set up Sentry** - Track errors in production
7. **Regular backups** - Enable Railway automatic backups
8. **Rate limiting** - Already configured via django-ratelimit
9. **CORS restrictions** - Only allow your domains
10. **Review security headers** - Check https://securityheaders.com

## Environment Variables Reference

Complete list of all environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | Yes | - | Django secret key for cryptographic signing |
| `DEBUG` | Yes | False | Debug mode (MUST be False in production) |
| `ALLOWED_HOSTS` | Yes | - | Comma-separated list of allowed hosts |
| `DATABASE_URL` | Yes | - | PostgreSQL connection URL (auto-set by Railway) |
| `REDIS_URL` | No | - | Redis connection URL (auto-set by Railway) |
| `EMAIL_BACKEND` | Yes | console | Email backend class |
| `EMAIL_HOST` | No* | smtp.gmail.com | SMTP server hostname |
| `EMAIL_PORT` | No | 587 | SMTP server port |
| `EMAIL_USE_TLS` | No | True | Use TLS for email |
| `EMAIL_HOST_USER` | No* | - | SMTP username |
| `EMAIL_HOST_PASSWORD` | No* | - | SMTP password |
| `DEFAULT_FROM_EMAIL` | No | - | Default from email address |
| `CORS_ALLOWED_ORIGINS` | No** | - | Comma-separated CORS allowed origins |
| `CORS_ALLOW_CREDENTIALS` | No | True | Allow CORS credentials |
| `CSRF_TRUSTED_ORIGINS` | No | - | Comma-separated CSRF trusted origins |
| `SUPPORT_EMAIL` | No | - | Support contact email |
| `SENTRY_DSN` | No | - | Sentry error tracking DSN |
| `SENTRY_ENVIRONMENT` | No | production | Sentry environment name |
| `SENTRY_TRACES_SAMPLE_RATE` | No | 0.1 | Sentry trace sampling rate |
| `LOG_LEVEL` | No | INFO | Logging level |
| `SESSION_COOKIE_AGE` | No | 86400 | Session cookie age in seconds |
| `CACHE_VERSION` | No | 1 | Cache version number |
| `GOOGLE_CALENDAR_CLIENT_ID` | No | - | Google Calendar OAuth client ID |
| `GOOGLE_CALENDAR_CLIENT_SECRET` | No | - | Google Calendar OAuth secret |
| `GOOGLE_CALENDAR_PROJECT_ID` | No | - | Google Cloud project ID |
| `GOOGLE_CALENDAR_REDIRECT_URI` | No | - | Google OAuth redirect URI |
| `MICROSOFT_CALENDAR_CLIENT_ID` | No | - | Microsoft Graph client ID |
| `MICROSOFT_CALENDAR_CLIENT_SECRET` | No | - | Microsoft Graph secret |
| `MICROSOFT_CALENDAR_TENANT_ID` | No | common | Microsoft tenant ID |

\* Required if using SMTP email backend in production
\** Required if you have a separate frontend application

## Cost Optimization

Railway pricing tips:

1. **Start with the Hobby plan** - $5/month for starter projects
2. **Monitor resource usage** - Check metrics regularly
3. **Scale workers as needed** - Don't run Celery workers if not needed
4. **Use database connection pooling** - Already configured
5. **Optimize queries** - Use database indexes (already implemented)
6. **Enable Redis only if needed** - For caching and Celery

## Further Resources

- [Railway Documentation](https://docs.railway.app)
- [Django Deployment Checklist](https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/)
- [PostgreSQL on Railway](https://docs.railway.app/databases/postgresql)
- [Redis on Railway](https://docs.railway.app/databases/redis)
- [Environment Variables](https://docs.railway.app/develop/variables)

---

**Last Updated:** October 2024
**Django Version:** 4.2.16
**Python Version:** 3.11+
