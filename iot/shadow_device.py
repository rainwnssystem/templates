import json
import time

from awscrt import mqtt
from awsiot import mqtt_connection_builder


ENDPOINT = "<AWS_IOT_ENDPOINT>"
THING_NAME = "<THING_NAME>"  # Client ID
CERT_PATH = "certs/device.pem.crt"
PRIVATE_KEY_PATH = "certs/private.pem.key"
ROOT_CA_PATH = "certs/AmazonRootCA1.pem"

SHADOW_PREFIX = f"$aws/things/{THING_NAME}/shadow"
DELTA_TOPIC = f"{SHADOW_PREFIX}/update/delta"
UPDATE_TOPIC = f"{SHADOW_PREFIX}/update"


connection = mqtt_connection_builder.mtls_from_path(
    endpoint=ENDPOINT,
    cert_filepath=CERT_PATH,
    pri_key_filepath=PRIVATE_KEY_PATH,
    ca_filepath=ROOT_CA_PATH,
    client_id=THING_NAME,
    clean_session=True,
    keep_alive_secs=30,
)


def on_delta(topic, payload, **kwargs):
    delta = json.loads(payload)["state"]
    print(f"[DELTA] {delta}")

    reported = {"state": {"reported": delta}}
    connection.publish(
        topic=UPDATE_TOPIC,
        payload=json.dumps(reported),
        qos=mqtt.QoS.AT_LEAST_ONCE,
    )
    print(f"[REPORTED] {delta}")


print("Connecting to AWS IoT Core...")
connection.connect().result()

connection.subscribe(
    topic=DELTA_TOPIC,
    qos=mqtt.QoS.AT_LEAST_ONCE,
    callback=on_delta,
)[0].result()

print(f"Waiting: {DELTA_TOPIC}")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    connection.disconnect().result()
    print("Connection disconnected.")
