# news/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Public pages
    path('', views.index, name='index'),
    # REMOVED: path('set-password/', views.set_initial_password_view, name='set_initial_password'),
    
    # Authentication
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('onboarding/', views.onboarding_view, name='onboarding'),
    path('change-password/', views.change_password_view, name='change_password'),
    
    # User pages
    path('profile/', views.profile_view, name='profile'),
    path('my-activity/', views.user_dashboard_auth, name='user_dashboard_auth'),
    
    # Admin pages
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # API endpoints
    path('api/news/', views.get_news, name='get_news'),
    path('api/archived/', views.get_archived, name='get_archived'),
    path('api/vote/', views.vote_article, name='vote_article'),
    path('api/comment/', views.add_comment, name='add_comment'),
    path('api/polls/', views.get_polls, name='get_polls'),
    path('api/poll/vote/', views.vote_poll, name='vote_poll'),
    path('api/stats/', views.get_stats, name='get_stats'),
    path('api/user-stats/', views.get_user_stats_auth, name='get_user_stats_auth'),
    
    # Public refresh endpoint
    path('api/refresh-news-public/', views.refresh_news_public, name='refresh_news_public'),
    
    # Admin refresh endpoint
    path('api/refresh-news/', views.refresh_news, name='refresh_news'),
    
    path('api/headlines/', views.get_news, name='get_headlines'), 
]