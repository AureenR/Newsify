from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import F, Q, Count, Sum # Note: Added Count and Sum for new API functions
from .models import NewsArticle, Vote, Comment, UserPreference, Poll, UserProfile
from .scraper import fetch_and_save_news
from .forms import SignUpForm, OnboardingForm, ProfileUpdateForm, PreferencesUpdateForm
import json
from datetime import timedelta
from django.utils import timezone


# -------------------- Utility Functions --------------------

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
        recency * 0.3 +
        engagement * 0.3 +
        credibility * 0.2 +
        category_pref * 0.2
    )

def calculate_reading_time(text):
    """Calculate reading time in minutes (avg 200 words/min)"""
    words = len(text.split())
    minutes = max(1, round(words / 200))
    return minutes

# -------------------- News & Feed --------------------

def index(request):
    if request.user.is_authenticated:
        return render(request, 'index.html')
    return render(request, 'landing.html')


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
        profile = request.user.profile
        if isinstance(profile.preferred_categories, list):
            preferences = {cat: 5.0 for cat in profile.preferred_categories}
        else:
            preferences = profile.preferred_categories or {}
    else:
        preferences = user_pref.preferred_categories

    # --- N+1 FIX and Article Selection ---
    if category == 'all':
        # Fetch articles with prefetch_related('comments') to solve N+1
        articles_qs = NewsArticle.objects.all().prefetch_related('comments')
    else:
        articles_qs = NewsArticle.objects.filter(category=category).prefetch_related('comments')
    # -------------------------------------

    if search_query:
        articles_qs = articles_qs.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )
    
    articles = list(articles_qs)

    # Calculate scores
    articles_with_scores = [
        (a, calculate_personalized_score(a, preferences))
        for a in articles
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
    for article, score in articles_with_scores[:20]:
        # Comments are efficiently retrieved due to prefetch_related
        comments = [
            {
                'author': c.author_name,
                'text': c.text,
                'created_at': c.created_at.strftime('%Y-%m-%d %H:%M')
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
            'source_url': article.source_url,  # <--- FIX: Added source_url to response data
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


# -------------------- Voting & Comments --------------------

@csrf_exempt
def vote_article(request):
    """Handle article upvotes/downvotes"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request'})

    try:
        data = json.loads(request.body)
        article = NewsArticle.objects.get(id=data['article_id'])
        vote_type = data['vote_type']
        session_id = get_or_create_session(request)

        existing_vote = Vote.objects.filter(article=article, session_id=session_id).first()
        if existing_vote:
            old = existing_vote.vote_type
            if old == vote_type:
                # Toggle off
                if vote_type == 'up':
                    article.upvotes = F('upvotes') - 1
                else:
                    article.downvotes = F('downvotes') - 1
                article.save()
                existing_vote.delete()
                article.refresh_from_db()
                return JsonResponse({'status': 'success', 'upvotes': article.upvotes, 'downvotes': article.downvotes})
            else:
                # Changing vote type
                if old == 'up':
                    article.upvotes = F('upvotes') - 1
                    article.downvotes = F('downvotes') + 1
                else:
                    article.downvotes = F('downvotes') - 1
                    article.upvotes = F('upvotes') + 1
                existing_vote.vote_type = vote_type
                existing_vote.save()
        else:
            Vote.objects.create(article=article, session_id=session_id, vote_type=vote_type)
            if vote_type == 'up':
                article.upvotes = F('upvotes') + 1
            else:
                article.downvotes = F('downvotes') + 1

        article.save()
        article.refresh_from_db()
        return JsonResponse({'status': 'success', 'upvotes': article.upvotes, 'downvotes': article.downvotes})

    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})



def update_user_preferences(session_id, category, weight):
    """Update preference score"""
    user_pref, _ = UserPreference.objects.get_or_create(
        session_id=session_id, defaults={'preferred_categories': {}}
    )
    prefs = user_pref.preferred_categories
    current = prefs.get(category, 5)
    prefs[category] = min(10, current + (weight * 0.5))
    user_pref.preferred_categories = prefs
    user_pref.save()


@csrf_exempt
def add_comment(request):
    """Add a comment"""
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request'})

    try:
        data = json.loads(request.body)
        article = NewsArticle.objects.get(id=data['article_id'])
        
        # --- FIX: Determine the true author name based on authentication ---
        if request.user.is_authenticated:
            # Use first name if available, otherwise use username
            author_name = request.user.first_name or request.user.username
        else:
            # Fallback for anonymous users
            author_name = 'Anonymous'
        # -----------------------------------------------------------------
        
        comment = Comment.objects.create(
            article=article,
            session_id=get_or_create_session(request),
            author_name=author_name, # Use the determined name
            text=data['comment']
        )
        update_user_preferences(get_or_create_session(request), article.category, 0.5)
        return JsonResponse({
            'status': 'success',
            'comment': {
                'author': comment.author_name, # Return the correct name
                'text': comment.text,
                'created_at': comment.created_at.strftime('%Y-%m-%d %H:%M')
            }
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


# -------------------- Polls --------------------

def get_polls(request):
    polls = Poll.objects.filter(is_active=True).prefetch_related('options')
    data = [{
        'id': p.id,
        'question': p.question,
        'options': [
            {'id': o.id, 'text': o.text, 'votes': o.votes, 'percentage': o.percentage}
            for o in p.options.all()
        ]
    } for p in polls]
    return JsonResponse({'polls': data})


@csrf_exempt
def vote_poll(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Invalid request'})
    try:
        from .models import PollOption
        data = json.loads(request.body)
        option = PollOption.objects.get(id=data['option_id'])
        option.votes = F('votes') + 1
        option.save()
        option.refresh_from_db()
        return JsonResponse({'status': 'success', 'votes': option.votes, 'percentage': option.percentage})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)})


# -------------------- Admin Views --------------------

@staff_member_required
def refresh_news(request):
    stats = fetch_and_save_news(articles_per_category=5)
    return JsonResponse({'status': 'success', 'message': f"Fetched {stats['total_saved']} new articles"})


@staff_member_required
def dashboard(request):
    return render(request, 'dashboard.html')


def get_stats(request):
    from .models import PollOption
    total_poll_votes = 0
    try:
        total_poll_votes = PollOption.objects.all().aggregate(total=__import__('django').db.models.Sum('votes'))['total'] or 0
    except Exception:
        total_poll_votes = 0

    stats = {
        'total_articles': NewsArticle.objects.count(),
        'total_votes': Vote.objects.count(),
        'total_comments': Comment.objects.count(),
        'active_users': UserPreference.objects.count(),
        'total_users': User.objects.count(),
        'total_profiles': UserProfile.objects.count(),
        'total_polls': Poll.objects.count(),
        'total_poll_votes': total_poll_votes,
        'by_category': {
            cat: NewsArticle.objects.filter(category=cat).count()
            for cat, _ in NewsArticle.CATEGORY_CHOICES if NewsArticle.objects.filter(category=cat).exists()
        }
    }
    return JsonResponse(stats)


# -------------------- User Dashboard --------------------

def user_dashboard(request):
    return render(request, 'user_dashboard.html')


def get_user_stats(request):
    session_id = get_or_create_session(request)
    user_votes = Vote.objects.filter(session_id=session_id)
    user_comments = Comment.objects.filter(session_id=session_id)
    upvotes = user_votes.filter(vote_type='up').count()

    try:
        user_pref = UserPreference.objects.get(session_id=session_id)
        prefs = user_pref.preferred_categories
        fav = max(prefs, key=prefs.get) if prefs else None
    except UserPreference.DoesNotExist:
        prefs, fav = {}, None

    activity = []
    for v in user_votes.order_by('-created_at')[:5]:
        activity.append({'title': v.article.title[:50] + '...', 'type': v.vote_type.title(), 'time': get_relative_time(v.created_at)})
    for c in user_comments.order_by('-created_at')[:5]:
        activity.append({'title': c.article.title[:50] + '...', 'type': 'Commented', 'time': get_relative_time(c.created_at)})

    return JsonResponse({
        'articles_read': user_votes.count(),
        'upvotes_given': upvotes,
        'comments_posted': user_comments.count(),
        'favorite_category': fav.title() if fav else 'None yet',
        'preferences': prefs,
        'recent_activity': activity
    })


# -------------------- Authentication Views --------------------

def signup_view(request):
    """User signup"""
    if request.user.is_authenticated:
        return redirect('onboarding')
    
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully! Please complete your profile.')
            return redirect('onboarding')
    else:
        form = SignUpForm()
    
    return render(request, 'signup.html', {'form': form})


def login_view(request):
    """User login"""
    if request.user.is_authenticated:
        return redirect('index')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Check if onboarding is complete
            if not user.profile.onboarding_complete:
                return redirect('onboarding')
            
            messages.success(request, f'Welcome back, {user.first_name}!')
            
            # Redirect to next or home
            next_url = request.GET.get('next', 'index')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'login.html')


@login_required
def logout_view(request):
    """User logout"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('index')


@login_required
def onboarding_view(request):
    """User onboarding - setup preferences"""
    profile = request.user.profile
    
    if profile.onboarding_complete:
        messages.info(request, 'You have already completed onboarding.')
        return redirect('index')
    
    if request.method == 'POST':
        form = OnboardingForm(request.POST, instance=profile)
        if form.is_valid():
            profile = form.save(commit=False)
            profile.onboarding_complete = True
            profile.save()
            
            messages.success(request, 'Welcome to Newsify! Your feed is now personalized.')
            return redirect('index')
    else:
        form = OnboardingForm(instance=profile)
    
    return render(request, 'onboarding.html', {'form': form})


@login_required
def profile_view(request):
    """View and edit user profile"""
    user = request.user
    profile = user.profile
    
    if request.method == 'POST':
        user_form = ProfileUpdateForm(request.POST, instance=user)
        pref_form = PreferencesUpdateForm(request.POST, instance=profile)
        
        if user_form.is_valid() and pref_form.is_valid():
            user_form.save()
            pref_form.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
    else:
        user_form = ProfileUpdateForm(instance=user)
        pref_form = PreferencesUpdateForm(instance=profile)
    
    context = {
        'user_form': user_form,
        'pref_form': pref_form,
        'profile': profile
    }
    
    return render(request, 'profile.html', context)


@login_required
def user_dashboard_auth(request):
    """Authenticated user dashboard"""
    user = request.user
    profile = user.profile
    session_id = get_or_create_session(request)
    
    # Get user's votes
    user_votes = Vote.objects.filter(session_id=session_id)
    upvotes = user_votes.filter(vote_type='up').count()
    downvotes = user_votes.filter(vote_type='down').count()
    
    # Get user's comments
    user_comments = Comment.objects.filter(session_id=session_id)
    
    # Get recent activity
    recent_votes = user_votes.order_by('-created_at')[:10]
    recent_comments = user_comments.order_by('-created_at')[:10]
    
    context = {
        'user': user,
        'profile': profile,
        'upvotes': upvotes,
        'downvotes': downvotes,
        'total_comments': user_comments.count(),
        'recent_votes': recent_votes,
        'recent_comments': recent_comments,
    }
    
    return render(request, 'user_dashboard.html', context)


def get_user_stats_auth(request):
    """Get authenticated user statistics"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    user = request.user
    profile = user.profile
    session_id = get_or_create_session(request)
    
    # Get user votes
    user_votes = Vote.objects.filter(session_id=session_id)
    upvotes = user_votes.filter(vote_type='up').count()
    downvotes = user_votes.filter(vote_type='down').count()
    
    # Get user comments
    user_comments = Comment.objects.filter(session_id=session_id)
    
    # Get preferences as dict
    if isinstance(profile.preferred_categories, list):
        # Convert list to dict with equal scores
        preferences = {cat: 5.0 for cat in profile.preferred_categories}
    else:
        preferences = profile.preferred_categories or {}
    
    # Find favorite category
    if preferences:
        favorite_category = max(preferences.items(), key=lambda x: x[1] if isinstance(x[1], (int, float)) else 5)[0]
    else:
        favorite_category = 'None'
    
    # Get recent activity
    recent_votes = user_votes.select_related('article').order_by('-created_at')[:10]
    recent_comments = user_comments.select_related('article').order_by('-created_at')[:10]
    
    activity = []
    
    for vote in recent_votes:
        activity.append({
            'title': vote.article.title[:60] + '...',
            'type': 'Upvoted' if vote.vote_type == 'up' else 'Downvoted',
            'time': get_relative_time(vote.created_at)
        })
    
    for comment in recent_comments:
        activity.append({
            'title': comment.article.title[:60] + '...',
            'type': 'Commented',
            'time': get_relative_time(comment.created_at)
        })
    
    stats = {
        'articles_read': profile.total_articles_read,
        'upvotes_given': upvotes,
        'downvotes_given': downvotes,
        'comments_posted': user_comments.count(),
        'favorite_category': favorite_category.title(),
        'preferences': preferences,
        'recent_activity': activity[:10],
        'user_info': {
            'username': user.username,
            'full_name': f"{user.first_name} {user.last_name}",
            'email': user.email,
            'joined': user.date_joined.strftime('%B %Y')
        }
    }
    
    return JsonResponse(stats)