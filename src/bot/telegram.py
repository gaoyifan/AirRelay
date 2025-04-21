import logging
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.functions.channels import CreateForumTopicRequest

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.db.workers_kv import Database
    from src.mqtt.client import AsyncMQTTClient

logger = logging.getLogger(__name__)


class SMSTelegramClient(TelegramClient):
    """Enhanced Telegram client that handles SMS forwarding and commands"""

    def __init__(self, session_name, api_id, api_hash):
        """Initialize the Telegram client with required credentials"""
        super().__init__(session_name, api_id, api_hash)
        self.db : Database = None  # Will be set by the main application
        self.mqtt_client : AsyncMQTTClient = None  # Will be set by the main application

    def set_dependencies(self, db, mqtt_client):
        """Set dependencies after initialization"""
        self.db = db
        self.mqtt_client = mqtt_client
        logger.info("Telegram client dependencies set")

    def register_handlers(self):
        """Register event handlers for incoming messages and commands"""
        
        # Register message handler - this handles forum message replies
        @events.register(events.NewMessage(incoming=True, pattern=r"^[^/]+$"))
        async def handle_new_message(event):
            # Check if it's a reply in a topic
            topic_id = None
            if (
                event.reply_to
                and hasattr(event.reply_to, "forum_topic")
                and event.reply_to.forum_topic
            ):
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
            existing_group = self.db.get_group_from_device(imei)
            if existing_group:
                await event.respond(
                    f"Device {imei} is already bound to another group. Unbind it first."
                )
                return

            # Check if this group already has a device
            existing_device = self.db.get_device_from_group(group_id)
            if existing_device:
                await event.respond(
                    f"This group is already bound to device {existing_device}. Unbind it first."
                )
                return

            # Create the binding
            self.db.map_device_group(imei, group_id)

            await event.respond(f"Device {imei} has been bound to this group successfully.")

        @events.register(events.NewMessage(pattern="^/unbind"))
        async def handle_unbind_command(event):
            group_id = event.chat_id

            # Check if IMEI was specified
            parts = event.text.split(maxsplit=1)
            if len(parts) < 2:
                # No IMEI specified, unbind whatever device is bound to this group
                imei = self.db.get_device_from_group(group_id)
                if not imei:
                    await event.respond("No device is bound to this group.")
                    return
            else:
                # IMEI specified, check if it's bound to this group
                imei = parts[1].strip()
                bound_group = self.db.get_group_from_device(imei)
                if bound_group != group_id:
                    await event.respond(f"Device {imei} is not bound to this group.")
                    return

            # Remove the binding
            self.db.delete_device_group(imei=imei, group_id=group_id)

            await event.respond(f"Device {imei} has been unbound from this group.")

        @events.register(events.NewMessage(pattern="^/status"))
        async def handle_status_command(event):
            group_id = event.chat_id

            # Get the device for this group
            imei = self.db.get_device_from_group(group_id)
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
            result = await self(CreateForumTopicRequest(channel=chat_id, title=title))

            for update in result.updates:
                if hasattr(update, "id"):
                    return update.id

            return None
        except Exception as e:
            logger.error(f"Failed to create topic: {e}")
            return None

    async def forward_sms_to_telegram(
        self, sender: str, content: str, imei: str, timestamp: int = None
    ):
        """Forward an SMS message to the appropriate Telegram group and topic"""
        # Find the Telegram group for this device
        group_id = self.db.get_group_from_device(imei)
        if not group_id:
            logger.warning(f"No Telegram group found for device {imei}")
            return

        # Format the message
        formatted_message = f"From: {sender}\n\n{content}"

        # Find or create a topic for this sender
        topic_id = self.db.get_topic_from_phone(group_id, sender)
        if not topic_id:
            # Create a new topic
            topic_title = f"SMS: {sender}"
            topic_id = await self.create_topic(group_id, topic_title)
            if topic_id:
                # This will also create the reverse mapping
                self.db.map_phone_topic(group_id, sender, topic_id)
            else:
                logger.error(f"Failed to create topic for {sender}")
                return

        # Send the message to the topic
        try:
            sent_msg = await self.send_message(
                entity=group_id, message=formatted_message, reply_to=topic_id
            )
            logger.info(
                f"SMS from {sender} forwarded to Telegram group {group_id}, topic {topic_id}"
            )
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

        try:
            # Edit the original message to show status
            original_message = await self.get_messages(group_id, ids=msg_id)
            if original_message:
                await self.send_message(
                    entity=group_id, 
                    reply_to=msg_id, 
                    message=status
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

        # Get the phone number directly using the reverse mapping
        phone_number = self.db.get_phone_from_topic(group_id, topic_id)

        if not phone_number:
            await self.send_message(
                entity=group_id,
                reply_to=msg_id,
                message="Error: Could not determine the recipient for this message.",
            )
            return

        # Get the device IMEI for this group
        imei = self.db.get_device_from_group(group_id)
        if not imei:
            await self.send_message(
                entity=group_id, reply_to=msg_id, message="Error: No device is bound to this group."
            )
            return

        # Send the SMS via MQTT - now using the async method
        message_id = await self.mqtt_client.send_sms(imei, phone_number, text)
        if message_id:
            # Track the message for status updates
            self.db.track_message(message_id, group_id, msg_id)
        else:
            await self.send_message(
                entity=group_id, reply_to=msg_id, message="Failed to send SMS message."
            )
