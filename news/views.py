from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import F, Q, Count, Sum
from django.db.models.functions import Coalesce
from .models import NewsArticle, Vote, Comment, UserPreference, Poll, UserProfile, PollOption
from .scraper import fetch_and_save_news
from .forms import (
    SignUpForm,
    OnboardingForm,
    ProfileUpdateForm,
    PreferencesUpdateForm,
    SetInitialPasswordForm,
)
import json
from datetime import timedelta
from django.utils import timezone

# ==================== Utility Functions ====================

def get_or_create_session(request):
    """Get or create session ID"""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def get_relative_time(dt):
    """Return relative time string"""
    now = timezone.now()
    diff = now - dt
    if diff < timedelta(minutes=1):
        return 'Just now'
    elif diff < timedelta(hours=1):
        return f'{int(diff.total_seconds() / 60)} mins ago'
    elif diff < timedelta(days=1):
        return f'{int(diff.total_seconds() / 3600)} hrs ago'
    elif diff < timedelta(days=7):
        return f'{diff.days} days ago'
    return dt.strftime('%B %d, %Y')


def calculate_personalized_score(article, prefs):
    """Weighted personalized score"""
    hours_old = (timezone.now() - article.published_date).total_seconds() / 3600
    recency = max(0, 10 - (hours_old / 24))
    engagement = min(10, (article.upvotes * 0.5 + article.views * 0.01) / 10)
    credibility = article.credibility_score
    category_pref = prefs.get(article.category, 5)
    return (
        recency * 0.3
        + engagement * 0.3
        + credibility * 0.2
        + category_pref * 0.2
    )


def calculate_reading_time(text):
    """Calculate reading time in minutes (avg 200 words/min)"""
    words = len(text.split())
    minutes = max(1, round(words / 200))
    return minutes

# ==================== Public Pages ====================

def index(request):
    """Homepage view (Redirects to password setup if onboarding is incomplete)"""
    if request.user.is_authenticated and not request.user.profile.onboarding_complete:
        return redirect('set_initial_password') # Enforcing mandatory password step

    if request.user.is_authenticated:
        return render(request, 'index.html')
    return render(request, 'landing.html')

# ==================== Authentication ====================

def signup_view(request):
    """User signup with redirect to password setup"""
    if request.user.is_authenticated:
        if not request.user.profile.onboarding_complete:
            return redirect('set_initial_password')
        return redirect('index')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.info(request, 'Account created! Please set your new password.')
            return redirect('set_initial_password') # Mandatory password step
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SignUpForm()

    return render(request, 'signup.html', {'form': form})


def login_view(request):
    """User login (username/email) + password setup check"""
    if request.user.is_authenticated:
        if not request.user.profile.onboarding_complete:
            return redirect('set_initial_password') # Enforcing mandatory password step
        return redirect('index')

    if request.method == 'POST':
        identifier = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=identifier, password=password)

        # Allow login via email if username fails
        if user is None and '@' in identifier:
            try:
                user_by_email = User.objects.get(email__iexact=identifier)
                user = authenticate(
                    request, username=user_by_email.username, password=password
                )
            except User.DoesNotExist:
                pass

        if user is not None:
            login(request, user)
            if not user.profile.onboarding_complete:
                messages.info(
                    request, 'Welcome! Please set your permanent password to continue.'
                )
                return redirect('set_initial_password') # Enforcing mandatory password step
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect('index')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'login.html')


def logout_view(request):
    """User logout"""
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('index')


@login_required
def set_initial_password_view(request):
    """Force newly registered users to set a permanent password"""
    if request.user.profile.onboarding_complete:
        messages.info(request, 'Your password is already set.')
        return redirect('index')

    if request.method == 'POST':
        form = SetInitialPasswordForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password set successfully! Let's personalize your feed.")
            return redirect('onboarding') # Redirect to onboarding next
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SetInitialPasswordForm(request.user)

    context = {'form': form, 'title': 'Set Your Permanent Password'}
    return render(request, 'set_initial_password.html', context)


