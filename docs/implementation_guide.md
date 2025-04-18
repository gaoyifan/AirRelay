# SMS to Telegram Bridge - Implementation Guide

This guide provides code examples and instructions for implementing the core components of the SMS to Telegram Bridge service.

## Prerequisites

Before starting implementation, ensure you have:

1. Python 3.12+ installed
2. Telegram Bot created with API credentials
3. Cloudflare Workers KV account set up
4. MQTT broker with WebSocket support available
5. Air780E device configured for MQTT communication

## Project Structure

The recommended project structure is:

```
air-relay/
├── config/
│   └── .env
├── src/
│   ├── __init__.py
│   ├── __main__.py
│   ├── bot/
│   │   ├── __init__.py
│   │   └── telegram.py
│   ├── db/
│   │   ├── __init__.py
│   │   └── workers_kv.py
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py
│   └── mqtt/
│       ├── __init__.py
│       └── client.py
├── tests/
│   └── ...
├── docs/
│   └── ...
├── requirements.txt
└── README.md
```

## Component Implementation

### 1. Data Models with Pydantic

```python
# src/models/schemas.py

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator

class Settings(BaseModel):
    """Application settings from environment variables"""
    # Telegram settings
    tg_api_id: int
    tg_api_hash: str
    tg_bot_token: str
    
    # MQTT settings
    mqtt_host: str
    mqtt_port: int
    mqtt_user: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_use_tls: bool = False
    
    # Cloudflare Workers KV settings
    cf_account_id: str
    cf_namespace_id: str
    cf_api_key: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = ""
        case_sensitive = False

class SMSMessage(BaseModel):
    """SMS message received from device"""
    sender: str = Field(..., description="Phone number of the SMS sender")
    recipient: Optional[str] = Field(None, description="Phone number that received the message")
    content: str = Field(..., description="Text content of the SMS message")
    timestamp: int = Field(..., description="Unix timestamp when the message was received")
    imei: str = Field(..., description="The IMEI number of the device that received the SMS")
    
    @validator('sender')
    def validate_phone_number(cls, v):
        # Simple validation for phone number format
        if not v.startswith('+'):
            return f"+{v}"
        return v

class OutgoingSMS(BaseModel):
    """SMS message to be sent to a phone number"""
    recipient: str = Field(..., description="Phone number to send the SMS to")
    content: str = Field(..., description="Text content to send")
    message_id: str = Field(..., description="Unique identifier for tracking message status")

class SMSStatus(BaseModel):
    """Status update for a sent SMS message"""
    message_id: str = Field(..., description="The unique identifier from the outgoing SMS")
    status: str = Field(..., description="Current status of the message (delivered, failed)")
    timestamp: int = Field(..., description="Unix timestamp of the status update")
    imei: str = Field(..., description="The IMEI number of the device reporting the status")

class DeviceStatus(BaseModel):
    """Status information for a device"""
    imei: str = Field(..., description="Device IMEI number")
    status: str = Field(..., description="Device status (online, offline, error)")
    signal_strength: int = Field(..., description="GSM signal strength percentage (0-100)")
    battery_level: int = Field(..., description="Battery level percentage (0-100)")
    timestamp: int = Field(..., description="Unix timestamp of the status update")

class PhoneTopicMapping(BaseModel):
    """Mapping between a phone number and a Telegram topic"""
    group_id: int
    topic_id: int
    topic_title: str
    last_activity: int

class MessageTracking(BaseModel):
    """Information for tracking an outgoing message"""
    group_id: int
    msg_id: int
```

### 2. Database Layer (Cloudflare Workers KV)

