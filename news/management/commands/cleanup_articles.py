from django.core.management.base import BaseCommand
from news.models import NewsArticle
from news.scraper import check_article_status

class Command(BaseCommand):
    help = 'Checks existence of all existing news articles and deletes stale/removed ones.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Starting stale article cleanup... This may take a moment."))
        
        articles_to_check = NewsArticle.objects.all()
        total_checked = articles_to_check.count()
        deleted_count = 0
        
        for article in articles_to_check:
            # Check the URL status using the helper function from scraper.py
            is_live = check_article_status(article.source_url)
            
            if not is_live:
                article_title = article.title
                article.delete()
                deleted_count += 1
                # Truncate title for clean console output
                self.stdout.write(self.style.SUCCESS(f"🗑️ Deleted: {article_title[:60]}... (URL check failed)"))
        
        self.stdout.write(self.style.WARNING(f"\n--- Cleanup Complete ---"))
        self.stdout.write(self.style.SUCCESS(f"Total articles checked: {total_checked}"))
        self.stdout.write(self.style.SUCCESS(f"Total articles deleted: {deleted_count}"))
        self.stdout.write(self.style.WARNING("To automate, schedule this command (e.g., via cron) to run daily."))