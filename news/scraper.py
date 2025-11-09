import requests
from datetime import datetime
from django.utils import timezone
from .models import NewsArticle

# ==================== API KEYS ====================
# Get free API keys from:
# NewsAPI: https://newsapi.org/register
# NewsData.io: https://newsdata.io/register
# The Guardian: https://open-platform.theguardian.com/access/
# NYTimes: https://developer.nytimes.com/get-started
# GNews: https://gnews.io/register

NEWS_API_KEY = '267f3830acbd45e4b1bdfd28c64419f9'
NEWSDATA_API_KEY = 'pub_cde35b14c3474f5689c7497ec6cd2f6c'
GUARDIAN_API_KEY = 'da02a924-6607-4b2b-9ede-c874c056758f'
#NYTIMES_API_KEY = 'YOUR_NYTIMES_KEY'
GNEWS_API_KEY = '958daa01aadda9e82eec21d3a007b053'

# ==================== API URLs ====================
NEWS_API_URL = 'https://newsapi.org/v2/top-headlines'
NEWSDATA_URL = 'https://newsdata.io/api/1/news'
GUARDIAN_URL = 'https://content.guardianapis.com/search'
NYTIMES_URL = 'https://api.nytimes.com/svc/topstories/v2'
GNEWS_URL = 'https://gnews.io/api/v4/top-headlines'

# Category mapping
CATEGORY_MAPPING = {
    'technology': 'technology',
    'sports': 'sports',
    'business': 'business',
    'entertainment': 'entertainment',
    'health': 'health',
    'science': 'science',
    'general': 'world',
}

# Source credibility scores
SOURCE_CREDIBILITY = {
    'bbc-news': 10,
    'reuters': 10,
    'the-wall-street-journal': 9,
    'bloomberg': 9,
    'cnn': 8,
    'techcrunch': 8,
    'espn': 9,
    'the-verge': 8,
    'the-guardian': 9,
    'new-york-times': 10,
    'associated-press': 10,
    'default': 7
}

def get_credibility_score(source_name):
    """Get credibility score for a news source"""
    source_id = source_name.lower().replace(' ', '-')
    return SOURCE_CREDIBILITY.get(source_id, SOURCE_CREDIBILITY['default'])

def save_article_to_db(article_data, category):
    """Save a news article to the database"""
    try:
        url = article_data.get('url', '')
        if not url or NewsArticle.objects.filter(source_url=url).exists():
            return None
        
        title = article_data.get('title', '')
        if '[Removed]' in title or not title:
            return None
        
        published_at = article_data.get('publishedAt') or article_data.get('published_date')
        if published_at:
            try:
                published_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            except:
                published_date = timezone.now()
        else:
            published_date = timezone.now()
        
        source_name = article_data.get('source', 'Unknown')
        if isinstance(source_name, dict):
            source_name = source_name.get('name', 'Unknown')
        
        article = NewsArticle.objects.create(
            title=title,
            description=article_data.get('description', '')[:500] if article_data.get('description') else '',
            content=article_data.get('content', ''),
            category=category,
            source=source_name,
            source_url=url,
            image_url=article_data.get('image_url') or article_data.get('urlToImage', ''),
            published_date=published_date,
            credibility_score=get_credibility_score(source_name),
            upvotes=0,
            downvotes=0,
            views=0
        )
        
        return article
        
    except Exception as e:
        print(f"Error saving article: {e}")
        return None