```python
# src/db/workers_kv.py

import os
import json
import workers_kv
from typing import Optional, Dict, Any, Union
from src.models.schemas import PhoneTopicMapping, MessageTracking

class Database:
    def __init__(self, account_id: str, namespace_id: str, api_key: str):
        self.namespace = workers_kv.Namespace(
            account_id=account_id,
            namespace_id=namespace_id,
            api_key=api_key
        )
    
    def get_device_group(self, imei: str) -> Optional[int]:
        """Get Telegram group ID for a device IMEI"""
        key = f"device:{imei}"
        value = self.namespace.read(key)
        return int(value) if value else None
    
    def set_device_group(self, imei: str, group_id: Optional[int]) -> None:
        """Map device IMEI to a Telegram group"""
        key = f"device:{imei}"
        if group_id is None:
            self.namespace.delete_one(key)
        else:
            self.namespace.write({key: str(group_id)})
    
    def get_thread_topic(self, group_id: int, phone: str) -> Optional[int]:
        """Get topic ID for a phone number in a group"""
        key = f"thread:{group_id}:{phone}"
        value = self.namespace.read(key)
        return int(value) if value else None
    
    def set_thread_topic(self, group_id: int, phone: str, topic_id: int, topic_title: str = None) -> None:
        """Map a phone number to a topic in a group"""
        key = f"thread:{group_id}:{phone}"
        mapping = PhoneTopicMapping(
            group_id=group_id,
            topic_id=topic_id,
            topic_title=topic_title or f"SMS: {phone}",
            last_activity=int(__import__('time').time())
        )
        self.namespace.write({key: mapping.dict()})
    
    def get_group_device(self, group_id: int) -> Optional[str]:
        """Get device IMEI for a Telegram group (reverse lookup)"""
        key = f"group:{group_id}"
        return self.namespace.read(key)
    
    def set_group_device(self, group_id: int, imei: Optional[str]) -> None:
        """Map a Telegram group to a device IMEI"""
        key = f"group:{group_id}"
        if imei is None:
            self.namespace.delete_one(key)
        else:
            self.namespace.write({key: imei})
    
    def track_message(self, message_id: str, group_id: int, msg_id: int) -> None:
        """Track an outgoing message for status updates"""
        key = f"msg:{message_id}"
        tracking = MessageTracking(
            group_id=group_id,
            msg_id=msg_id
        )
        self.namespace.write({key: tracking.dict()})
    
    def get_tracked_message(self, message_id: str) -> Optional[MessageTracking]:
        """Get tracking info for a message"""
        key = f"msg:{message_id}"
        data = self.namespace.read(key)
        if data:
            return MessageTracking(**data)
        return None
    
    def delete_tracked_message(self, message_id: str) -> None:
        """Delete tracking info for a message"""
        key = f"msg:{message_id}"
        self.namespace.delete_one(key)
```

### 3. MQTT Client

```python
# src/mqtt/client.py

import json
import uuid
import os
import paho.mqtt.client as mqtt
import time
import asyncio
from typing import Callable, Dict, Any
import logging
from src.models.schemas import SMSMessage, SMSStatus, DeviceStatus, OutgoingSMS

logger = logging.getLogger(__name__)

class MQTTClient:
    def __init__(self, telegram_client, host: str, port: int, username: str = None, 
                 password: str = None, use_tls: bool = False):
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
                    sms_message = SMSMessage(**payload)
                    asyncio.create_task(self._handle_incoming_sms(sms_message))
                except Exception as e:
                    logger.error(f"Invalid SMS message format: {e}")
            
            elif msg.topic == "sms/status":
                try:
                    status_message = SMSStatus(**payload)
                    asyncio.create_task(self._handle_status_update(status_message))
                except Exception as e:
                    logger.error(f"Invalid status message format: {e}")
            
            elif msg.topic == "device/status":
                try:
                    device_status = DeviceStatus(**payload)
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
    
    async def _handle_incoming_sms(self, message: SMSMessage):
        """Handle incoming SMS from the device"""
        # Forward to the Telegram client
        await self.telegram_client.forward_sms_to_telegram(
            sender=message.sender,
            content=message.content,
            imei=message.imei,
            timestamp=message.timestamp
        )
    
    async def _handle_status_update(self, status: SMSStatus):
        """Handle SMS status updates from the device"""
        # Forward to the Telegram client
        await self.telegram_client.update_message_status(status.message_id, status.status)
    
    def send_sms(self, imei: str, recipient: str, content: str) -> str:
        """Send an SMS message via the device"""
        message_id = str(uuid.uuid4())
        outgoing_sms = OutgoingSMS(
            recipient=recipient,
            content=content,
            message_id=message_id
        )
        
        topic = f"sms/outgoing/{imei}"
        result = self.client.publish(topic, outgoing_sms.json())
        
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error(f"Failed to publish message: {result}")
            return None
        
        logger.info(f"SMS message queued for {recipient} via {imei}, ID: {message_id}")
        return message_id
```

### 4. Telegram Client

