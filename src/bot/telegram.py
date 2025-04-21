import logging
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.functions.channels import CreateForumTopicRequest
from telethon.tl.functions.bots import SetBotCommandsRequest
from telethon.tl.types import BotCommand, BotCommandScopeDefault

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

    async def register_bot_commands(self):
        """Register bot commands to be displayed in the Telegram client."""
        try:
            await self(
                SetBotCommandsRequest(
                    scope=BotCommandScopeDefault(),
                    lang_code="en",
                    commands=[
                        BotCommand(command=cmd, description=desc)
                        for cmd, desc in [
                            ("linkdevice", "Bind a device to this group"),
                            ("unlinkdevice", "Remove a device binding"),
                            ("linkphone", "Bind a phone number to a topic"),
                            ("unlinkphone", "Remove a phone number binding"),
                            ("phoneinfo", "Show phone number bound to current topic"),
                            ("status", "Show system status"),
                            ("help", "Show help message"),
                        ]
                    ],
                )
            )
            logger.info("Bot commands registered successfully")
        except Exception as e:
            logger.error(f"Failed to register bot commands: {e}")

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
            await self._send_response(
                event,
                "SMS to Telegram Bridge Bot\n\n"
                "Use this bot to forward SMS messages to Telegram and reply to them.\n\n"
                "Available commands:\n"
                "/linkdevice <imei> - Bind a device to this group\n"
                "/unlinkdevice <imei> - Remove a device binding\n"
                "/linkphone <phone> - Bind a phone number to a topic\n"
                "/unlinkphone <phone> - Remove a phone number binding\n"
                "/phoneinfo - Show phone number bound to current topic\n"
                "/status - Show system status\n"
                "/help - Show this help message"
            )
            raise events.StopPropagation

        @events.register(events.NewMessage(pattern="^/linkdevice"))
        async def handle_bind_device_command(event):
            # Extract IMEI from command
            parts = event.text.split(maxsplit=1)
            if len(parts) < 2:
                await self._send_response(event, "Please specify the device IMEI. Usage: /linkdevice <imei>")
                return

            imei = parts[1].strip()
            group_id = event.chat_id

            # Check if this device is already bound
            existing_group = self.db.get_group_from_device(imei)
            if existing_group:
                await self._send_response(
                    event, f"Device {imei} is already bound to another group. Unbind it first."
                )
                return

            # Check if this group already has a device
            existing_device = self.db.get_device_from_group(group_id)
            if existing_device:
                await self._send_response(
                    event, f"This group is already bound to device {existing_device}. Unbind it first."
                )
                return

            # Create the binding
            self.db.map_device_group(imei, group_id)

            await self._send_response(event, f"Device {imei} has been bound to this group successfully.")

        @events.register(events.NewMessage(pattern="^/unlinkdevice"))
        async def handle_unbind_device_command(event):
            group_id = event.chat_id

            # Check if IMEI was specified
            parts = event.text.split(maxsplit=1)
            if len(parts) < 2:
                # No IMEI specified, unbind whatever device is bound to this group
                imei = self.db.get_device_from_group(group_id)
                if not imei:
                    await self._send_response(event, "No device is bound to this group.")
                    return
            else:
                # IMEI specified, check if it's bound to this group
                imei = parts[1].strip()
                bound_group = self.db.get_group_from_device(imei)
                if bound_group != group_id:
                    await self._send_response(event, f"Device {imei} is not bound to this group.")
                    return

            # Remove the binding
            self.db.delete_device_group(imei=imei, group_id=group_id)

            await self._send_response(event, f"Device {imei} has been unbound from this group.")

        @events.register(events.NewMessage(pattern="^/linkphone"))
        async def handle_bind_phone_command(event):
            # Extract phone number from command
            parts = event.text.split(maxsplit=1)
            if len(parts) < 2:
                await self._send_response(event, "Please specify the phone number. Usage: /linkphone <phone>")
                return

            phone_number = parts[1].strip()
            group_id = event.chat_id
            
            # Get current topic ID using the helper method
            current_topic_id = self._get_current_topic_id(event)

            # Check if this phone is already bound to a topic in this group
            existing_topic = self.db.get_topic_from_phone(group_id, phone_number)
            if existing_topic:
                await self._send_response(
                    event, f"Phone number {phone_number} is already bound to a topic in this group."
                )
                return

            topic_id = None
            # Create a new topic (only when command is used in General Topic)
            if not current_topic_id:
                topic_title = f"{phone_number}"
                topic_id = await self.create_topic(group_id, topic_title)
                
                if not topic_id:
                    await self._send_response(event, "Failed to create a new topic. Please check if this group supports topics and bot has permissions to manage topics.")
                    return

            # Create the binding
            self.db.map_phone_topic(group_id, phone_number, topic_id)

            await self._send_response(event, f"Phone number {phone_number} has been bound to the topic successfully.")

        @events.register(events.NewMessage(pattern="^/unlinkphone"))
        async def handle_unbind_phone_command(event):
            group_id = event.chat_id
            
            # Get current topic ID using the helper method
            topic_id = self._get_current_topic_id(event)
            if not topic_id:
                await self._send_response(event, "This command must be used within a topic.")
                return

            # Extract phone number from command
            parts = event.text.split(maxsplit=1)
            if len(parts) < 2:
                phone_number = self.db.get_phone_from_topic(group_id, topic_id)
                if not phone_number:
                    await self._send_response(event, "No phone number is bound to this topic.")  
                    return
            else:
                phone_number = parts[1].strip()
            
            current_phone_number = self.db.get_phone_from_topic(group_id, topic_id)
            if current_phone_number != phone_number:
                await self._send_response(event, f"Phone number {phone_number} is not bound to this topic.")
                return

            # Remove the binding
            try:
                self.db.remove_phone_topic(group_id=group_id, phone=phone_number, topic_id=topic_id)
                await self._send_response(event, f"Phone number {phone_number} has been unbound from its topic.")
            except Exception as e:
                logger.error(f"Failed to unbind phone: {e}")
                await self._send_response(event, f"Failed to unbind phone number: {str(e)}")

        @events.register(events.NewMessage(pattern="^/status"))
        async def handle_status_command(event):
            group_id = event.chat_id

            # Get the device for this group
            imei = self.db.get_device_from_group(group_id)
            if not imei:
                await self._send_response(event, "No device is bound to this group.")
                return

            # Here you could include more status info like online/offline,
            # last seen time, etc., if that information is available
            await self._send_response(event, f"Device IMEI: {imei}\nStatus: Active")

        @events.register(events.NewMessage(pattern="^/help"))
        async def handle_help_command(event):
            await self._send_response(
                event,
                "Available commands:\n"
                "/linkdevice <imei> - Bind a device to this group\n"
                "/unlinkdevice <imei> - Remove a device binding\n"
                "/linkphone <phone> - Bind a phone number to a topic\n"
                "/unlinkphone <phone> - Remove a phone number binding\n"
                "/phoneinfo - Show phone number bound to current topic\n"
                "/status - Show system status\n"
                "/help - Show this help message"
            )
            raise events.StopPropagation

        @events.register(events.NewMessage(pattern="^/phoneinfo"))
        async def handle_phone_info_command(event):
            group_id = event.chat_id
            
            # Get current topic ID using the helper method
            topic_id = self._get_current_topic_id(event)
            if not topic_id:
                await self._send_response(event, "This command can only be used within a topic.")
                return
                
            # Get the phone number for this topic
            phone_number = self.db.get_phone_from_topic(group_id, topic_id)
            
            if phone_number:
                await self._send_response(event, f"Phone number bound to this topic: {phone_number}")
            else:
                await self._send_response(event, "No phone number is bound to this topic.")

        # Add all the event handlers
        self.add_event_handler(handle_new_message)
        self.add_event_handler(handle_start_command)
        self.add_event_handler(handle_bind_device_command)
        self.add_event_handler(handle_unbind_device_command)
        self.add_event_handler(handle_bind_phone_command)
        self.add_event_handler(handle_unbind_phone_command)
        self.add_event_handler(handle_status_command)
        self.add_event_handler(handle_help_command)
        self.add_event_handler(handle_phone_info_command)

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

    def _get_current_topic_id(self, event) -> Optional[int]:
        """Helper method to extract the current topic ID from an event"""
        if (
            hasattr(event, "reply_to") 
            and event.reply_to 
            and hasattr(event.reply_to, "forum_topic") 
            and event.reply_to.forum_topic
        ):
            return event.reply_to.reply_to_top_id or event.reply_to.reply_to_msg_id
        return None
        
    async def _send_response(self, event, message: str):
        """Helper method to respond to messages correctly in topics or general chat."""
        
        topic_id = self._get_current_topic_id(event)

        if topic_id:
            await self.send_message(
                entity=event.chat_id,
                reply_to=topic_id,
                message=message
            )
        else:
            # We're in general chat, use respond
            return await event.respond(message)

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