# ==================== NEWS API (Original) ====================
def fetch_newsapi(category='general', page_size=100, page=1):
    """Fetch from NewsAPI.org"""
    try:
        params = {
            'apiKey': NEWS_API_KEY,
            'category': category,
            'country': 'us',
            'pageSize': page_size,
            'page': page,
        }
        
        response = requests.get(NEWS_API_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'ok':
                return data['articles']
        return None
    except Exception as e:
        print(f"NewsAPI error: {e}")
        return None

# ==================== NEWSDATA.IO ====================
def fetch_newsdata(category='top', language='en', page_size=10):
    """
    Fetch from NewsData.io
    Free tier: 200 requests/day
    Categories: top, business, entertainment, health, science, sports, technology
    """
    try:
        if NEWSDATA_API_KEY == 'YOUR_NEWSDATA_KEY':
            return None
        
        params = {
            'apikey': NEWSDATA_API_KEY,
            'language': language,
            'category': category,
            'size': page_size,
        }
        
        response = requests.get(NEWSDATA_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'success':
                # Transform to common format
                articles = []
                for item in data.get('results', []):
                    articles.append({
                        'title': item.get('title'),
                        'description': item.get('description'),
                        'content': item.get('content'),
                        'url': item.get('link'),
                        'image_url': item.get('image_url'),
                        'publishedAt': item.get('pubDate'),
                        'source': item.get('source_id', 'NewsData'),
                    })
                return articles
        return None
    except Exception as e:
        print(f"NewsData.io error: {e}")
        return None

# ==================== THE GUARDIAN ====================
def fetch_guardian(section='world', page_size=50):
    """
    Fetch from The Guardian API
    Free tier: 500 requests/day (5000/day with key)
    Sections: world, business, technology, sport, culture, science
    """
    try:
        if GUARDIAN_API_KEY == 'YOUR_GUARDIAN_KEY':
            return None
        
        params = {
            'api-key': GUARDIAN_API_KEY,
            'section': section,
            'page-size': page_size,
            'show-fields': 'headline,trailText,thumbnail,body',
            'order-by': 'newest'
        }
        
        response = requests.get(GUARDIAN_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data['response']['status'] == 'ok':
                # Transform to common format
                articles = []
                for item in data['response']['results']:
                    fields = item.get('fields', {})
                    articles.append({
                        'title': fields.get('headline', item.get('webTitle')),
                        'description': fields.get('trailText', ''),
                        'content': fields.get('body', ''),
                        'url': item.get('webUrl'),
                        'image_url': fields.get('thumbnail'),
                        'publishedAt': item.get('webPublicationDate'),
                        'source': 'The Guardian',
                    })
                return articles
        return None
    except Exception as e:
        print(f"Guardian API error: {e}")
        return None

# ==================== NEW YORK TIMES ====================
def fetch_nytimes(section='home'):
    """
    Fetch from NYTimes API
    Sections: home, world, business, technology, sports, science, health
    NYTimes Top Stories API does not accept a results limit parameter.
    """
    try:
        if NYTIMES_API_KEY == 'YOUR_NYTIMES_KEY':
            return None
        
        url = f"{NYTIMES_URL}/{section}.json"
        params = {'api-key': NYTIMES_API_KEY}
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'OK':
                # Transform to common format
                articles = []
                for item in data.get('results', []):
                    image_url = ''
                    if item.get('multimedia'):
                        for media in item['multimedia']:
                            if media.get('format') == 'Large Thumbnail':
                                image_url = media.get('url')
                                break
                    
                    articles.append({
                        'title': item.get('title'),
                        'description': item.get('abstract'),
                        'content': item.get('abstract'),
                        'url': item.get('url'),
                        'image_url': image_url,
                        'publishedAt': item.get('published_date'),
                        'source': 'New York Times',
                    })
                return articles
        return None
    except Exception as e:
        print(f"NYTimes API error: {e}")
        return None

# ==================== GNEWS ====================
def fetch_gnews(category='general', lang='en', max_results=10):
    """
    Fetch from GNews API
    Free tier: 100 requests/day
    Categories: general, world, nation, business, technology, entertainment, sports, science, health
    """
    try:
        if GNEWS_API_KEY == 'YOUR_GNEWS_KEY':
            return None
        
        params = {
            'token': GNEWS_API_KEY,
            'category': category,
            'lang': lang,
            'max': max_results,
        }
        
        response = requests.get(GNEWS_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            # Transform to common format
            articles = []
            for item in data.get('articles', []):
                articles.append({
                    'title': item.get('title'),
                    'description': item.get('description'),
                    'content': item.get('content'),
                    'url': item.get('url'),
                    'image_url': item.get('image'),
                    'publishedAt': item.get('publishedAt'),
                    'source': item.get('source', {}).get('name', 'GNews'),
                })
            return articles
        return None
    except Exception as e:
        print(f"GNews API error: {e}")
        return None

# ==================== MASTER FETCH FUNCTION ====================
def fetch_from_all_apis(category='general', articles_per_category=10):
    """
    Fetch from ALL available APIs at once!
    This gives you MASSIVE amounts of diverse news
    """
    all_articles = []
    sources_used = []
    
    print(f"\n{'='*60}")
    print(f"🌐 FETCHING FROM MULTIPLE SOURCES: {category.upper()}")
    print(f"{'='*60}\n")
    
    # 1. NewsAPI - Max 100
    newsapi_size = min(100, articles_per_category)
    print(f"📰 NewsAPI.org (size={newsapi_size})...", end=' ')
    newsapi_articles = fetch_newsapi(category=category, page_size=newsapi_size)
    if newsapi_articles:
        all_articles.extend(newsapi_articles)
        sources_used.append('NewsAPI')
        print(f"✓ {len(newsapi_articles)} articles")
    else:
        print("✗ Failed")
    
    # 2. NewsData.io - Max 10 (size is 10 max)
    newsdata_size = min(10, articles_per_category)
    print(f"📰 NewsData.io (size={newsdata_size})...", end=' ')
    newsdata_articles = fetch_newsdata(category=category if category != 'general' else 'top', page_size=newsdata_size) 
    if newsdata_articles:
        all_articles.extend(newsdata_articles)
        sources_used.append('NewsData.io')
        print(f"✓ {len(newsdata_articles)} articles")
    else:
        print("✗ Skipped (no API key/failed)")
    
    # 3. The Guardian - Max 50
    guardian_size = min(50, articles_per_category)
    print(f"📰 The Guardian (size={guardian_size})...", end=' ')
    guardian_section = 'world' if category == 'general' else category
    guardian_articles = fetch_guardian(section=guardian_section, page_size=guardian_size)
    if guardian_articles:
        all_articles.extend(guardian_articles)
        sources_used.append('The Guardian')
        print(f"✓ {len(guardian_articles)} articles")
    else:
        print("✗ Skipped (no API key/failed)")
    
    # 4. NYTimes - No size parameter, but we can take the top N results later if needed.
    print("📰 New York Times...", end=' ')
    nyt_section = 'home' if category == 'general' else category
    nyt_articles = fetch_nytimes(section=nyt_section)
    if nyt_articles:
        # Slice to the requested size if NYT has more results
        nyt_articles = nyt_articles[:articles_per_category]
        all_articles.extend(nyt_articles)
        sources_used.append('NYTimes')
        print(f"✓ {len(nyt_articles)} articles")
    else:
        print("✗ Skipped (no API key/failed)")
    
    # 5. GNews - Max 10
    gnews_size = min(10, articles_per_category)
    print(f"📰 GNews (size={gnews_size})...", end=' ')
    gnews_articles = fetch_gnews(category=category, max_results=gnews_size)
    if gnews_articles:
        all_articles.extend(gnews_articles)
        sources_used.append('GNews')
        print(f"✓ {len(gnews_articles)} articles")
    else:
        print("✗ Skipped (no API key/failed)")
    
    print(f"\n✅ Total fetched: {len(all_articles)} articles from {len(sources_used)} sources")
    print(f"   Sources: {', '.join(sources_used)}\n")
    
    return all_articles

# ==================== MAIN FETCH FUNCTION ====================
def fetch_and_save_news(categories=None, articles_per_category=10, use_all_apis=True):
    """
    Fetch news from multiple APIs and save to database
    
    Args:
        categories: List of categories (None = all)
        articles_per_category: Number of articles per category (Used by single API call and passed to multi-API fetcher)
        use_all_apis: If True, fetch from all available APIs
    
    Returns:
        Dictionary with stats
    """
    if categories is None:
        categories = list(CATEGORY_MAPPING.keys())
    
    stats = {
        'total_fetched': 0,
        'total_saved': 0,
        'by_category': {},
        'by_source': {}
    }
    
    print(f"\n{'='*70}")
    print(f"🚀 MULTI-API NEWS FETCHER - {len(categories)} categories")
    print(f"{'='*70}\n")
    
    for api_category in categories:
        our_category = CATEGORY_MAPPING.get(api_category, 'world')
        
        if use_all_apis:
            # Pass the corrected arguments to the master fetcher
            articles = fetch_from_all_apis(category=api_category, articles_per_category=articles_per_category)
        else:
            # Use articles_per_category for the single API call mode
            articles = fetch_newsapi(category=api_category, page_size=articles_per_category)
        
        if articles:
            saved_count = 0
            for article_data in articles:
                stats['total_fetched'] += 1
                
                saved_article = save_article_to_db(article_data, our_category)
                if saved_article:
                    saved_count += 1
                    stats['total_saved'] += 1
                    
                    # Track by source
                    source = saved_article.source
                    stats['by_source'][source] = stats['by_source'].get(source, 0) + 1
            
            stats['by_category'][our_category] = saved_count
            print(f"   💾 Saved {saved_count} new articles for {our_category}\n")
    
    print(f"{'='*70}")
    print(f"✅ COMPLETE!")
    print(f"   Fetched: {stats['total_fetched']} articles")
    print(f"   Saved: {stats['total_saved']} NEW articles")
    print(f"   Sources: {len(stats['by_source'])}")
    print(f"{'='*70}\n")
    
    return stats


# ==================== STALE ARTICLE CHECK (NEW) ====================

def check_article_status(url):
    """
    Checks if an article's URL is still accessible (returns HTTP 200).
    Uses a HEAD request for speed.

    Returns:
        True if URL is accessible, False otherwise.
    """
    if not url:
        return False
    
    try:
        # Use HEAD request to avoid downloading the entire page content
        response = requests.head(url, timeout=5, allow_redirects=True)
        
        # We consider the article still available if status code is 200
        # or in the 3xx range (redirects are often valid updates).
        if 200 <= response.status_code < 400:
            return True
        else:
            # Codes like 404 (Not Found), 410 (Gone), 5xx (Server Error) suggest deletion
            return False
            
    except requests.exceptions.RequestException as e:
        # Catch connection errors, DNS errors, or timeouts (suggesting article is offline)
        print(f"URL check failed for {url}: {e}")
        return False