```python
# src/bot/telegram.py

from telethon import TelegramClient, events
from telethon.tl.functions.channels import CreateForumTopicRequest
import os
import asyncio
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class SMSTelegramClient(TelegramClient):
    """Enhanced Telegram client that handles SMS forwarding and commands"""
    
    def __init__(self, session_name, api_id, api_hash):
        """Initialize the Telegram client with required credentials"""
        super().__init__(session_name, api_id, api_hash)
        self.db = None  # Will be set by the main application
        self.mqtt_client = None  # Will be set by the main application
    
    def set_dependencies(self, db, mqtt_client):
        """Set dependencies after initialization"""
        self.db = db
        self.mqtt_client = mqtt_client
        logger.info("Telegram client dependencies set")
    
    def register_handlers(self):
        """Register event handlers for incoming messages and commands"""
        # Register message handler - this handles forum message replies
        @events.register(events.NewMessage(incoming=True))
        async def handle_new_message(event):
            # Skip messages from ourselves
            if event.out:
                return
            
            # Skip command messages (they're handled by specific handlers)
            if event.text.startswith('/'):
                return
            
            # Check if it's a reply in a topic
            topic_id = None
            if event.reply_to and hasattr(event.reply_to, 'forum_topic') and event.reply_to.forum_topic:
                topic_id = event.reply_to.reply_to_top_id or event.reply_to.reply_to_msg_id
            
            if topic_id:
                # It's a reply in a topic, handle it as an SMS reply
                await self._handle_sms_reply(event.chat_id, topic_id, event.id, event.text)
        
        # Register command handlers using decorators
        @events.register(events.NewMessage(pattern="^/start"))
        async def handle_start_command(event):
            await event.respond(
                "SMS to Telegram Bridge Bot\n\n"
                "Use this bot to forward SMS messages to Telegram and reply to them.\n\n"
                "Available commands:\n"
                "/bind <imei> - Bind a device to this group\n"
                "/unbind <imei> - Remove a device binding\n"
                "/status - Show system status\n"
                "/help - Show this help message"
            )
            raise events.StopPropagation
        
        @events.register(events.NewMessage(pattern="^/bind"))
        async def handle_bind_command(event):
            # Extract IMEI from command
            parts = event.text.split(maxsplit=1)
            if len(parts) < 2:
                await event.respond("Please specify the device IMEI. Usage: /bind <imei>")
                return
            
            imei = parts[1].strip()
            group_id = event.chat_id
            
            # Check if this device is already bound
            existing_group = self.db.get_device_group(imei)
            if existing_group:
                await event.respond(
                    f"Device {imei} is already bound to another group. Unbind it first."
                )
                return
            
            # Check if this group already has a device
            existing_device = self.db.get_group_device(group_id)
            if existing_device:
                await event.respond(
                    f"This group is already bound to device {existing_device}. Unbind it first."
                )
                return
            
            # Create the binding
            self.db.set_device_group(imei, group_id)
            self.db.set_group_device(group_id, imei)
            
            await event.respond(f"Device {imei} has been bound to this group successfully.")
        
        @events.register(events.NewMessage(pattern="^/unbind"))
        async def handle_unbind_command(event):
            group_id = event.chat_id
            
            # Check if IMEI was specified
            parts = event.text.split(maxsplit=1)
            if len(parts) < 2:
                # No IMEI specified, unbind whatever device is bound to this group
                imei = self.db.get_group_device(group_id)
                if not imei:
                    await event.respond("No device is bound to this group.")
                    return
            else:
                # IMEI specified, check if it's bound to this group
                imei = parts[1].strip()
                bound_group = self.db.get_device_group(imei)
                if bound_group != group_id:
                    await event.respond(f"Device {imei} is not bound to this group.")
                    return
            
            # Remove the binding
            self.db.set_device_group(imei, None)
            self.db.set_group_device(group_id, None)
            
            await event.respond(f"Device {imei} has been unbound from this group.")
        
        @events.register(events.NewMessage(pattern="^/status"))
        async def handle_status_command(event):
            group_id = event.chat_id
            
            # Get the device for this group
            imei = self.db.get_group_device(group_id)
            if not imei:
                await event.respond("No device is bound to this group.")
                return
            
            # Here you could include more status info like online/offline,
            # last seen time, etc., if that information is available
            await event.respond(f"Device IMEI: {imei}\nStatus: Active")
        
        @events.register(events.NewMessage(pattern="^/help"))
        async def handle_help_command(event):
            await event.respond(
                "Available commands:\n"
                "/bind <imei> - Bind a device to this group\n"
                "/unbind <imei> - Remove a device binding\n"
                "/status - Show system status\n"
                "/help - Show this help message"
            )
            raise events.StopPropagation
        
        # Add all the event handlers
        self.add_event_handler(handle_new_message)
        self.add_event_handler(handle_start_command)
        self.add_event_handler(handle_bind_command)
        self.add_event_handler(handle_unbind_command)
        self.add_event_handler(handle_status_command)
        self.add_event_handler(handle_help_command)
        
        logger.info("Telegram event handlers registered")
    
    async def create_topic(self, chat_id: int, title: str) -> Optional[int]:
        """Create a new forum topic in a group"""
        try:
            result = await self(CreateForumTopicRequest(
                channel=chat_id,
                title=title
            ))
            
            for update in result.updates:
                if hasattr(update, 'id'):
                    return update.id
            
            return None
        except Exception as e:
            logger.error(f"Failed to create topic: {e}")
            return None
    
    async def forward_sms_to_telegram(self, sender: str, content: str, imei: str, timestamp: int = None):
        """Forward an SMS message to the appropriate Telegram group and topic"""
        # Find the Telegram group for this device
        group_id = self.db.get_device_group(imei)
        if not group_id:
            logger.warning(f"No Telegram group found for device {imei}")
            return
        
        # Format the message
        formatted_message = f"From: {sender}\n\n{content}"
        
        # Find or create a topic for this sender
        topic_id = self.db.get_thread_topic(group_id, sender)
        if not topic_id:
            # Create a new topic
            topic_title = f"SMS: {sender}"
            topic_id = await self.create_topic(group_id, topic_title)
            if topic_id:
                self.db.set_thread_topic(group_id, sender, topic_id, topic_title)
            else:
                logger.error(f"Failed to create topic for {sender}")
                return
        
        # Send the message to the topic
        try:
            sent_msg = await self.send_message(
                entity=group_id,
                message=formatted_message,
                reply_to=topic_id
            )
            logger.info(f"SMS from {sender} forwarded to Telegram group {group_id}, topic {topic_id}")
            return sent_msg.id
        except Exception as e:
            logger.error(f"Failed to send message to topic: {e}")
            return None
    
    async def update_message_status(self, message_id: str, status: str):
        """Update the status of a sent message in Telegram"""
        # Get the tracked message info
        tracked_message = self.db.get_tracked_message(message_id)
        if not tracked_message:
            logger.warning(f"No tracked message found with ID {message_id}")
            return
        
        # Update message in Telegram if needed
        group_id = tracked_message.group_id
        msg_id = tracked_message.msg_id
        
        status_text = "✓✓" if status == "delivered" else "❌"
        
        try:
            # Edit the original message to show status
            original_message = await self.get_messages(group_id, ids=msg_id)
            if original_message:
                await self.edit_message(
                    entity=group_id,
                    message=msg_id,
                    text=f"{original_message.text} {status_text}"
                )
                logger.info(f"Message status updated to {status} for message {message_id}")
        except Exception as e:
            logger.error(f"Failed to update message status: {e}")
        
        # If the message was delivered (or failed), remove from tracking
        self.db.delete_tracked_message(message_id)
    
    async def _handle_sms_reply(self, group_id: int, topic_id: int, msg_id: int, text: str):
        """Handle replies to messages in Telegram topics"""
        # Get all phone numbers associated with this topic
        # This is a simplified approach - in a real implementation, you might want
        # to extract the phone number from the topic title or from messages in the topic
        phone_number = None
        
        # Search for the phone number mapped to this topic
        for key in self.db.namespace.list_keys():
            if key.startswith(f"thread:{group_id}:"):
                _, _, phone = key.split(":", 2)
                stored_topic_id = self.db.get_thread_topic(group_id, phone)
                if stored_topic_id == topic_id:
                    phone_number = phone
                    break
        
        if not phone_number:
            await self.send_message(
                entity=group_id,
                reply_to=msg_id,
                message="Error: Could not determine the recipient for this message."
            )
            return
        
        # Get the device IMEI for this group
        imei = self.db.get_group_device(group_id)
        if not imei:
            await self.send_message(
                entity=group_id,
                reply_to=msg_id,
                message="Error: No device is bound to this group."
            )
            return
        
        # Send the SMS via MQTT
        message_id = self.mqtt_client.send_sms(imei, phone_number, text)
        if message_id:
            # Track the message for status updates
            self.db.track_message(message_id, group_id, msg_id)
        else:
            await self.send_message(
                entity=group_id,
                reply_to=msg_id,
                message="Failed to send SMS message."
            )
```

