# EyeHealth 20-20-20 SaaS Deployment Guide

## Overview

EyeHealth 20-20-20 is a comprehensive SaaS application built with Django that helps users protect their vision by implementing the 20-20-20 rule: every 20 minutes, look at something 20 feet away for 20 seconds.

## Features

### ✅ Core Features Implemented
- **User Authentication**: Custom user model with email login
- **20-20-20 Timer**: Interactive timer with 20-minute intervals
- **Break Reminders**: Visual, audio, and browser notifications
- **Statistics Dashboard**: Daily, weekly, and monthly analytics
- **Subscription Management**: Freemium model with Pro/Enterprise tiers
- **Payment Integration**: Stripe integration for subscriptions
- **Responsive Design**: Mobile-friendly Bootstrap 5 interface
- **Admin Panel**: Comprehensive Django admin interface

### 🎯 User Flow
1. **Registration**: Sign up with email and password
2. **Onboarding**: Set preferences and work schedule
3. **Timer Sessions**: Start 20-minute work intervals
4. **Break Notifications**: Get reminded to take eye breaks
5. **Progress Tracking**: View statistics and compliance rates
6. **Upgrade Options**: Access premium features with subscriptions

## Technical Architecture

### Backend
- **Framework**: Django 4.2.16
- **Database**: SQLite (development) / PostgreSQL (production)
- **Task Queue**: Celery with Redis
- **Authentication**: Custom User model with email
- **API**: Django REST Framework
- **Payments**: Stripe integration

### Frontend
- **Framework**: Bootstrap 5.3.2
- **Icons**: Font Awesome 6.4.0
- **JavaScript**: Vanilla JS with modern ES6+
- **Styling**: Custom CSS with CSS variables
- **Responsive**: Mobile-first design

### Apps Structure
```
mysite/                 # Main Django project
├── accounts/           # User authentication and profiles
├── timer/              # Timer functionality and sessions
├── analytics/          # Statistics and reporting
├── notifications/      # Email and push notifications
├── subscriptions/      # Payment and subscription management
└── templates/          # Global templates
```

## Installation & Setup

### Prerequisites
- Python 3.11+
- Redis (for Celery)
- PostgreSQL (for production)

### Development Setup
```bash
# Clone repository
git clone <repository-url>
cd 20-20-20

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Collect static files
python manage.py collectstatic

# Run development server
python manage.py runserver
```

### Environment Variables
Create a `.env` file in the project root:

```env
# Django Settings
SECRET_KEY=your-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database (Production)
DATABASE_URL=postgresql://user:password@host:port/dbname

# Email Configuration
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Celery Configuration
REDIS_URL=redis://localhost:6379/0

# Stripe Configuration
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

## Database Schema

### Key Models

#### User Model (`accounts.User`)
- Custom user with email authentication
- Subscription information
- Notification preferences
- Work schedule settings

#### Timer Models (`timer`)
- `TimerSession`: Work sessions
- `TimerInterval`: 20-minute intervals
- `BreakRecord`: Break compliance tracking
- `UserTimerSettings`: Personal preferences

#### Subscription Models (`subscriptions`)
- `SubscriptionPlan`: Available plans
- `UserSubscription`: Active subscriptions
- `Invoice`: Billing records
- `PaymentMethod`: Stored payment info

#### Analytics Models (`analytics`)
- `DailyStats`: Daily usage statistics
- `WeeklyReport`: Weekly summaries
- Performance metrics and compliance rates

## API Endpoints

### Authentication
- `POST /accounts/login/` - User login
- `POST /accounts/signup/` - User registration
- `POST /accounts/logout/` - User logout

### Timer Operations
- `POST /timer/start-session/` - Start new timer session
- `POST /timer/end-session/` - End current session
- `POST /timer/take-break/` - Record break start
- `POST /timer/complete-break/` - Complete break

### Statistics
- `GET /analytics/daily-stats/` - Daily statistics
- `GET /analytics/weekly-report/` - Weekly reports
- `GET /analytics/monthly-summary/` - Monthly summaries

### Subscriptions
- `GET /subscriptions/plans/` - Available plans
- `POST /subscriptions/create/` - Create subscription
- `POST /subscriptions/cancel/` - Cancel subscription

## Deployment Options

### 1. Heroku Deployment

```bash
# Install Heroku CLI
heroku create eyehealth-20-20-20

