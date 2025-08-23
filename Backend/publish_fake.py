# publish_fake.py
import json
import time
import random
import paho.mqtt.publish as publish

BROKER = "broker.emqx.io"
PORT = 1883
TOPIC = "m-iot/1/1/humidite"   # tenant_id=1, site_id=1, parameter=temperateur

for i in range(3):
    payload = {
        "value": round(50 + random.random() * 10, 2),
        "timestamp": "2025-08-23T12:00:00Z"
    }
    publish.single(TOPIC, json.dumps(payload), hostname=BROKER, port=PORT)
    print("Published ->", TOPIC, payload)
    time.sleep(1)




"""
import paho.mqtt.client as mqtt
import time
import Adafruit_DHT  # example sensor library

broker = "your-broker-url"
port = 1883
topic = "m-iot/{tenant_id}/{site_id}/temperature"

client = mqtt.Client()
client.connect(broker, port)

sensor = Adafruit_DHT.DHT22
pin = 4  # GPIO pin

while True:
    humidity, temp = Adafruit_DHT.read_retry(sensor, pin)
    if temp:
        client.publish(topic, temp)
    time.sleep(2)
"""