from django.core.management.base import BaseCommand
from house.mqtt import MQTTBridge


class Command(BaseCommand):
    help = "Run the MQTT subscriber that persists device state in Django."

    def handle(self, *args, **options):
        self.stdout.write("Starting Smart House MQTT bridge")
        MQTTBridge().run_forever()
