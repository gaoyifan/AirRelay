#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import sys
import time

import paho.mqtt.client as mqtt


def send_test_sms(
    sender_phone,
    message_content,
    imei,
    mqtt_host="localhost",
    mqtt_port=1883,
    mqtt_user=None,
    mqtt_password=None,
    mqtt_use_tls=False,
):
    """Send a test SMS message via MQTT as if it came from an Air780E device"""
    # Format phone number
    if not sender_phone.startswith("+"):
        sender_phone = "+" + sender_phone

    # Prepare message payload
    timestamp = int(time.time())
    sms_message = {
        "sender": sender_phone,
        "recipient": "+10000000000",  # Simulated device number
        "content": message_content,
        "timestamp": timestamp,
        "imei": imei,
    }

    # Set up MQTT client
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    # Set up credentials if provided
    if mqtt_user and mqtt_password:
        client.username_pw_set(mqtt_user, mqtt_password)

    # Set up TLS if enabled
    if mqtt_use_tls:
        client.tls_set()

    # Connect to broker
    try:
        client.connect(mqtt_host, mqtt_port)
    except Exception as e:
        print(f"Error connecting to MQTT broker: {e}")
        return False

    # Publish message
    result = client.publish("sms/incoming", json.dumps(sms_message))

    # Check result
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        print(f"Failed to publish message: {result}")
        return False

    print(f"SMS message sent successfully from {sender_phone} via device {imei}")
    print(f"Content: {message_content}")

    # Disconnect
    client.disconnect()
    return True


def main():
    """Command line interface for sending test SMS messages"""
    parser = argparse.ArgumentParser(description="Send test SMS message via MQTT")
    parser.add_argument("--sender", "-s", required=True, help="Sender phone number")
    parser.add_argument("--message", "-m", required=True, help="SMS message content")
    parser.add_argument("--imei", "-i", required=True, help="Device IMEI")
    parser.add_argument("--mqtt-host", default="localhost", help="MQTT broker host")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--mqtt-user", default="test2", help="MQTT broker username")
    parser.add_argument("--mqtt-password", default="test", help="MQTT broker password")
    parser.add_argument("--mqtt-use-tls", help="Use TLS for MQTT connection")

    args = parser.parse_args()

    # Send the SMS
    success = send_test_sms(
        args.sender,
        args.message,
        args.imei,
        args.mqtt_host,
        args.mqtt_port,
        args.mqtt_user,
        args.mqtt_password,
        args.mqtt_use_tls,
    )

    # Exit with appropriate status code
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
