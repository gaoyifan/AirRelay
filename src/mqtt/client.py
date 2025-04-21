import asyncio
import json
import logging
import uuid
from typing import TYPE_CHECKING

import aiomqtt

from src.models.schemas import DeviceStatus, IncomingSMS, OutgoingSMS, OutgoingSMSStatus

if TYPE_CHECKING:
    from src.bot.telegram import SMSTelegramClient

logger = logging.getLogger(__name__)


class AsyncMQTTClient:
    def __init__(
        self,
        telegram_client,
        host: str,
        port: int,
        username: str = None,
        password: str = None,
        use_tls: bool = False,
    ):
        """Initialize async MQTT client with reference to the Telegram client for callbacks"""
        # Store configuration
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.telegram_client: SMSTelegramClient = telegram_client

        # Connection status
        self.connected = False
        self.client = None
        self.task = None

    async def connect(self):
        """Connect to the MQTT broker asynchronously"""
        try:
            # Create client with the appropriate parameters
            client_kwargs = {
                "hostname": self.host,
                "port": self.port,
                "keepalive": 60,
            }

            # Add authentication if provided
            if self.username and self.password:
                client_kwargs["username"] = self.username
                client_kwargs["password"] = self.password

            # Add TLS if enabled
            if self.use_tls:
                from ssl import create_default_context

                client_kwargs["tls_context"] = create_default_context()

            # Connect and start the message processing task
            self.client = aiomqtt.Client(**client_kwargs)
            self.task = asyncio.create_task(self._process_messages())
            logger.info(f"Async MQTT client connecting to {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            raise

    async def disconnect(self):
        """Disconnect from the MQTT broker asynchronously"""
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

        # Note: We don't need to call disconnect() on the client
        # as it will be closed by the context manager in the task
        self.client = None
        self.connected = False
        logger.info("Async MQTT client disconnected")

    async def _process_messages(self):
        """Process MQTT messages in a background task"""
        async with self.client as client:
            self.connected = True
            logger.info(f"Connected to MQTT broker successfully")

            # Subscribe to topics
            await client.subscribe("sms/incoming")
            logger.info(f"Subscribed to topic: sms/incoming")
            await client.subscribe("sms/status")
            logger.info(f"Subscribed to topic: sms/status")
            await client.subscribe("device/status")
            logger.info(f"Subscribed to topic: device/status")

            # Process incoming messages
            async for message in client.messages:
                try:
                    payload = json.loads(message.payload.decode())
                    logger.debug(f"Received message on topic {message.topic}: {payload}")

                    # Log exact topic for debugging
                    logger.info(
                        f"Message topic: '{message.topic}', topic type: {type(message.topic)}"
                    )

                    # Depending on the topic, dispatch to different handlers
                    if message.topic.value == "sms/incoming":
                        logger.info(f"Received incoming SMS: {payload}")
                        try:
                            sms_message = IncomingSMS(**payload)
                            asyncio.create_task(self._handle_incoming_sms(sms_message))
                        except Exception as e:
                            logger.error(f"Invalid SMS message format: {e}")

                    elif message.topic.value == "sms/status":
                        logger.info(f"Received SMS status update: {payload}")
                        try:
                            status_message = OutgoingSMSStatus(**payload)
                            asyncio.create_task(self._handle_status_update(status_message))
                        except Exception as e:
                            logger.error(f"Invalid status message format: {e}")

                    elif message.topic.value == "device/status":
                        logger.info(f"Received device status update: {payload}")
                        try:
                            DeviceStatus(**payload)
                            # Could handle device status updates here
                        except Exception as e:
                            logger.error(f"Invalid device status format: {e}")
                    else:
                        logger.info(
                            f"Received message on unhandled topic '{message.topic}': {payload}"
                        )

                except json.JSONDecodeError:
                    logger.error(f"Failed to decode JSON message: {message.payload}")
                except Exception as e:
                    logger.error(f"Error handling message: {e}")

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

    async def send_sms(self, imei: str, recipient: str, content: str) -> str:
        """Send an SMS message via the device asynchronously"""
        if not self.client or not self.connected:
            logger.error("Cannot send SMS: MQTT client not connected")
            return None

        message_id = str(uuid.uuid4())
        outgoing_sms = OutgoingSMS(recipient=recipient, content=content, message_id=message_id)

        # Create the outgoing topic
        topic = f"sms/outgoing/{imei}"
        payload = outgoing_sms.model_dump_json()

        try:
            # Publish to the topic
            logger.info(f"Publishing SMS to topic: {topic}")
            await self.client.publish(topic, payload)
            logger.info(f"SMS message queued for {recipient} via {imei}, ID: {message_id}")
            return message_id
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return None
