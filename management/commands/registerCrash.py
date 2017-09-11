from django.core.management.base import BaseCommand
from monitor.mon import runThroughCrash


class Command(BaseCommand):
    help = 'Registers a crash on a specified host'

    def add_arguments(self, parser):
        parser.add_argument('host_address', nargs='1', type=str)

    def handle(self, *args, **options):
        addr = options["host_address"][0]
        assert "host" in addr and "jc.rl.ac.uk" in addr
        runThroughCrash(addr)
