#!/usr/bin/env python
# -*- coding: utf-8 -*-

import argparse
import json
import logging
import random
import signal
import sys
import time
import uuid
from datetime import datetime

import paho.mqtt.client as mqtt
from pydantic import ValidationError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("Air780E-Simulator")


class Air780ESimulator:
    """
    Air780E device simulator for testing SMS functionality via MQTT.
    Simulates an Air780E GSM/LTE module that can send and receive SMS.
    """

    def __init__(
        self,
        imei=None,
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_user=None,
        mqtt_password=None,
        mqtt_use_tls=False,
        signal_strength=75,
        battery_level=90,
    ):
        """Initialize the simulator with device and connection parameters"""
        # Generate IMEI if not provided
        self.imei = imei or self._generate_imei()
        self.mqtt_host = mqtt_host
        self.mqtt_port = mqtt_port
        self.mqtt_user = mqtt_user
        self.mqtt_password = mqtt_password
        self.mqtt_use_tls = mqtt_use_tls
        
        # Device status
        self.signal_strength = signal_strength
        self.battery_level = battery_level
        self.device_number = "+10000000000"  # Simulated device phone number
        self.device_status = "online"
        
        # MQTT client setup
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        # Set up credentials if provided
        if self.mqtt_user and self.mqtt_password:
            self.client.username_pw_set(self.mqtt_user, self.mqtt_password)
        
        # Set up TLS if enabled
        if self.mqtt_use_tls:
            self.client.tls_set()
            
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"Initialized Air780E simulator with IMEI: {self.imei}")
        
    def _generate_imei(self):
        """Generate a random valid IMEI number"""
        # IMEI is 15 digits with the last being a check digit
        prefix = "35" + "".join([str(random.randint(0, 9)) for _ in range(12)])
        # Calculate Luhn check digit
        digits = [int(digit) for digit in prefix]
        for i in range(0, len(digits), 2):
            digits[i] *= 2
            if digits[i] > 9:
                digits[i] -= 9
        checksum = sum(digits)
        check_digit = (10 - (checksum % 10)) % 10
        return prefix + str(check_digit)
        
    def connect(self):
        """Connect to the MQTT broker"""
        try:
            self.client.connect(self.mqtt_host, self.mqtt_port)
            self.client.loop_start()
            logger.info(f"Connecting to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise
            
    def disconnect(self):
        """Disconnect from the MQTT broker"""
        self.device_status = "offline"
        self.publish_device_status()
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("Disconnected from MQTT broker")
        
    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback for when client connects to the broker"""
        if rc == 0:
            logger.info(f"Connected to MQTT broker with result code {rc}")
            # Subscribe to outgoing SMS topic for this device
            client.subscribe(f"sms/outgoing/{self.imei}")
            
            # Publish device status upon connection
            self.publish_device_status()
        else:
            logger.error(f"Failed to connect to MQTT broker, error code: {rc}")
            
    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received from the broker"""
        try:
            payload = json.loads(msg.payload.decode())
            logger.info(f"Received message on topic {msg.topic}: {payload}")
            
            # Handle outgoing SMS requests
            if msg.topic == f"sms/outgoing/{self.imei}":
                self._handle_outgoing_sms(payload)
                
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON message: {msg.payload}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            
    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Callback for when client disconnects from the broker"""
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker: {rc}")
            # Attempt to reconnect after a delay
            time.sleep(5)
            self.connect()
        else:
            logger.info("Successfully disconnected from MQTT broker")
            
    def _handle_outgoing_sms(self, payload):
        """Process an outgoing SMS message and simulate sending it"""
        try:
            # Extract message details
            recipient = payload.get("recipient")
            content = payload.get("content")
            message_id = payload.get("message_id")
            
            if not all([recipient, content, message_id]):
                logger.error("Missing required fields in outgoing SMS request")
                return
                
            logger.info(f"Sending SMS to {recipient}: {content}")
            
            # Simulate message sending delay
            time.sleep(random.uniform(0.5, 2.0))
            
            # Simulate success with 95% probability
            if random.random() < 0.95:
                status = "delivered"
                logger.info(f"Successfully delivered SMS to {recipient}")
            else:
                status = "failed"
                logger.warning(f"Failed to deliver SMS to {recipient}")
                
            # Publish delivery status
            self.publish_sms_status(message_id, status)
            
        except Exception as e:
            logger.error(f"Error handling outgoing SMS: {e}")
            
    def publish_device_status(self):
        """Publish the current device status to MQTT"""
        timestamp = int(time.time())
        
        # Randomly fluctuate signal strength and battery level for realism
        self.signal_strength = max(0, min(100, self.signal_strength + random.randint(-5, 5)))
        self.battery_level = max(0, min(100, self.battery_level - random.uniform(0, 0.2)))
        
        status = {
            "imei": self.imei,
            "status": self.device_status,
            "signal_strength": self.signal_strength,
            "battery_level": int(self.battery_level),
            "timestamp": timestamp
        }
        
        self.client.publish("device/status", json.dumps(status))
        logger.debug(f"Published device status: {status}")
        
    def publish_sms_status(self, message_id, status):
        """Publish the status of an outgoing SMS message"""
        timestamp = int(time.time())
        
        status_message = {
            "message_id": message_id,
            "status": status,
            "timestamp": timestamp,
            "imei": self.imei
        }
        
        self.client.publish("sms/status", json.dumps(status_message))
        logger.info(f"Published SMS status update: message_id={message_id}, status={status}")
        
    def simulate_incoming_sms(self, sender, content):
        """Simulate receiving an SMS message from a phone number"""
        timestamp = int(time.time())
        
        sms_message = {
            "sender": sender,
            "recipient": self.device_number,
            "content": content,
            "timestamp": timestamp,
            "imei": self.imei
        }
        
        self.client.publish("sms/incoming", json.dumps(sms_message))
        logger.info(f"Published incoming SMS from {sender}: {content}")
        
    def run(self):
        """Run the simulator - connect and keep running"""
        self.connect()
        logger.info(f"Air780E simulator running with IMEI: {self.imei}")
        
        try:
            # Main loop - publish device status periodically
            while True:
                time.sleep(60)  # Update device status every minute
                self.publish_device_status()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
            self.disconnect()
            
    def _signal_handler(self, sig, frame):
        """Handle termination signals"""
        logger.info("Received termination signal, shutting down...")
        self.disconnect()
        sys.exit(0)


def main():
    """Run the simulator as a standalone application"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Air780E GSM/LTE module simulator")
    parser.add_argument("--imei", default="123456789012345", help="Custom IMEI for the device")
    parser.add_argument("--mqtt-host", default="localhost", help="MQTT broker host")
    parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT broker port")
    parser.add_argument("--mqtt-user", default="test", help="MQTT broker username")
    parser.add_argument("--mqtt-password", default="test", help="MQTT broker password")
    parser.add_argument("--mqtt-use-tls", help="Use TLS for MQTT connection")
    parser.add_argument(
        "--signal-strength", type=int, default=75, 
        help="Initial signal strength (0-100)"
    )
    parser.add_argument(
        "--battery-level", type=int, default=90, 
        help="Initial battery level (0-100)"
    )
    parser.add_argument(
        "--send-sms", action="store_true",
        help="Enter interactive mode to send SMS messages"
    )
    
    args = parser.parse_args()
    
    # Create and run the simulator
    simulator = Air780ESimulator(
        imei=args.imei,
        mqtt_host=args.mqtt_host,
        mqtt_port=args.mqtt_port,
        mqtt_user=args.mqtt_user,
        mqtt_password=args.mqtt_password,
        mqtt_use_tls=args.mqtt_use_tls,
        signal_strength=args.signal_strength,
        battery_level=args.battery_level,
    )
    
    # Connect to MQTT broker
    simulator.connect()
    
    if args.send_sms:
        # Interactive mode for sending SMS
        try:
            while True:
                print("\n=== Air780E Simulator ===")
                print(f"IMEI: {simulator.imei}")
                print(f"Status: {simulator.device_status}")
                print(f"Signal: {simulator.signal_strength}%")
                print(f"Battery: {int(simulator.battery_level)}%")
                print("========================")
                print("1. Simulate incoming SMS")
                print("2. Update device status")
                print("3. Quit")
                
                choice = input("\nEnter your choice (1-3): ")
                
                if choice == "1":
                    sender = input("Enter sender phone number (with + prefix): ")
                    if not sender.startswith("+"):
                        sender = "+" + sender
                    content = input("Enter SMS content: ")
                    simulator.simulate_incoming_sms(sender, content)
                    
                elif choice == "2":
                    simulator.publish_device_status()
                    print("Device status updated and published")
                    
                elif choice == "3":
                    break
                    
                else:
                    print("Invalid choice, please try again.")
                    
        except KeyboardInterrupt:
            print("\nExiting simulator...")
        finally:
            simulator.disconnect()
    else:
        # Run in continuous mode
        try:
            simulator.run()
        except KeyboardInterrupt:
            simulator.disconnect()


if __name__ == "__main__":
    main() 