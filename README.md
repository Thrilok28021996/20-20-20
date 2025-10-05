# 20-20-20 Eye Health SaaS Application

A Django-based web application that helps users follow the 20-20-20 rule to reduce eye strain: Every 20 minutes, look at something 20 feet away for 20 seconds.

## Features

- ⏰ **Smart Timer** - Customizable work and break intervals
- 📊 **Analytics Dashboard** - Track your eye health progress
- 🎯 **Gamification** - Achievements, badges, and challenges
- 📧 **Email Notifications** - Break reminders and reports
- 📅 **Calendar Integration** - Google Calendar and Microsoft Calendar
- 🎨 **Customizable Themes** - Personalize your experience
- 📈 **Advanced Analytics** - Daily, weekly, and monthly stats
- 💪 **Eye Exercises** - Guided exercises during breaks
- 🏆 **Streak Tracking** - Build healthy habits

## Tech Stack

- **Backend:** Django 4.2.16
- **Database:** PostgreSQL (production) / SQLite (development)
- **Cache:** Redis
- **Task Queue:** Celery
- **API:** Django REST Framework
- **Frontend:** Bootstrap 5, JavaScript
- **Authentication:** Django Auth with Token Authentication

## Project Structure

```
20-20-20/
├── accounts/           # User authentication and profiles
├── timer/              # Timer functionality and breaks
├── analytics/          # Statistics and analytics
├── notifications/      # Email and notification system
├── subscriptions/      # Subscription management (currently unused)
├── calendars/          # Calendar integrations
├── mysite/             # Main Django project settings
├── templates/          # HTML templates
├── static/             # CSS, JavaScript, images
├── logs/               # Application logs
├── manage.py           # Django management script
└── requirements.txt    # Python dependencies
```

## Installation

### Prerequisites

- Python 3.11+
- PostgreSQL (for production)
- Redis (for caching and Celery)

### Setup

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd 20-20-20
   ```

2. **Create virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

5. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser:**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run development server:**
   ```bash
   python manage.py runserver
   ```

Visit `http://localhost:8000` to access the application.

## Environment Variables

Key environment variables in `.env`:

```env
# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DATABASE_URL=sqlite:///db.sqlite3  # or PostgreSQL URL

# Redis
REDIS_URL=redis://localhost:6379/0

# Email
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Security
CORS_ALLOWED_ORIGINS=http://localhost:3000

# Calendar Integration (optional)
GOOGLE_CALENDAR_CLIENT_ID=
GOOGLE_CALENDAR_CLIENT_SECRET=
MICROSOFT_CALENDAR_CLIENT_ID=
MICROSOFT_CALENDAR_CLIENT_SECRET=
```

See `.env.example` for full configuration options.

## Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=.

# Run specific test file
pytest accounts/tests.py
```

## Running Celery (Background Tasks)

```bash
# Start Celery worker
celery -A mysite worker -l info

# Start Celery beat (scheduler)
celery -A mysite beat -l info
```

## Admin Interface

Access the Django admin at `http://localhost:8000/admin/`

Features:
- User management
- Timer session monitoring
- Analytics review
- Badge and achievement management
- Challenge creation

## API Documentation

The application provides a REST API for timer and analytics functionality.

### Authentication

```bash
# Get token
POST /api/auth/token/
{
  "username": "user@example.com",
  "password": "password"
}

# Use token in requests
Authorization: Token <your-token>
```

### Timer Endpoints

- `GET /timer/api/sessions/` - List timer sessions
- `POST /timer/api/sessions/start/` - Start new session
- `POST /timer/api/sessions/stop/` - Stop current session
- `GET /timer/api/breaks/` - List break records

### Analytics Endpoints

- `GET /analytics/api/daily-stats/` - Daily statistics
- `GET /analytics/api/weekly-stats/` - Weekly statistics
- `GET /analytics/api/dashboard/` - Dashboard metrics

## Adding Payment Integration

Currently, all features are free. To add payment functionality:

1. See `HOW_TO_ADD_DODO_PAYMENTS.md` for complete integration guide
2. Choose your payment provider (Stripe, PayPal, etc.)
3. Follow the 13-step implementation guide

## Deployment

### Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Configure PostgreSQL database
- [ ] Set up Redis for caching
- [ ] Configure email backend (SMTP)
- [ ] Set strong `SECRET_KEY`
- [ ] Configure `ALLOWED_HOSTS`
- [ ] Set up HTTPS (SSL certificate)
- [ ] Configure static file serving (WhiteNoise)
- [ ] Set up Celery workers
- [ ] Configure error monitoring (optional: Sentry)

### Deployment Platforms

The application can be deployed to:
- **Railway** - Use `Procfile` for configuration
- **Heroku** - Compatible with Heroku buildpacks
- **DigitalOcean** - Use Docker or direct deployment
- **AWS** - EC2, ECS, or Elastic Beanstalk
- **Google Cloud** - App Engine or Compute Engine

## Security Features

- ✅ CSRF protection enabled
- ✅ Content Security Policy (CSP)
- ✅ Brute force protection (django-axes)
- ✅ Rate limiting on API endpoints
- ✅ Secure password hashing
- ✅ HTTPS enforcement in production
- ✅ SQL injection protection (Django ORM)
- ✅ XSS protection
- ✅ Session security

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## Development Tips

### Database Reset

```bash
# Delete database
rm db.sqlite3

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### Debugging

- Set `DEBUG=True` in `.env`
- Check logs in `logs/django.log`
- Use Django Debug Toolbar (optional)
- Access debug endpoint: `/csrf-debug/`

### Performance

- Enable Redis caching in production
- Use PostgreSQL instead of SQLite
- Configure Celery for background tasks
- Optimize static file serving

## File Guide

### Essential Files

**Root Configuration:**
- `manage.py` - Django management script
- `requirements.txt` - Python dependencies
- `.env` - Environment variables (create from `.env.example`)
- `.env.example` - Environment variables template
- `.gitignore` - Git ignore rules
- `conftest.py` - Pytest configuration
- `pytest.ini` - Pytest settings
- `Procfile` - Process file for deployment

**Documentation:**
- `README.md` - This file
- `HOW_TO_ADD_DODO_PAYMENTS.md` - Payment integration guide

**Django Apps:**
- `accounts/` - User management
- `timer/` - Timer and break functionality
- `analytics/` - Statistics and reports
- `notifications/` - Email notifications
- `subscriptions/` - Subscription models (unused)
- `calendars/` - Calendar integrations
- `mysite/` - Project settings and configuration

## Troubleshooting

### Common Issues

**ImportError or ModuleNotFoundError:**
```bash
# Reinstall dependencies
pip install -r requirements.txt
```

**Migration errors:**
```bash
# Reset migrations (development only)
python manage.py migrate --fake
python manage.py migrate
```

**Static files not loading:**
```bash
# Collect static files
python manage.py collectstatic --noinput
```

**Redis connection error:**
```bash
# Start Redis server
redis-server
```

## Support

For issues or questions:
- Check the documentation
- Review error logs in `logs/`
- Create an issue in the repository

## License

[Add your license here]

## Acknowledgments

- Django framework
- Bootstrap for UI components
- All open-source contributors

---

**Version:** 1.0.0
**Last Updated:** 2025-10-02
**Status:** Production Ready
