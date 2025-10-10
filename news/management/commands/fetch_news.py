from django.core.management.base import BaseCommand
from news.scraper import fetch_and_save_news

class Command(BaseCommand):
    help = 'Fetch latest news from NewsAPI and save to database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--categories',
            nargs='+',
            type=str,
            help='Categories to fetch (technology sports business entertainment health science)',
            default=None
        )
        parser.add_argument(
            '--count',
            type=int,
            help='Number of articles per category',
            default=5
        )

    def handle(self, *args, **options):
        categories = options['categories']
        count = options['count']
        
        self.stdout.write(self.style.WARNING('Fetching news from NewsAPI...'))
        
        stats = fetch_and_save_news(categories=categories, articles_per_category=count)
        
        self.stdout.write(self.style.SUCCESS('\n--- Fetch Complete ---'))
        self.stdout.write(f"Total fetched: {stats['total_fetched']}")
        self.stdout.write(f"Total saved: {stats['total_saved']}")
        self.stdout.write(f"Duplicates skipped: {stats['total_fetched'] - stats['total_saved']}")
        
        self.stdout.write('\nBy category:')
        for category, count in stats['by_category'].items():
            self.stdout.write(f"  {category}: {count} articles")