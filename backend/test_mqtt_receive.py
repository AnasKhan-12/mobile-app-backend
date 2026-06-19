"""
Quick MQTT test — run this to verify your hardware is publishing correctly.
Press Ctrl+C to stop.

Subscribes to:
  - abdul_bms/power_temp
  - abdul_bms/cell_voltages
"""

import json
import paho.mqtt.client as mqtt

BROKER = "broker.hivemq.com"
PORT   = 1883
TOPICS = ["abdul_bms/power_temp", "abdul_bms/cell_voltages"]


def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print(f"✅ Connected to {BROKER}:{PORT}")
        for topic in TOPICS:
            client.subscribe(topic, qos=0)
            print(f"📡 Subscribed to: {topic}")
        print("\nWaiting for messages from your hardware... (Ctrl+C to stop)\n")
    else:
        print(f"❌ Connection failed (rc={rc})")


def on_message(client, userdata, msg):
    topic   = msg.topic
    payload = msg.payload.decode("utf-8")

    try:
        data = json.loads(payload)
        pretty = json.dumps(data, indent=2)
    except json.JSONDecodeError:
        pretty = payload  # show raw if not JSON

    print(f"──────────────────────────────────")
    print(f"📨 Topic  : {topic}")
    print(f"📦 Payload:\n{pretty}")


def on_disconnect(client, userdata, rc, properties=None):
    print(f"\n🔌 Disconnected (rc={rc})")


client = mqtt.Client(client_id="bms_test_listener", protocol=mqtt.MQTTv5)
client.on_connect    = on_connect
client.on_message    = on_message
client.on_disconnect = on_disconnect

print(f"Connecting to {BROKER}:{PORT} ...")
client.connect(BROKER, PORT, keepalive=60)

try:
    client.loop_forever()
except KeyboardInterrupt:
    print("\n👋 Stopped.")
    client.disconnect()