@login_required
def onboarding_view(request):
    """Onboarding for new users"""
    profile = request.user.profile

    # Check if the mandatory password step was completed first
    if not profile.onboarding_complete:
        messages.warning(
            request, 'Please set your permanent password before choosing preferences.'
        )
        return redirect('set_initial_password') # Redirect back to password setup

    if profile.onboarding_complete:
        messages.info(request, 'You have already completed onboarding.')
        return redirect('index')

    if request.method == 'POST':
        form = OnboardingForm(request.POST, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.onboarding_complete = True
            profile.save()
            messages.success(
                request, 'Preferences saved! Your feed is now personalized.'
            )
            return redirect('index')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = OnboardingForm(instance=profile)

    return render(request, 'onboarding.html', {'form': form})

# ==================== User Pages ====================

@login_required
def profile_view(request):
    """User profile page"""
    if not request.user.profile.onboarding_complete:
        messages.warning(request, 'Please complete the setup process first.')
        return redirect('set_initial_password') # Enforcing mandatory password step

    if request.method == 'POST':
        user_form = ProfileUpdateForm(request.POST, instance=request.user)
        prefs_form = PreferencesUpdateForm(request.POST, instance=request.user.profile)

        if user_form.is_valid() and prefs_form.is_valid():
            user_form.save()
            prefs_form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        user_form = ProfileUpdateForm(instance=request.user)
        prefs_form = PreferencesUpdateForm(instance=request.user.profile)

    context = {
        'profile_form': user_form,
        'prefs_form': prefs_form,
        'user': request.user,
    }
    return render(request, 'profile.html', context)


@login_required
def user_dashboard_auth(request):
    """User activity dashboard"""
    if not request.user.profile.onboarding_complete:
        messages.warning(request, 'Please complete the setup process first.')
        return redirect('set_initial_password') # Enforcing mandatory password step

    session_id = get_or_create_session(request)
    user_votes = Vote.objects.filter(session_id=session_id).select_related('article')
    user_comments = Comment.objects.filter(
        author_name=request.user.username
    ).select_related('article')

    context = {
        'votes': user_votes,
        'comments': user_comments,
        'total_votes': user_votes.count(),
        'total_comments': user_comments.count(),
    }
    return render(request, 'user_dashboard.html', context)

# ==================== API Endpoints ====================

def get_news(request):
    """Fetch personalized news"""
    session_id = get_or_create_session(request)
    category = request.GET.get('category', 'all')
    search_query = request.GET.get('search', '')

    user_pref, _ = UserPreference.objects.get_or_create(
        session_id=session_id, defaults={'preferred_categories': {}}
    )

    # Determine preference source: profile if authenticated, else session
    if request.user.is_authenticated:
        try:
            profile = request.user.profile
            if isinstance(profile.preferred_categories, list):
                preferences = {cat: 5.0 for cat in profile.preferred_categories}
            else:
                preferences = profile.preferred_categories or {}
        except UserProfile.DoesNotExist:
            preferences = {}
    else:
        preferences = user_pref.preferred_categories

    # Fetch articles
    if category == 'all':
        articles_qs = NewsArticle.objects.all().prefetch_related('comments').order_by('-published_date')
    else:
        articles_qs = NewsArticle.objects.filter(category=category).prefetch_related('comments').order_by('-published_date')

    if search_query:
        articles_qs = articles_qs.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    articles = list(articles_qs[:100])  # Limit to 100

    # Calculate personalized scores
    articles_with_scores = [
        (a, calculate_personalized_score(a, preferences)) for a in articles
    ]
    articles_with_scores.sort(key=lambda x: x[1], reverse=True)

    # Get user votes
    user_votes = Vote.objects.filter(
        session_id=session_id,
        article__in=[a[0] for a in articles_with_scores]
    ).values('article_id', 'vote_type')
    user_votes_dict = {v['article_id']: v['vote_type'] for v in user_votes}

    # Prepare data
    news_data = []
    for article, score in articles_with_scores[:50]:
        comments = [
            {
                'author': c.author_name,
                'text': c.text,
                'created_at': c.created_at.strftime('%Y-%m-%d %H:%M'),
            }
            for c in article.comments.all()[:5]
        ]

        reading_time = calculate_reading_time(article.description + (article.content or ''))
        is_personalized = article.category in preferences
        is_trending = article.upvotes > 50 or (article.upvotes > 20 and len(comments) > 5)

        news_data.append({
            'id': article.id,
            'title': article.title,
            'description': article.description,
            'category': article.category,
            'source': article.source,
            'source_url': article.source_url,
            'time': get_relative_time(article.published_date),
            'image': article.image_url,
            'upvotes': article.upvotes,
            'downvotes': article.downvotes,
            'views': article.views,
            'user_vote': user_votes_dict.get(article.id),
            'comments': comments,
            'score': round(score, 2),
            'reading_time': reading_time,
            'personalized': is_personalized,
            'trending': is_trending,
        })

    return JsonResponse({'news': news_data, 'user_preferences': list(preferences.keys())})


def get_archived(request):
    """Fetch old, highly-engaged news (archived)"""
    days = int(request.GET.get('days', 7))
    min_upvotes = 5
    min_views = 50

    cutoff_date = timezone.now() - timedelta(days=days)

    archived_articles = (
        NewsArticle.objects.filter(
            published_date__lt=cutoff_date,
            upvotes__gt=min_upvotes,
            views__gt=min_views
        )
        .annotate(engagement=F('upvotes') + F('views') + Count('comments'))
        .order_by('-engagement')[:10]
        .prefetch_related('comments')
    )

    archived_data = [
        {
            'id': a.id,
            'title': a.title,
            'description': a.description,
            'category': a.category,
            'source': a.source,
            'source_url': a.source_url,
            'time': get_relative_time(a.published_date),
            'image': a.image_url,
            'upvotes': a.upvotes,
            'downvotes': a.downvotes,
            'views': a.views,
            'comments': [{'id': c.id} for c in a.comments.all()],
        }
        for a in archived_articles
    ]

    return JsonResponse({'archived': archived_data})


@csrf_exempt
def vote_article(request):
    """Handle upvote/downvote"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

    data = json.loads(request.body)
    article_id = data.get('article_id')
    vote_type = data.get('vote_type')
    session_id = get_or_create_session(request)

    try:
        article = NewsArticle.objects.get(id=article_id)
        vote_obj, created = Vote.objects.get_or_create(
            session_id=session_id,
            article=article,
            defaults={'vote_type': vote_type}
        )

        if not created:
            if vote_obj.vote_type == vote_type:
                # Remove vote
                if vote_type == 'up':
                    article.upvotes = max(0, article.upvotes - 1)
                else:
                    article.downvotes = max(0, article.downvotes - 1)
                vote_obj.delete()
                new_vote = None
            else:
                # Switch vote
                if vote_obj.vote_type == 'up':
                    article.upvotes = max(0, article.upvotes - 1)
                    article.downvotes += 1
                else:
                    article.downvotes = max(0, article.downvotes - 1)
                    article.upvotes += 1
                vote_obj.vote_type = vote_type
                vote_obj.save()
                new_vote = vote_type
        else:
            # New vote
            if vote_type == 'up':
                article.upvotes += 1
            else:
                article.downvotes += 1
            new_vote = vote_type

        article.save()

        return JsonResponse({
            'status': 'success',
            'upvotes': article.upvotes,
            'downvotes': article.downvotes,
            'user_vote': new_vote,
        })

    except NewsArticle.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Article not found'}, status=404)


@csrf_exempt
def add_comment(request):
    """Add a comment to an article"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

    data = json.loads(request.body)
    article_id = data.get('article_id')
    comment_text = data.get('text')

    if request.user.is_authenticated:
        author_name = request.user.first_name or request.user.username
    else:
        author_name = data.get('author', 'Anonymous')

    try:
        article = NewsArticle.objects.get(id=article_id)
        comment = Comment.objects.create(
            article=article, text=comment_text, author_name=author_name
        )

        return JsonResponse({
            'status': 'success',
            'comment': {
                'author': comment.author_name,
                'text': comment.text,
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M'),
            },
        })
    except NewsArticle.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Article not found'}, status=404)

# ==================== Polls ====================

def get_polls(request):
    """Get active polls"""
    polls_qs = Poll.objects.filter(is_active=True).prefetch_related('options')
    polls_data = []

    for poll in polls_qs:
        total_votes = poll.options.aggregate(total=Coalesce(Sum('votes'), 0))['total']
        options_data = [
            {
                'id': o.id,
                'text': o.text,
                'votes': o.votes,
                'percentage': round((o.votes / total_votes) * 100, 1) if total_votes > 0 else 0,
            }
            for o in poll.options.all()
        ]

        polls_data.append({
            'id': poll.id,
            'question': poll.question,
            'options': options_data,
            'total_votes': total_votes,
        })

    return JsonResponse({'polls': polls_data})


@csrf_exempt
def vote_poll(request):
    """Vote on a poll"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

    data = json.loads(request.body)
    option_id = data.get('option_id')

    try:
        option = PollOption.objects.get(id=option_id)
        option.votes = F('votes') + 1
        option.save()
        option.refresh_from_db()

        return JsonResponse({'status': 'success', 'option_id': option.id})

    except PollOption.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Poll option not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Server error: {type(e).__name__}'}, status=500)

# ==================== Stats ====================

def get_stats(request):
    """Get overall statistics"""
    total_poll_votes = PollOption.objects.aggregate(total=Coalesce(Sum('votes'), 0))['total']

    stats = {
        'total_articles': NewsArticle.objects.count(),
        'total_votes': Vote.objects.count(),
        'total_comments': Comment.objects.count(),
        'active_users': UserPreference.objects.count(),
        'total_users': User.objects.count(),
        'total_profiles': UserProfile.objects.count(),
        'total_polls': Poll.objects.count(),
        'total_poll_votes': total_poll_votes,
    }

    category_counts_qs = NewsArticle.objects.values('category').annotate(count=Count('id'))
    stats['by_category'] = {i['category']: i['count'] for i in category_counts_qs}

    return JsonResponse(stats)


@login_required
def get_user_stats_auth(request):
    """Get authenticated user statistics"""
    if request.user.profile.onboarding_complete is False: 
        return JsonResponse({'status': 'error', 'message': 'Setup incomplete'}, status=403) 

    user = request.user
    profile = user.profile
    session_id = request.session.session_key
    
    # --- 1. Get Votes and Comments ---
    user_votes_qs = Vote.objects.filter(session_id=session_id)
    upvotes = user_votes_qs.filter(vote_type='up').count()

    user_comments_qs = Comment.objects.filter(author_name__in=[user.username, user.first_name]).select_related('article') 
    
    # --- 2. Get Preferences ---
    if isinstance(profile.preferred_categories, list):
        preferences = {cat: 5.0 for cat in profile.preferred_categories}
    else:
        preferences = profile.preferred_categories or {}
        
    favorite_category = max(preferences.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 0)[0] if preferences else 'None'
    
    # --- 3. Recent Activity (Votes + Comments) ---
    recent_activity = []
    
    for vote in user_votes_qs.select_related('article').order_by('-created_at')[:5]:
        recent_activity.append({
            'title': vote.article.title[:40] + '...',
            'type': 'Upvoted' if vote.vote_type == 'up' else 'Downvoted',
            'time': get_relative_time(vote.created_at)
        })
        
    for comment in user_comments_qs.order_by('-created_at')[:5]:
        recent_activity.append({
            'title': comment.article.title[:40] + '...',
            'type': 'Commented',
            'time': get_relative_time(comment.created_at)
        })
        
    recent_activity.sort(key=lambda x: x['time'], reverse=False)

    stats = {
        'articles_read': profile.total_articles_read,
        'upvotes_given': upvotes,
        'comments_posted': user_comments_qs.count(),
        'favorite_category': favorite_category.title() if favorite_category != 'None' else 'None yet',
        'preferences': {k.title(): round(v, 1) for k, v in preferences.items()},
        'recent_activity': recent_activity[:10],
    }
    
    return JsonResponse(stats)

# ==================== News Refresh (Public & Admin) ====================

def refresh_news_public(request):
    """
    Public endpoint for users to refresh news
    Limited to prevent API abuse
    """
    session_id = get_or_create_session(request)
    last_refresh_key = f'last_refresh_{session_id}'
    last_refresh = request.session.get(last_refresh_key)
    
    # --- Rate Limiting Logic ---
    if last_refresh:
        try:
            last_refresh_time = timezone.datetime.fromisoformat(last_refresh)
        except ValueError:
            return JsonResponse({'status': 'error', 'message': 'Internal error parsing last refresh time.'}, status=500)
            
        time_since_refresh = (timezone.now() - last_refresh_time).total_seconds()
        
        if time_since_refresh < 300:
            return JsonResponse({
                'status': 'error',
                'message': f'Please wait {int(300 - time_since_refresh)} seconds before refreshing again.'
            }, status=429)
    
    # --- Core Logic with Robust Error Handling ---
    try:
        stats = fetch_and_save_news(
            categories=['general', 'technology'],
            articles_per_category=5
        )
        
        # Update last refresh time only on successful scraping
        request.session[last_refresh_key] = timezone.now().isoformat()
        
        return JsonResponse({
            'status': 'success',
            'message': f"✅ Refreshed! Found {stats.get('total_saved', 0)} new articles",
            'total_saved': stats.get('total_saved', 0),
            'by_category': stats['by_category']
        })
    except Exception as e:
        # Catch any exception during scraping (e.g., requests.exceptions.ConnectionError)
        return JsonResponse({
            'status': 'error',
            'message': f'Scraping failed due to a server error: {type(e).__name__}'
        }, status=500)


@staff_member_required
def refresh_news(request):
    """
    Admin endpoint to fetch news with higher limits.
    """
    try:
        stats = fetch_and_save_news(
            categories=None,  # Fetch all categories
            articles_per_category=10
        )
        
        return JsonResponse({
            'status': 'success',
            'message': f"✅ Saved {stats['total_saved']} NEW articles!",
            'total_fetched': stats['total_fetched'],
            'total_saved': stats['total_saved'],
            'by_category': stats['by_category'],
        })
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': f'Admin scraping failed due to a server error: {type(e).__name__}'
        }, status=500)


@staff_member_required
def dashboard(request):
    """Admin dashboard view"""
    stats = {
        'total_articles': NewsArticle.objects.count(),
        'total_users': User.objects.count(),
        'total_votes': Vote.objects.count(),
        'total_comments': Comment.objects.count(),
    }
    
    return render(request, 'dashboard.html', {'stats': stats})