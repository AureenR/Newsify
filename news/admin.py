from django.contrib import admin
from .models import NewsArticle, UserPreference, Vote, Comment, Poll, PollOption

from .models import UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'onboarding_complete', 'total_articles_read', 'total_upvotes', 'created_at']
    list_filter = ['onboarding_complete', 'email_notifications']
search_fields = ['user__username', 'user__email']
@admin.register(NewsArticle)
class NewsArticleAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'source', 'published_date', 'upvotes', 'downvotes', 'views']
    list_filter = ['category', 'source', 'published_date']
    search_fields = ['title', 'description', 'source']
    date_hierarchy = 'published_date'
    ordering = ['-published_date']

@admin.register(UserPreference)
class UserPreferenceAdmin(admin.ModelAdmin):
    list_display = ['session_id', 'created_at', 'updated_at']
    search_fields = ['session_id']

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['article', 'session_id', 'vote_type', 'created_at']
    list_filter = ['vote_type', 'created_at']
    search_fields = ['article__title', 'session_id']

@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['article', 'author_name', 'text', 'created_at']
    list_filter = ['created_at']
    search_fields = ['article__title', 'author_name', 'text']
    date_hierarchy = 'created_at'

class PollOptionInline(admin.TabularInline):
    model = PollOption
    extra = 4

@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ['question', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['question']
    inlines = [PollOptionInline]