### 5. Main Application

```python
# src/__main__.py

import asyncio
import os
import signal
import sys
import logging
from pydantic import ValidationError
from dotenv import load_dotenv

from src.bot.telegram import SMSTelegramClient
from src.db.workers_kv import Database
from src.mqtt.client import MQTTClient
from src.models.schemas import Settings

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class AirRelay:
    """Main bridge application that connects SMS and Telegram"""
    
    def __init__(self):
        """Initialize the bridge with required components"""
        # Load settings from environment variables
        try:
            self.settings = Settings(
                tg_api_id=os.environ.get("TG_API_ID"),
                tg_api_hash=os.environ.get("TG_API_HASH"),
                tg_bot_token=os.environ.get("TG_BOT_TOKEN"),
                mqtt_host=os.environ.get("MQTT_HOST"),
                mqtt_port=int(os.environ.get("MQTT_PORT", 0)),
                mqtt_user=os.environ.get("MQTT_USER"),
                mqtt_password=os.environ.get("MQTT_PASSWORD"),
                mqtt_use_tls=os.environ.get("MQTT_USE_TLS", "").lower() == "true",
                cf_account_id=os.environ.get("CF_ACCOUNT_ID"),
                cf_namespace_id=os.environ.get("CF_NAMESPACE_ID"),
                cf_api_key=os.environ.get("CF_API_KEY")
            )
        except ValidationError as e:
            logger.error(f"Configuration error: {e}")
            raise ValueError(f"Invalid configuration: {e}")
        
        # Initialize database
        self.db = Database(
            account_id=self.settings.cf_account_id,
            namespace_id=self.settings.cf_namespace_id,
            api_key=self.settings.cf_api_key
        )
        
        # Initialize Telegram client
        self.tg = SMSTelegramClient(
            'air_relay_bot', 
            self.settings.tg_api_id, 
            self.settings.tg_api_hash
        )
        
        # Initialize MQTT client
        self.mqtt = MQTTClient(
            telegram_client=self.tg,
            host=self.settings.mqtt_host,
            port=self.settings.mqtt_port,
            username=self.settings.mqtt_user,
            password=self.settings.mqtt_password,
            use_tls=self.settings.mqtt_use_tls
        )
        
        # Set dependencies
        self.tg.set_dependencies(self.db, self.mqtt)
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info("AirRelay initialized")
    
    async def setup(self):
        """Set up the bridge components"""
        # Start Telegram client
        await self.tg.start(bot_token=self.settings.tg_bot_token)
        
        # Register Telegram event handlers
        self.tg.register_handlers()
        
        # Connect MQTT client
        self.mqtt.connect()
        
        logger.info("AirRelay setup completed")
    
    async def run(self):
        """Run the bridge service"""
        await self.setup()
        logger.info("AirRelay is now running!")
        
        # Keep the application running until disconnected
        await self.tg.run_until_disconnected()
    
    async def stop(self):
        """Stop all components of the bridge"""
        # Disconnect MQTT client
        self.mqtt.disconnect()
        
        # Disconnect Telegram client
        await self.tg.disconnect()
        
        logger.info("AirRelay stopped")
    
    def _signal_handler(self, sig, frame):
        """Handle termination signals"""
        logger.info("Received termination signal, shutting down...")
        asyncio.create_task(self.stop())
        sys.exit(0)


def run_bridge():
    """Run the bridge as a standalone application"""
    # Create bridge instance
    bridge = AirRelay()
    
    # Get or create event loop
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    # Run the bridge using the event loop
    try:
        loop.run_until_complete(bridge.run())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        sys.exit(0)


if __name__ == "__main__":
    run_bridge()
```

