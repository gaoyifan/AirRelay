import asyncio
import json
import logging
import time
import uuid

import paho.mqtt.client as mqtt

from src.models.schemas import DeviceStatus, IncomingSMS, OutgoingSMS, OutgoingSMSStatus

logger = logging.getLogger(__name__)


class MQTTClient:
    def __init__(
        self,
        telegram_client,
        host: str,
        port: int,
        username: str = None,
        password: str = None,
        use_tls: bool = False,
    ):
        """Initialize MQTT client with reference to the Telegram client for callbacks"""
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, transport="websockets")
        self.telegram_client = telegram_client

        # Store configuration
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls

        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect

        # Set up credentials if provided
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)

        # Set up TLS if enabled
        if self.use_tls:
            self.client.tls_set()

    def connect(self):
        """Connect to the MQTT broker"""
        try:
            self.client.connect(self.host, self.port)
            self.client.loop_start()
            logger.info(f"MQTT client connecting to {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    def disconnect(self):
        """Disconnect from the MQTT broker"""
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("MQTT client disconnected")

    def _on_connect(self, client, userdata, flags, rc, properties=None):
        """Callback for when client connects to the broker"""
        logger.info(f"Connected to MQTT broker with result code {rc}")
        # Subscribe to topics
        client.subscribe("sms/incoming")
        client.subscribe("sms/status")
        client.subscribe("device/status")

    def _on_message(self, client, userdata, msg):
        """Callback for when a message is received from the broker"""
        try:
            payload = json.loads(msg.payload.decode())
            logger.debug(f"Received message on topic {msg.topic}: {payload}")

            # Depending on the topic, dispatch to different handlers
            if msg.topic == "sms/incoming":
                try:
                    sms_message = IncomingSMS(**payload)
                    asyncio.create_task(self._handle_incoming_sms(sms_message))
                except Exception as e:
                    logger.error(f"Invalid SMS message format: {e}")

            elif msg.topic == "sms/status":
                try:
                    status_message = OutgoingSMSStatus(**payload)
                    asyncio.create_task(self._handle_status_update(status_message))
                except Exception as e:
                    logger.error(f"Invalid status message format: {e}")

            elif msg.topic == "device/status":
                try:
                    DeviceStatus(**payload)
                    # Could handle device status updates here
                except Exception as e:
                    logger.error(f"Invalid device status format: {e}")

        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON message: {msg.payload}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    def _on_disconnect(self, client, userdata, rc, properties=None):
        """Callback for when client disconnects from the broker"""
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker: {rc}")
            # Attempt to reconnect
            time.sleep(5)
            self.connect()

    async def _handle_incoming_sms(self, message: IncomingSMS):
        """Handle incoming SMS from the device"""
        # Forward to the Telegram client
        await self.telegram_client.forward_sms_to_telegram(
            sender=message.sender,
            content=message.content,
            imei=message.imei,
            timestamp=message.timestamp,
        )

    async def _handle_status_update(self, status: OutgoingSMSStatus):
        """Handle SMS status updates from the device"""
        # Forward to the Telegram client
        await self.telegram_client.update_message_status(status.message_id, status.status)

    def send_sms(self, imei: str, recipient: str, content: str) -> str:
        """Send an SMS message via the device"""
        message_id = str(uuid.uuid4())
        outgoing_sms = OutgoingSMS(recipient=recipient, content=content, message_id=message_id)

        topic = f"sms/outgoing/{imei}"
        result = self.client.publish(topic, outgoing_sms.json())

        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error(f"Failed to publish message: {result}")
            return None

        logger.info(f"SMS message queued for {recipient} via {imei}, ID: {message_id}")
        return message_id
