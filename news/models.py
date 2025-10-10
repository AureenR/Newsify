from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


# -------------------- NEWS MODELS --------------------

class NewsArticle(models.Model):
    """Model for storing news articles"""
    CATEGORY_CHOICES = [
        ('technology', 'Technology'),
        ('sports', 'Sports'),
        ('business', 'Business'),
        ('entertainment', 'Entertainment'),
        ('health', 'Health'),
        ('science', 'Science'),
        ('politics', 'Politics'),
        ('world', 'World'),
    ]
    
    title = models.CharField(max_length=500)
    description = models.TextField()
    content = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    source = models.CharField(max_length=200)
    source_url = models.URLField(max_length=1000)
    image_url = models.URLField(max_length=1000, blank=True, null=True)
    published_date = models.DateTimeField(default=timezone.now)
    scraped_date = models.DateTimeField(auto_now_add=True)
    
    credibility_score = models.IntegerField(default=5)
    upvotes = models.IntegerField(default=0)
    downvotes = models.IntegerField(default=0)
    views = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-published_date']
        indexes = [
            models.Index(fields=['category', '-published_date']),
            models.Index(fields=['-published_date']),
        ]
    
    def __str__(self):
        return self.title

    @property
    def vote_score(self):
        return self.upvotes - self.downvotes
    
    @property
    def engagement_score(self):
        return (self.upvotes * 2) + self.views - self.downvotes


class UserPreference(models.Model):
    """Track anonymous user preferences (session-based)"""
    session_id = models.CharField(max_length=100, unique=True)
    preferred_categories = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Preferences for {self.session_id}"


class Vote(models.Model):
    """Track votes on articles"""
    VOTE_CHOICES = [
        ('up', 'Upvote'),
        ('down', 'Downvote'),
    ]
    
    article = models.ForeignKey(NewsArticle, on_delete=models.CASCADE, related_name='article_votes')
    session_id = models.CharField(max_length=100)
    vote_type = models.CharField(max_length=10, choices=VOTE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('article', 'session_id')
        indexes = [models.Index(fields=['article', 'session_id'])]
    
    def __str__(self):
        return f"{self.vote_type} on {self.article.title[:50]}"


class Comment(models.Model):
    """Store user comments on articles"""
    article = models.ForeignKey(NewsArticle, on_delete=models.CASCADE, related_name='comments')
    session_id = models.CharField(max_length=100)
    author_name = models.CharField(max_length=100, default='Anonymous')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Comment by {self.author_name} on {self.article.title[:50]}"


class Poll(models.Model):
    """Create polls for user engagement"""
    question = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return self.question


class PollOption(models.Model):
    """Options for each poll"""
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=200)
    votes = models.IntegerField(default=0)
    
    def __str__(self):
        return f"{self.text} ({self.votes} votes)"
    
    @property
    def percentage(self):
        total_votes = sum(option.votes for option in self.poll.options.all())
        return round((self.votes / total_votes) * 100, 1) if total_votes > 0 else 0


# -------------------- USER PROFILE EXTENSION --------------------

class UserProfile(models.Model):
    """Extended user profile with preferences"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Preferences
    preferred_categories = models.JSONField(default=list)
    preferred_language = models.CharField(max_length=10, default='en')
    country = models.CharField(max_length=100, blank=True)
    
    # Settings
    email_notifications = models.BooleanField(default=True)
    show_images = models.BooleanField(default=True)
    dark_mode = models.BooleanField(default=False)
    
    # Statistics
    total_articles_read = models.IntegerField(default=0)
    total_upvotes = models.IntegerField(default=0)
    total_downvotes = models.IntegerField(default=0)
    total_comments = models.IntegerField(default=0)
    
    # Profile info
    bio = models.TextField(max_length=500, blank=True)
    avatar = models.URLField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Onboarding
    onboarding_complete = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.user.username}'s Profile"
    
    @property
    def engagement_score(self):
        """Calculate user engagement score"""
        return self.total_upvotes + (self.total_comments * 2) + (self.total_articles_read * 0.5)


# -------------------- SIGNALS --------------------

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Automatically create profile when a new user is registered"""
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Save the profile whenever the user model is saved"""
    instance.profile.save()
