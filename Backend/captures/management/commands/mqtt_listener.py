# monitor/management/commands/mqtt_listener.py
import json
import signal
import sys
from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from django.db import connection

import paho.mqtt.client as mqtt

from captures.models import SiteParametre, TypeParametre, CaptureSite, Site  # adjust imports to your actual model names
from tenants.models import Client
# Helper: safe timestamp parser
def parse_timestamp(ts_str):
    try:
        # try ISO format
        return timezone.make_aware(datetime.fromisoformat(ts_str.replace("Z", "+00:00")))
    except Exception:
        return timezone.now()

class Command(BaseCommand):
    help = "Starts MQTT listener and writes incoming sensor data to DB (SiteParametre). Tenant-aware."

    def add_arguments(self, parser):
        parser.add_argument(
            "--broker", dest="broker", default=settings.MQTT.get("BROKER_HOST", "localhost")
        )
        parser.add_argument("--port", dest="port", default=settings.MQTT.get("BROKER_PORT", 1883), type=int)
        parser.add_argument("--topic", dest="topic", default=settings.MQTT.get("TOPIC", "sensors/#"))

    def handle(self, *args, **options):
        broker = options["broker"]
        port = options["port"]
        topic = options["topic"]
        qos = settings.MQTT.get("QOS", 0)

        client = mqtt.Client()

        username = settings.MQTT.get("USERNAME")
        password = settings.MQTT.get("PASSWORD")
        if username and password:
            client.username_pw_set(username, password)

        def on_connect(client, userdata, flags, rc, properties=None):
            if rc == 0:
                self.stdout.write(self.style.SUCCESS(f"Connected to MQTT broker {broker}:{port}"))
                client.subscribe(topic, qos=qos)
                self.stdout.write(self.style.SUCCESS(f"Subscribed to topic: {topic}"))
            else:
                self.stderr.write(self.style.ERROR(f"Failed to connect, return code {rc}"))

        def on_message(client, userdata, msg):
            try:
                payload = msg.payload.decode("utf-8")
                self.stdout.write(f"Message on {msg.topic}: {payload}")

                # topic expected: {base}/{tenant_id}/{site_id}/{parameter}
                parts = msg.topic.split("/")
                if len(parts) < 4:
                    self.stderr.write(f"Invalid topic, not enough parts: {parts}")
                    return

                # get base topic from settings if present (fallback ok)
                base_topic = settings.MQTT.get("BASE_TOPIC", None)
                # If base_topic is set and doesn't match, we still accept if structure tenant/site/param present.
                # Extract tenant/site/param assuming they are at indices 1,2,3
                tenant_str = parts[1]
                site_str = parts[2]
                type_name = parts[3]

                try:
                    tenant_id = int(tenant_str)
                    site_id = int(site_str)
                except Exception:
                    self.stderr.write(f"Invalid tenant_id or site_id in topic: {tenant_str}, {site_str}")
                    return

                # Lookup tenant in public schema
                tenant = Client.objects.filter(id=tenant_id).first()
                if not tenant:
                    self.stderr.write(f"No tenant found with id={tenant_id}")
                    return

                schema_name = tenant.schema_name

                # switch to tenant schema
                connection.set_schema(schema_name)

                # parse payload JSON (expecting at least "value")
                try:
                    data = json.loads(payload)
                except Exception:
                    self.stderr.write("Payload is not valid JSON")
                    return

                # Prefer payload['value']; else try to match parameter names in payload
                raw_value = data.get("value", None)
                if raw_value is None:
                    # some devices send "temp", "temperature", "noise", etc. try reasonable fallbacks
                    if type_name in data:
                        raw_value = data.get(type_name)
                    elif "temp" in data:
                        raw_value = data.get("temp")
                    elif "temperature" in data:
                        raw_value = data.get("temperature")
                    elif "noise" in data:
                        raw_value = data.get("noise")
                    # add more fallbacks if you expect others

                if raw_value is None:
                    self.stderr.write(f"No numeric value found in payload for parameter '{type_name}': {data}")
                    return

                # convert to float
                try:
                    value = float(raw_value)
                except Exception:
                    self.stderr.write(f"Value is not a number: {raw_value}")
                    return

                timestamp = data.get("timestamp", None)
                date_heure = parse_timestamp(timestamp) if timestamp else timezone.now()

                # find TypeParametre inside tenant schema (must exist)
                type_obj = TypeParametre.objects.filter(site__id=site_id, nom=type_name).first()
                if not type_obj:
                    self.stderr.write(f"[{schema_name}] No TypeParametre for site {site_id} with nom='{type_name}'. Skipping.")
                    return

                # finally create the SiteParametre
                sp = SiteParametre.objects.create(
                    typeParametre=type_obj,
                    valeur=value,
                    date_heure=date_heure
                )
                self.stdout.write(self.style.SUCCESS(f"[{schema_name}] Saved SiteParametre id={sp.id} value={value}"))

            except Exception as e:
                self.stderr.write(f"Error in on_message: {e}")
            finally:
                # always switch back to public schema
                try:
                    connection.set_schema_to_public()
                except Exception:
                    pass


        client.on_connect = on_connect
        client.on_message = on_message

        # graceful shutdown function
        def stop(signum, frame):
            self.stdout.write("Stopping MQTT client...")
            try:
                client.disconnect()
            except Exception:
                pass
            sys.exit(0)

        signal.signal(signal.SIGINT, stop)
        signal.signal(signal.SIGTERM, stop)

        client.connect(broker, port, keepalive=60)
        client.loop_forever()