# Configure environment variables
heroku config:set SECRET_KEY=your-secret-key
heroku config:set DEBUG=False
heroku config:set STRIPE_PUBLISHABLE_KEY=pk_live_...
heroku config:set STRIPE_SECRET_KEY=sk_live_...

# Add PostgreSQL
heroku addons:create heroku-postgresql:basic

# Add Redis
heroku addons:create heroku-redis:mini

# Deploy
git push heroku main

# Run migrations
heroku run python manage.py migrate
heroku run python manage.py createsuperuser
heroku run python manage.py collectstatic --noinput
```

### 2. Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "mysite.wsgi:application"]
```

### 3. VPS Deployment (Ubuntu/Nginx)

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install python3-pip python3-venv nginx postgresql postgresql-contrib redis-server

# Create user and setup project
sudo useradd -m -s /bin/bash eyehealth
sudo su - eyehealth
git clone <repository-url>
cd 20-20-20

# Setup Python environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Configure PostgreSQL
sudo -u postgres createuser --interactive eyehealth
sudo -u postgres createdb eyehealth_db

# Configure Nginx
sudo nano /etc/nginx/sites-available/eyehealth
sudo ln -s /etc/nginx/sites-available/eyehealth /etc/nginx/sites-enabled/
sudo systemctl reload nginx

# Setup Systemd service
sudo nano /etc/systemd/system/eyehealth.service
sudo systemctl enable eyehealth
sudo systemctl start eyehealth
```

## Production Configuration

### Security Settings
```python
# settings.py (Production)
DEBUG = False
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']

# Security Headers
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Database
DATABASES = {
    'default': dj_database_url.parse(os.environ.get('DATABASE_URL'))
}

# Static Files
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
```

### Celery Configuration
```python
# celery.py
from celery import Celery
from django.conf import settings
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mysite.settings')

app = Celery('eyehealth')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# Periodic tasks
from celery.schedules import crontab

app.conf.beat_schedule = {
    'send-daily-summaries': {
        'task': 'notifications.tasks.send_daily_summaries',
        'schedule': crontab(hour=18, minute=0),  # 6 PM daily
    },
    'send-weekly-reports': {
        'task': 'analytics.tasks.generate_weekly_reports',
        'schedule': crontab(day_of_week=0, hour=9, minute=0),  # Sunday 9 AM
    },
}
```

## Monitoring & Maintenance

### Health Checks
- `/admin/` - Django admin interface
- Database connectivity check
- Redis connectivity check
- Celery worker status
- Static file serving

### Backup Strategy
- Daily database backups
- Weekly full system backups
- Stripe webhook backup logs
- User data export capabilities

### Performance Optimization
- Database query optimization
- Redis caching for sessions
- CDN for static files
- Image optimization
- JavaScript minification

## Marketing & Business Model

### Freemium Model
- **Free Tier**: 5 sessions/day, basic statistics
- **Pro Tier ($9.99/month)**: Unlimited sessions, advanced analytics, custom messages
- **Enterprise Tier ($49.99/month)**: Team management, API access, white-labeling

### Target Market
- Remote workers and digital professionals
- Students spending long hours on computers
- Companies focused on employee wellness
- Healthcare organizations promoting eye health

### Growth Strategy
- Content marketing about digital eye strain
- Integration with popular productivity tools
- Corporate wellness program partnerships
- Referral program for users

## Support & Documentation

### User Documentation
- Getting started guide
- Feature tutorials
- Troubleshooting guide
- API documentation

### Admin Documentation
- User management
- Subscription handling
- Analytics interpretation
- System maintenance

## Version History

### v1.0.0 (Current)
- ✅ User authentication system
- ✅ 20-20-20 timer functionality
- ✅ Break reminder notifications
- ✅ Statistics and analytics
- ✅ Subscription management
- ✅ Responsive web design
- ✅ Admin interface

### Future Roadmap
- [ ] Mobile apps (iOS/Android)
- [ ] Browser extension
- [ ] Integration with calendar apps
- [ ] Team collaboration features
- [ ] Advanced eye health tracking
- [ ] AI-powered personalized recommendations

## Contact & Support

- **Documentation**: [docs.eyehealth2020.com](https://docs.eyehealth2020.com)
- **Support Email**: support@eyehealth2020.com
- **GitHub Issues**: [github.com/eyehealth2020/issues](https://github.com/eyehealth2020/issues)
- **Status Page**: [status.eyehealth2020.com](https://status.eyehealth2020.com)

---

**Built with ❤️ for healthier vision**