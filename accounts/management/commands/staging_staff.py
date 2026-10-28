"""Explicitly grant a tester staff access; never promote a phone during login."""
import re
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from accounts.models import User


class Command(BaseCommand):
    help = 'Create or promote a phone account to creator in private staging only.'

    def add_arguments(self, parser):
        parser.add_argument('phone')

    def handle(self, *args, **options):
        if not getattr(settings, 'STAGING_TEST_MODE', False):
            raise CommandError('This command is only available in private staging.')
        phone = options['phone']
        if not re.fullmatch(r'09[0-9]{9}', phone):
            raise CommandError('Use an Iranian mobile number with ASCII digits, starting 09.')
        user = User.objects.filter(phone=phone).first()
        if user is None:
            user = User.objects.create_user(phone)
        if not user.is_active:
            raise CommandError('The existing account is inactive; review it before granting access.')
        user.role = 'creator'
        user.save(update_fields=['role'])
        self.stdout.write('Staging staff access granted.')
