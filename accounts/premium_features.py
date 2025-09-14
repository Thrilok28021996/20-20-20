"""
Premium features configuration and utilities for the 20-20-20 SaaS app
"""
from django.conf import settings

# Premium timer presets (smart customization feature)
PREMIUM_TIMER_PRESETS = [
    {
        'name': 'Classic 20-20-20',
        'work_duration': 1200,  # 20 minutes in seconds
        'break_duration': 20,   # 20 seconds
        'description': 'The standard eye health rule'
    },
    {
        'name': 'Intensive Focus',
        'work_duration': 1500,  # 25 minutes (Pomodoro-style)
        'break_duration': 30,   # 30 seconds
        'description': 'Longer focus sessions with extended breaks'
    },
    {
        'name': 'Gentle Reminder',
        'work_duration': 900,   # 15 minutes
        'break_duration': 15,   # 15 seconds
        'description': 'More frequent, shorter breaks'
    },
    {
        'name': 'Power User',
        'work_duration': 1800,  # 30 minutes
        'break_duration': 60,   # 1 minute
        'description': 'Extended work periods with longer recovery'
    },
    {
        'name': 'Quick Start',
        'work_duration': 600,   # 10 minutes
        'break_duration': 10,   # 10 seconds
        'description': 'Perfect for getting started with the habit'
    }
]

# Premium themes (8 custom themes)
PREMIUM_THEMES = [
    {
        'name': 'Ocean Blue',
        'primary_color': '#1e40af',
        'secondary_color': '#0ea5e9',
        'accent_color': '#38bdf8',
        'description': 'Calming ocean-inspired colors'
    },
    {
        'name': 'Forest Green',
        'primary_color': '#16a34a',
        'secondary_color': '#22c55e',
        'accent_color': '#4ade80',
        'description': 'Nature-inspired green palette'
    },
    {
        'name': 'Sunset Orange',
        'primary_color': '#ea580c',
        'secondary_color': '#f97316',
        'accent_color': '#fb923c',
        'description': 'Warm and energizing sunset colors'
    },
    {
        'name': 'Purple Zen',
        'primary_color': '#7c3aed',
        'secondary_color': '#8b5cf6',
        'accent_color': '#a78bfa',
        'description': 'Mindful purple tones for focus'
    },
    {
        'name': 'Rose Gold',
        'primary_color': '#be185d',
        'secondary_color': '#ec4899',
        'accent_color': '#f472b6',
        'description': 'Elegant rose gold finish'
    },
    {
        'name': 'Midnight Dark',
        'primary_color': '#1f2937',
        'secondary_color': '#374151',
        'accent_color': '#6b7280',
        'description': 'Professional dark mode'
    },
    {
        'name': 'Arctic White',
        'primary_color': '#f8fafc',
        'secondary_color': '#f1f5f9',
        'accent_color': '#cbd5e1',
        'description': 'Clean minimalist white'
    },
    {
        'name': 'Productivity Red',
        'primary_color': '#dc2626',
        'secondary_color': '#ef4444',
        'accent_color': '#f87171',
        'description': 'Energizing red for productivity'
    }
]

# Guided eye exercises (6 types)
EYE_EXERCISES = [
    {
        'name': 'Focus Shifting',
        'duration': 30,
        'instructions': [
            'Hold your finger 6 inches from your face',
            'Focus on your finger for 3 seconds',
            'Look at something 20 feet away for 3 seconds',
            'Repeat 5 times'
        ],
        'benefits': 'Improves focus flexibility and reduces eye strain'
    },
    {
        'name': 'Eye Circles',
        'duration': 20,
        'instructions': [
            'Look up and slowly circle your eyes clockwise',
            'Complete 5 circles clockwise',
            'Complete 5 circles counter-clockwise',
            'Blink several times to relax'
        ],
        'benefits': 'Strengthens eye muscles and improves mobility'
    },
    {
        'name': 'Palming',
        'duration': 60,
        'instructions': [
            'Rub your palms together to warm them',
            'Gently cup your palms over your closed eyes',
            'Breathe deeply and relax for 1 minute',
            'Remove hands slowly and blink gently'
        ],
        'benefits': 'Relieves eye tension and promotes relaxation'
    },
    {
        'name': 'Blinking Exercise',
        'duration': 30,
        'instructions': [
            'Blink normally 10 times',
            'Close eyes tightly for 2 seconds',
            'Open and blink rapidly 10 times',
            'Rest with eyes closed for 5 seconds'
        ],
        'benefits': 'Moisturizes eyes and prevents dryness'
    },
    {
        'name': 'Figure Eight',
        'duration': 30,
        'instructions': [
            'Imagine a large figure 8 in front of you',
            'Trace the figure 8 with your eyes slowly',
            'Complete 5 figure 8s in one direction',
            'Repeat 5 times in the opposite direction'
        ],
        'benefits': 'Enhances eye coordination and control'
    },
    {
        'name': 'Distance Focusing',
        'duration': 60,
        'instructions': [
            'Look at something 20+ feet away',
            'Focus clearly for 10 seconds',
            'Look at something 10 feet away for 10 seconds',
            'Look at something 3 feet away for 10 seconds',
            'Repeat this sequence 3 times'
        ],
        'benefits': 'Prevents focusing fatigue and eye strain'
    }
]

# Achievement definitions for gamification
ACHIEVEMENT_DEFINITIONS = {
    'streak_7': {
        'name': '7 Day Streak',
        'description': 'Complete 7 consecutive days of 20-20-20 sessions',
        'icon': '🔥',
        'points': 100
    },
    'streak_30': {
        'name': '30 Day Streak', 
        'description': 'Complete 30 consecutive days of sessions',
        'icon': '🏆',
        'points': 500
    },
    'streak_100': {
        'name': '100 Day Streak',
        'description': 'Complete 100 consecutive days of sessions',
        'icon': '💎',
        'points': 2000
    },
    'early_bird': {
        'name': 'Early Bird',
        'description': 'Complete 10 sessions between 5 AM - 9 AM',
        'icon': '🌅',
        'points': 200
    },
    'night_owl': {
        'name': 'Night Owl',
        'description': 'Complete 10 sessions between 6 PM - 12 AM',
        'icon': '🦉',
        'points': 200
    },
    'weekend_warrior': {
        'name': 'Weekend Warrior',
        'description': 'Complete sessions on 5 consecutive weekends',
        'icon': '⚡',
        'points': 300
    },
    'session_master': {
        'name': 'Session Master',
        'description': 'Complete 1000 total sessions',
        'icon': '👑',
        'points': 1000
    },
    'eye_health_champion': {
        'name': 'Eye Health Champion',
        'description': 'Complete perfect week (no missed days)',
        'icon': '🎯',
        'points': 250
    }
}

def get_user_premium_features(user):
    """
    Get available premium features for a user
    """
    if not user.is_authenticated:
        return []
    
    if user.is_premium_user and user.is_subscription_active:
        return [
            'unlimited_sessions',
            'smart_timer_presets',
            'advanced_analytics',
            'guided_exercises', 
            'custom_themes',
            'email_reports',
            'achievements',
            'data_export',
            'calendar_integration',
            'priority_support'
        ]
    else:
        return []

def can_access_feature(user, feature_name):
    """
    Check if user can access a specific premium feature
    """
    premium_features = get_user_premium_features(user)
    return feature_name in premium_features