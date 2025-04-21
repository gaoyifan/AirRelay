# AirRelay - SMS to Telegram Bridge

AirRelay is a service that forwards SMS messages between a Luat Air780E device and Telegram Group Forums.

## Features

- Bidirectional message forwarding between SMS and Telegram
- Topic-based organization of SMS conversations in Telegram
- Support for device status monitoring
- Easy device setup with MQTT over WebSocket
- Secure storage using Cloudflare Workers KV

## Prerequisites

- Python 3.12+
- Telegram Bot created with API credentials (via @BotFather)
- Cloudflare Workers KV account
- MQTT broker with WebSocket support
- Air780E device configured for MQTT communication

## Installation

### Using Rye (Recommended)

This project uses [Rye](https://rye-up.com) for Python project management.

1. Install Rye following the [official instructions](https://rye-up.com/guide/installation/)

2. Clone the repository:

```bash
git clone https://github.com/yourusername/air-relay.git
cd air-relay
```

3. Set up the project with Rye:

```bash
rye sync
```

4. Copy the example environment file and edit it with your credentials:

```bash
cp .env.example .env
# Edit .env with your credentials
```

5. Run the application:

```bash
rye run python -m src
```

### Using pip (Alternative)

1. Clone the repository:

```bash
git clone https://github.com/yourusername/air-relay.git
cd air-relay
```

2. Install the required dependencies:

```bash
pip install -r requirements.txt
```

3. Copy the example environment file and edit it with your credentials:

```bash
cp .env.example .env
# Edit .env with your credentials
```

4. Run the application:

```bash
python -m src
```

## Configuration

Edit the `.env` file with the following information:

- **Telegram Configuration**
  - `TG_API_ID`: Your Telegram API ID
  - `TG_API_HASH`: Your Telegram API Hash
  - `TG_BOT_TOKEN`: Your Bot Token from BotFather

- **MQTT Configuration**
  - `MQTT_HOST`: MQTT broker hostname
  - `MQTT_PORT`: MQTT broker port (default: 8883)
  - `MQTT_USER`: MQTT username (optional)
  - `MQTT_PASSWORD`: MQTT password (optional)
  - `MQTT_USE_TLS`: Use TLS for MQTT connection (default: true)

- **Cloudflare Workers KV Configuration**
  - `CF_ACCOUNT_ID`: Your Cloudflare account ID
  - `CF_NAMESPACE_ID`: Your KV namespace ID
  - `CF_API_KEY`: Your Cloudflare API key

## Usage

1. Add your bot to a Telegram group with forum topics enabled
2. Run the `/bind <imei>` command in the group to bind your Air780E device
3. Send SMS messages to your device's phone number
4. Receive them in the Telegram group organized by sender
5. Reply to messages in Telegram to send SMS responses

## Bot Commands

- `/start` - Initialize the bot and show help
- `/bind <imei>` - Bind a device to the current group
- `/unbind [imei]` - Remove a device binding
- `/status` - Show system status
- `/help` - Show command list

## Device Setup

See the [Device Integration Guide](docs/device_integration.md) for instructions on setting up your Air780E device.

## Documentation

Full documentation is available in the `docs/` directory:

- [System Overview](docs/system_overview.md)
- [API & Protocol Documentation](docs/api_protocol.md)
- [Implementation Guide](docs/implementation_guide.md)
- [Device Integration](docs/device_integration.md)
- [Telethon Group Topic Guide](docs/telethon_group_topic.md)

## Development

This project uses [Just](https://just.systems/) as a command runner. To see all available commands:

```bash
just
```

Common development commands:

```bash
# Format code using autoflake, isort, and black
just fmt

# Run tests
just test

# Type check with mypy
just typecheck

# Run a complete check (formatting, type checking, tests)
just check

# Clean up Python cache files
just clean
```

You can also use Rye for dependency management:

```bash
# Update dependencies
just update-deps
```

## License

This project is licensed under the MIT License. 

### MQTT Integration

The system uses MQTT for communication with the Air780E devices. We've implemented two MQTT client options:

#### 1. Synchronous MQTT Client (Legacy)

Uses `paho-mqtt` directly with callbacks for handling messages. This is maintained for backward compatibility.

#### 2. Asynchronous MQTT Client (Recommended)

Uses `aiomqtt` for fully asynchronous operation with these advantages:
- No callbacks, using modern Python async/await syntax
- Simplified error handling
- Graceful connection and disconnection
- Better integration with asyncio applications
- Cleaner code and reduced complexity

### Usage Examples

```python
# Async MQTT Client
async with AsyncMQTTClient(...) as client:
    await client.subscribe("topic")
    await client.publish("topic", payload)
    async for message in client.messages:
        print(message.payload)
```

### Requirements

- Python 3.12+
- paho-mqtt
- aiomqtt
- telethon
- workers-kv.py
- pydantic
- dotenv

### Setup and Installation

1. Clone this repository
2. Install dependencies: `rye sync`
3. Set up environment variables (see `.env.example`)
4. Run the application: `python -m src`

### Testing

Test scripts are available in the `tests` directory:
- `test_async_mqtt.py`: Tests the async MQTT client
- `test_incoming_sms.py`: Simulates an incoming SMS message 