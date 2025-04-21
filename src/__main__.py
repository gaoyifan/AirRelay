import asyncio
import logging
import os
import signal
import sys

from dotenv import load_dotenv
from pydantic import ValidationError

from src.bot.telegram import SMSTelegramClient
from src.db.workers_kv import Database
from src.models.schemas import Settings
from src.mqtt.client import AsyncMQTTClient

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG
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
                cf_api_key=os.environ.get("CF_API_KEY"),
            )
        except ValidationError as e:
            logger.error(f"Configuration error: {e}")
            raise ValueError(f"Invalid configuration: {e}")

        # Initialize database
        self.db = Database(
            account_id=self.settings.cf_account_id,
            namespace_id=self.settings.cf_namespace_id,
            api_key=self.settings.cf_api_key,
        )

        # Initialize Telegram client
        self.tg = SMSTelegramClient(
            "air_relay_bot", self.settings.tg_api_id, self.settings.tg_api_hash
        )

        # Initialize MQTT client
        self.mqtt = AsyncMQTTClient(
            telegram_client=self.tg,
            host=self.settings.mqtt_host,
            port=self.settings.mqtt_port,
            username=self.settings.mqtt_user,
            password=self.settings.mqtt_password,
            use_tls=self.settings.mqtt_use_tls,
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
        
        # Register bot commands menu
        await self.tg.register_bot_commands()

        # Connect MQTT client
        await self.mqtt.connect()

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
        await self.mqtt.disconnect()

        # Disconnect Telegram client
        await self.tg.disconnect()

        logger.info("AirRelay stopped")

    def _signal_handler(self, sig, frame):
        """Handle termination signals"""
        logger.info("Received termination signal, shutting down...")
        asyncio.create_task(self.stop())
        sys.exit(0)


def main():
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
    main()