## 6. Package Requirements

Create a `requirements.txt` file in the project root:

```
telethon>=1.27.0
paho-mqtt>=2.0.0
workers-kv.py>=1.2.2
python-dotenv>=1.0.0
pydantic>=2.0.0
```

## Configuration

Create a `.env` file in the config directory with your credentials:

```
# Telegram Configuration
TG_API_ID=123456
TG_API_HASH=your_api_hash
TG_BOT_TOKEN=your_bot_token

# MQTT Configuration
MQTT_HOST=broker.example.com
MQTT_PORT=8883
MQTT_USER=username
MQTT_PASSWORD=password
MQTT_USE_TLS=true

# Cloudflare Workers KV Configuration
CF_ACCOUNT_ID=your_account_id
CF_NAMESPACE_ID=your_namespace_id
CF_API_KEY=your_api_key
```

## Running the Application

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Start the bridge service:
   ```bash
   python -m src
   ```

## Deploying to Production

For production deployment, consider:

1. Using a process manager like Supervisor or systemd
2. Setting up logging to a file or external service
3. Implementing retry logic for API calls
4. Adding monitoring and health checks
5. Containerizing the application with Docker

Example systemd service file (`/etc/systemd/system/air-relay.service`):

```
[Unit]
Description=Air Relay SMS to Telegram Bridge Service
After=network.target

[Service]
User=yourusername
WorkingDirectory=/path/to/air-relay
ExecStart=/usr/bin/python3 -m src
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl enable air-relay
sudo systemctl start air-relay
``` 