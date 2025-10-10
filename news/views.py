from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import F, Q, Count, Sum
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

    # Get articles based on category
    if category == 'all':
        # For "All News", prioritize headlines (high votes/comments) then regular news
        from django.db.models import Count
        
        # Get top headlines first (articles with most votes and comments)
        headlines = NewsArticle.objects.annotate(
            comment_count=Count('comments'),
            total_engagement=F('upvotes') + F('downvotes') + Count('comments')
        ).order_by('-total_engagement', '-upvotes', '-published_date')[:10]
        
        # Get regular news from all categories (excluding already selected headlines)
        headline_ids = [h.id for h in headlines]
        regular_news = NewsArticle.objects.exclude(id__in=headline_ids).order_by('-published_date')[:20]
        
        # Combine: headlines first, then regular news
        articles = list(headlines) + list(regular_news)
    else:
        # For specific categories, filter by category
        articles = NewsArticle.objects.filter(category=category).order_by('-published_date')
    
    # Apply search filter if provided
    if search_query:
        articles = articles.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    # Calculate personalized scores
    articles_with_scores = [
        (a, calculate_personalized_score(a, preferences))
        for a in articles
    ]
    
    # Sort by score
    articles_with_scores.sort(key=lambda x: x[1], reverse=True)
    
    # Get user votes
    user_votes = Vote.objects.filter(
        session_id=session_id,
        article__in=[a[0] for a in articles_with_scores]
    ).values('article_id', 'vote_type')
    user_votes_dict = {v['article_id']: v['vote_type'] for v in user_votes}
    
    # Prepare response data
    news_data = []
    for article, score in articles_with_scores[:20]:  # Top 20 articles
        comments = [
            {
                'author': c.author_name,
                'text': c.text,
                'created_at': c.created_at.strftime('%Y-%m-%d %H:%M')
            }
            for c in article.comments.all()[:5]
        ]
        
        # Check if article is from preferred category
        is_personalized = article.category in preferences
        
        news_data.append({
            'id': article.id,
            'title': article.title,
            'description': article.description,
            'category': article.category,
            'source': article.source,
            'time': get_relative_time(article.published_date),
            'image': article.image_url,
            'upvotes': article.upvotes,
            'downvotes': article.downvotes,
            'views': article.views,
            'user_vote': user_votes_dict.get(article.id),
            'comments': comments,
            'score': round(score, 2),
            'personalized': is_personalized
        })
    
    return JsonResponse({
        'news': news_data,
        'user_preferences': list(preferences.keys()),
        'total_articles': len(news_data)
    })

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
                # Update profile stats if authenticated
                if request.user.is_authenticated:
                    prof = request.user.profile
                    if vote_type == 'up':
                        prof.total_upvotes = F('total_upvotes') - 1
                    else:
                        prof.total_downvotes = F('total_downvotes') - 1
                    prof.save()
                    prof.refresh_from_db()
                existing_vote.delete()
                article.refresh_from_db()
                return JsonResponse({'status': 'success', 'upvotes': article.upvotes, 'downvotes': article.downvotes})
            else:
                # Change vote
                if old == 'up':
                    article.upvotes = F('upvotes') - 1
                    article.downvotes = F('downvotes') + 1
                else:
                    article.downvotes = F('downvotes') - 1
                    article.upvotes = F('upvotes') + 1
                article.save()
                existing_vote.vote_type = vote_type
                existing_vote.save()
                if request.user.is_authenticated:
                    prof = request.user.profile
                    if vote_type == 'up':
                        prof.total_upvotes = F('total_upvotes') + 1
                        prof.total_downvotes = F('total_downvotes') - 1
                    else:
                        prof.total_downvotes = F('total_downvotes') + 1
                        prof.total_upvotes = F('total_upvotes') - 1
                    prof.save()
                    prof.refresh_from_db()
                article.refresh_from_db()
                return JsonResponse({'status': 'success', 'upvotes': article.upvotes, 'downvotes': article.downvotes})
        else:
            # New vote
            Vote.objects.create(article=article, session_id=session_id, vote_type=vote_type)
            if vote_type == 'up':
                article.upvotes = F('upvotes') + 1
            else:
                article.downvotes = F('downvotes') + 1
            article.save()
            article.refresh_from_db()
            update_user_preferences(session_id, article.category, 1)
            if request.user.is_authenticated:
                prof = request.user.profile
                if vote_type == 'up':
                    prof.total_upvotes = F('total_upvotes') + 1
                else:
                    prof.total_downvotes = F('total_downvotes') + 1
                prof.save()
                prof.refresh_from_db()
            return JsonResponse({'status': 'success', 'upvotes': article.upvotes, 'downvotes': article.downvotes})

    except NewsArticle.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Article not found'})
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
        comment = Comment.objects.create(
            article=article,
            session_id=get_or_create_session(request),
            author_name=data.get('author_name', 'Anonymous'),
            text=data['comment']
        )
        update_user_preferences(get_or_create_session(request), article.category, 0.5)
        if request.user.is_authenticated:
            prof = request.user.profile
            prof.total_comments = F('total_comments') + 1
            prof.save()
            prof.refresh_from_db()
        return JsonResponse({
            'status': 'success',
            'comment': {
                'author': comment.author_name,
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
    total_poll_votes = PollOption.objects.all().aggregate(total=Sum('votes'))['total'] or 0

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


# -------------------- Headlines & Archive --------------------

def get_headlines(request):
    """Top articles by votes and comments"""
    articles = (
        NewsArticle.objects
        .annotate(comment_count=Count('comments'))
        .order_by(F('upvotes').desc(), F('comment_count').desc(), F('published_date').desc())[:10]
    )

    news_data = []
    for article in articles:
        comments = [
            {
                'author': c.author_name,
                'text': c.text,
                'created_at': c.created_at.strftime('%Y-%m-%d %H:%M')
            }
            for c in article.comments.all()[:5]
        ]
        news_data.append({
            'id': article.id,
            'title': article.title,
            'description': article.description,
            'category': article.category,
            'source': article.source,
            'time': get_relative_time(article.published_date),
            'image': article.image_url,
            'upvotes': article.upvotes,
            'downvotes': article.downvotes,
            'views': article.views,
            'score': article.upvotes + int(getattr(article, 'comment_count', 0)),
            'comments': comments,
        })

    return JsonResponse({'headlines': news_data})


def get_archived(request):
    """Return older news (e.g., older than 14 days)"""
    cutoff_days = int(request.GET.get('days', 14))
    cutoff = timezone.now() - timedelta(days=cutoff_days)
    articles = NewsArticle.objects.filter(published_date__lt=cutoff).order_by('-published_date')[:20]

    news_data = []
    for article in articles:
        comments = [
            {
                'author': c.author_name,
                'text': c.text,
                'created_at': c.created_at.strftime('%Y-%m-%d %H:%M')
            }
            for c in article.comments.all()[:5]
        ]
        news_data.append({
            'id': article.id,
            'title': article.title,
            'description': article.description,
            'category': article.category,
            'source': article.source,
            'time': get_relative_time(article.published_date),
            'image': article.image_url,
            'upvotes': article.upvotes,
            'downvotes': article.downvotes,
            'views': article.views,
            'comments': comments,
        })

    return JsonResponse({'archived': news_data, 'cutoff_days': cutoff_days})


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

            # Merge session preferences into profile on login
            try:
                session_id = get_or_create_session(request)
                session_pref = UserPreference.objects.filter(session_id=session_id).first()
                profile = user.profile
                if session_pref:
                    # Normalize profile prefs to dict
                    if isinstance(profile.preferred_categories, list):
                        profile_prefs = {cat: 5.0 for cat in profile.preferred_categories}
                    else:
                        profile_prefs = dict(profile.preferred_categories or {})

                    merged = dict(profile_prefs)
                    for cat, score in (session_pref.preferred_categories or {}).items():
                        base = merged.get(cat, 5.0)
                        try:
                            merged[cat] = round(min(10.0, max(0.0, (float(base) + float(score)) / 2.0)), 2)
                        except Exception:
                            merged[cat] = base

                    profile.preferred_categories = merged
                    profile.save()
            except Exception:
                pass
            
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