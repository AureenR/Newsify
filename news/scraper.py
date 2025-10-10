import requests
from datetime import datetime
from django.utils import timezone
from .models import NewsArticle

# NewsAPI Configuration
NEWS_API_KEY = '267f3830acbd45e4b1bdfd28c64419f9'  
NEWS_API_URL = 'https://newsapi.org/v2/top-headlines'

# Category mapping (NewsAPI categories to our categories)
CATEGORY_MAPPING = {
    'technology': 'technology',
    'sports': 'sports',
    'business': 'business',
    'entertainment': 'entertainment',
    'health': 'health',
    'science': 'science',
    'general': 'world',
}

# Source credibility scores (you can customize these)
SOURCE_CREDIBILITY = {
    'bbc-news': 10,
    'reuters': 10,
    'the-wall-street-journal': 9,
    'bloomberg': 9,
    'cnn': 8,
    'techcrunch': 8,
    'espn': 9,
    'the-verge': 8,
    'ars-technica': 8,
    'wired': 8,
    'default': 7
}

def get_credibility_score(source_name):
    """Get credibility score for a news source"""
    source_id = source_name.lower().replace(' ', '-')
    return SOURCE_CREDIBILITY.get(source_id, SOURCE_CREDIBILITY['default'])

def fetch_news_by_category(category='general', country='us', page_size=10):
    """
    Fetch news from NewsAPI for a specific category
    
    Args:
        category: News category (technology, sports, business, etc.)
        country: Country code (us, in, gb, etc.)
        page_size: Number of articles to fetch (max 100)
    
    Returns:
        List of articles or None if error
    """
    try:
        params = {
            'apiKey': NEWS_API_KEY,
            'category': category,
            'country': country,
            'pageSize': page_size,
            'sortBy': 'publishedAt'
        }
        
        response = requests.get(NEWS_API_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data['status'] == 'ok':
                return data['articles']
            else:
                print(f"API Error: {data.get('message', 'Unknown error')}")
                return None
        else:
            print(f"HTTP Error: {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return None

def save_article_to_db(article_data, category):
    """
    Save a news article to the database
    
    Args:
        article_data: Article data from NewsAPI
        category: Category to assign to the article
    
    Returns:
        Created article or None if already exists
    """
    try:
        # Check if article already exists (by URL)
        url = article_data.get('url', '')
        if NewsArticle.objects.filter(source_url=url).exists():
            return None
        
        # Parse published date
        published_at = article_data.get('publishedAt')
        if published_at:
            published_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
        else:
            published_date = timezone.now()
        
        # Get source information
        source = article_data.get('source', {})
        source_name = source.get('name', 'Unknown')
        
        # Create article
        article = NewsArticle.objects.create(
            title=article_data.get('title', 'No title'),
            description=article_data.get('description', '')[:500] if article_data.get('description') else '',
            content=article_data.get('content', ''),
            category=category,
            source=source_name,
            source_url=url,
            image_url=article_data.get('urlToImage', ''),
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

def fetch_and_save_news(categories=None, articles_per_category=5):
    """
    Fetch news from NewsAPI and save to database
    
    Args:
        categories: List of categories to fetch (None = all)
        articles_per_category: Number of articles per category
    
    Returns:
        Dictionary with stats
    """
    if categories is None:
        categories = list(CATEGORY_MAPPING.keys())
    
    stats = {
        'total_fetched': 0,
        'total_saved': 0,
        'by_category': {}
    }
    
    for api_category in categories:
        our_category = CATEGORY_MAPPING.get(api_category, 'world')
        
        print(f"\nFetching {api_category} news...")
        articles = fetch_news_by_category(api_category, page_size=articles_per_category)
        
        if articles:
            saved_count = 0
            for article_data in articles:
                stats['total_fetched'] += 1
                
                saved_article = save_article_to_db(article_data, our_category)
                if saved_article:
                    saved_count += 1
                    stats['total_saved'] += 1
                    print(f"✓ Saved: {saved_article.title[:60]}...")
            
            stats['by_category'][our_category] = saved_count
            print(f"Saved {saved_count}/{len(articles)} articles for {api_category}")
    
    return stats

def search_news(query, language='en', page_size=10):
    """
    Search for specific news topics
    
    Args:
        query: Search query
        language: Language code
        page_size: Number of results
    
    Returns:
        List of articles
    """
    try:
        params = {
            'apiKey': NEWS_API_KEY,
            'q': query,
            'language': language,
            'pageSize': page_size,
            'sortBy': 'publishedAt'
        }
        
        response = requests.get(
            'https://newsapi.org/v2/everything',
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data['status'] == 'ok':
                return data['articles']
        
        return None
        
    except Exception as e:
        print(f"Search failed: {e}")
        return None