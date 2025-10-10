from django.core.management.base import BaseCommand
from news.models import NewsArticle, Poll, PollOption
from django.utils import timezone
from datetime import timedelta
import random

class Command(BaseCommand):
    help = 'Load sample news data into the database'

    def handle(self, *args, **kwargs):
        self.stdout.write('Loading sample news data...')
        
        # Clear existing data
        NewsArticle.objects.all().delete()
        Poll.objects.all().delete()
        
        # Sample news articles
        articles_data = [
            {
                'title': 'AI Revolution: New Breakthrough in Machine Learning Transforms Industries',
                'description': 'Researchers have unveiled a groundbreaking AI system that promises to revolutionize how we approach complex problem-solving across multiple sectors.',
                'content': 'In a major development, scientists at leading research institutions have demonstrated a new approach to machine learning that significantly improves accuracy and efficiency. The system has shown promising results in healthcare diagnostics, financial forecasting, and climate modeling.',
                'category': 'technology',
                'source': 'TechCrunch',
                'source_url': 'https://techcrunch.com',
                'image_url': 'https://images.unsplash.com/photo-1488590528505-98d2b5aba04b?w=800',
                'credibility_score': 9,
                'upvotes': 42,
                'downvotes': 3,
                'views': 1250,
                'published_date': timezone.now() - timedelta(hours=2)
            },
            {
                'title': 'Historic Win: Underdog Team Claims Championship Against All Odds',
                'description': 'In an unprecedented turn of events, the underdog team secured victory in the final moments of the championship match.',
                'content': 'The championship match ended in dramatic fashion as the underdog team scored in the final seconds to secure a historic victory. Fans erupted in celebration as the final whistle confirmed one of the greatest upsets in sports history.',
                'category': 'sports',
                'source': 'ESPN',
                'source_url': 'https://espn.com',
                'image_url': 'https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=800',
                'credibility_score': 10,
                'upvotes': 128,
                'downvotes': 5,
                'views': 3400,
                'published_date': timezone.now() - timedelta(hours=5)
            },
            {
                'title': 'Stock Market Reaches New Heights as Tech Sector Surges',
                'description': 'Major tech companies lead the market rally with impressive quarterly earnings reports exceeding analyst expectations.',
                'content': 'Wall Street celebrated another record-breaking day as the tech-heavy indices climbed to new all-time highs. Strong earnings from major technology companies drove investor confidence and market momentum.',
                'category': 'business',
                'source': 'Bloomberg',
                'source_url': 'https://bloomberg.com',
                'image_url': 'https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800',
                'credibility_score': 9,
                'upvotes': 67,
                'downvotes': 8,
                'views': 2100,
                'published_date': timezone.now() - timedelta(hours=1)
            },
            {
                'title': 'Medical Breakthrough: New Treatment Shows Promise for Chronic Disease',
                'description': 'Clinical trials reveal encouraging results for a novel therapy targeting previously incurable conditions.',
                'content': 'Medical researchers have announced promising results from phase III clinical trials of a new treatment approach. The therapy has shown significant improvements in patient outcomes with minimal side effects.',
                'category': 'health',
                'source': 'Medical News Today',
                'source_url': 'https://medicalnewstoday.com',
                'image_url': 'https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=800',
                'credibility_score': 8,
                'upvotes': 89,
                'downvotes': 4,
                'views': 1800,
                'published_date': timezone.now() - timedelta(hours=3)
            },
            {
                'title': 'Space Telescope Discovers Potentially Habitable Exoplanet',
                'description': 'Astronomers identify a planet in the habitable zone with conditions that might support life.',
                'content': 'Using advanced space telescopes, scientists have detected a planet orbiting a nearby star that shows signs of water vapor in its atmosphere. The discovery adds to the growing list of potentially habitable worlds beyond our solar system.',
                'category': 'science',
                'source': 'NASA News',
                'source_url': 'https://nasa.gov',
                'image_url': 'https://images.unsplash.com/photo-1614730321146-b6fa6a46bcb4?w=800',
                'credibility_score': 10,
                'upvotes': 156,
                'downvotes': 7,
                'views': 4200,
                'published_date': timezone.now() - timedelta(hours=6)
            },
            {
                'title': 'Box Office Smash: New Film Breaks Opening Weekend Records',
                'description': 'The highly anticipated blockbuster exceeds expectations with record-breaking ticket sales.',
                'content': 'Moviegoers flocked to theaters this weekend as the latest blockbuster shattered opening weekend records. The film has been praised for its stunning visuals and compelling storytelling.',
                'category': 'entertainment',
                'source': 'Variety',
                'source_url': 'https://variety.com',
                'image_url': 'https://images.unsplash.com/photo-1536440136628-849c177e76a1?w=800',
                'credibility_score': 7,
                'upvotes': 73,
                'downvotes': 12,
                'views': 2800,
                'published_date': timezone.now() - timedelta(hours=8)
            },
            {
                'title': 'Climate Summit: World Leaders Agree on New Environmental Targets',
                'description': 'International conference concludes with commitments to reduce emissions and protect ecosystems.',
                'content': 'After days of intense negotiations, world leaders have reached a consensus on ambitious new climate targets. The agreement includes specific milestones for reducing carbon emissions and transitioning to renewable energy.',
                'category': 'world',
                'source': 'Reuters',
                'source_url': 'https://reuters.com',
                'image_url': 'https://images.unsplash.com/photo-1569163139394-de4798aa62b6?w=800',
                'credibility_score': 9,
                'upvotes': 94,
                'downvotes': 15,
                'views': 3100,
                'published_date': timezone.now() - timedelta(hours=4)
            },
            {
                'title': 'Tech Giant Announces Revolutionary Smartphone with Week-Long Battery',
                'description': 'New device features breakthrough battery technology that eliminates daily charging.',
                'content': 'The technology industry is buzzing with excitement over the announcement of a smartphone that can run for seven days on a single charge. The innovation could reshape consumer expectations for mobile devices.',
                'category': 'technology',
                'source': 'The Verge',
                'source_url': 'https://theverge.com',
                'image_url': 'https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?w=800',
                'credibility_score': 8,
                'upvotes': 112,
                'downvotes': 9,
                'views': 3700,
                'published_date': timezone.now() - timedelta(hours=7)
            },
            {
                'title': 'Olympic Athletes Set Multiple World Records in Historic Competition',
                'description': 'Several long-standing records fall as athletes push the boundaries of human performance.',
                'content': 'The athletics world is celebrating after multiple world records were broken in a single day of competition. Athletes credited improved training methods and sports science for the remarkable achievements.',
                'category': 'sports',
                'source': 'Sports Illustrated',
                'source_url': 'https://si.com',
                'image_url': 'https://images.unsplash.com/photo-1587280501635-68a0e82cd5ff?w=800',
                'credibility_score': 9,
                'upvotes': 145,
                'downvotes': 6,
                'views': 4500,
                'published_date': timezone.now() - timedelta(hours=9)
            },
            {
                'title': 'Startup Secures Record Funding for Renewable Energy Innovation',
                'description': 'Investment round values clean energy company at over $1 billion.',
                'content': 'A startup focused on renewable energy storage has raised a record amount in its latest funding round. Investors are betting on the company\'s innovative approach to solving energy grid challenges.',
                'category': 'business',
                'source': 'Forbes',
                'source_url': 'https://forbes.com',
                'image_url': 'https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=800',
                'credibility_score': 8,
                'upvotes': 78,
                'downvotes': 11,
                'views': 2300,
                'published_date': timezone.now() - timedelta(hours=10)
            },
        ]
        
        # Create articles
        for article_data in articles_data:
            NewsArticle.objects.create(**article_data)
            self.stdout.write(self.style.SUCCESS(f'Created: {article_data["title"][:50]}...'))
        
        # Create sample poll
        poll = Poll.objects.create(
            question='Which news category interests you most?',
            is_active=True
        )
        
        poll_options = [
            {'text': 'Technology', 'votes': 145},
            {'text': 'Sports', 'votes': 98},
            {'text': 'Business', 'votes': 76},
            {'text': 'Entertainment', 'votes': 54},
            {'text': 'Health', 'votes': 89},
            {'text': 'Science', 'votes': 112},
        ]
        
        for option_data in poll_options:
            PollOption.objects.create(poll=poll, **option_data)
        
        self.stdout.write(self.style.SUCCESS('\nSample data loaded successfully!'))
        self.stdout.write(self.style.SUCCESS(f'Total articles: {NewsArticle.objects.count()}'))
        self.stdout.write(self.style.SUCCESS(f'Total polls: {Poll.objects.count()}'))