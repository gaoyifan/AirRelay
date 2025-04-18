# SMS to Telegram Bridge - API & Protocol Documentation

## MQTT Interface

The system uses MQTT over WebSocket for communication with the Air780E device. The following topics and message formats are defined:

### Topics

| Topic | Direction | Description |
|-------|-----------|-------------|
| `sms/incoming` | Device → Service | Device publishes received SMS messages |
| `sms/outgoing/<imei>` | Service → Device | Service publishes SMS messages to be sent by a specific device |
| `sms/status` | Device → Service | Device publishes delivery status updates |
| `device/status` | Device → Service | Device publishes its status information |

### Message Formats

#### 1. Incoming SMS (`sms/incoming`)

```json
{
  "sender": "+1234567890",
  "recipient": "+0987654321",
  "content": "Message text",
  "timestamp": 1621234567,
  "imei": "123456789012345"
}
```

Fields:
- `sender`: Phone number of the SMS sender (E.164 format)
- `recipient`: Phone number that received the message (E.164 format)
- `content`: Text content of the SMS message
- `timestamp`: Unix timestamp when the message was received
- `imei`: The IMEI number of the device that received the SMS

#### 2. Outgoing SMS (`sms/outgoing/<imei>`)

```json
{
  "recipient": "+1234567890",
  "content": "Reply message",
  "message_id": "unique_id"
}
```

Fields:
- `recipient`: Phone number to send the SMS to (E.164 format)
- `content`: Text content to send
- `message_id`: Unique identifier for tracking message status

#### 3. SMS Status (`sms/status`)

```json
{
  "message_id": "unique_id",
  "status": "delivered",
  "timestamp": 1621234567,
  "imei": "123456789012345"
}
```

Fields:
- `message_id`: The unique identifier from the outgoing SMS
- `status`: Current status of the message (delivered, failed)
- `timestamp`: Unix timestamp of the status update
- `imei`: The IMEI number of the device reporting the status

#### 4. Device Status (`device/status`)

```json
{
  "imei": "123456789012345",
  "status": "online",
  "signal_strength": 75,
  "battery_level": 85,
  "timestamp": 1621234567
}
```

Fields:
- `imei`: Device IMEI number
- `status`: Device status (online, offline, error)
- `signal_strength`: GSM signal strength percentage (0-100)
- `battery_level`: Battery level percentage (0-100)
- `timestamp`: Unix timestamp of the status update

## Telegram Bot Interface

The system interacts with Telegram via the Telethon library, which uses the MTProto API. The bot provides the following commands:

### Commands

| Command | Parameters | Description |
|---------|------------|-------------|
| `/start` | None | Initializes the bot and displays help information |
| `/bind` | `<imei>` | Binds a device to the current Telegram group |
| `/unbind` | `<imei>` | Removes a device binding from the group |
| `/status` | None | Shows the status of all devices bound to the group |
| `/help` | None | Displays available commands and usage information |

### Message Handling

1. **Incoming SMS to Telegram**:
   - Messages are forwarded to the appropriate group and topic
   - Format: `From: +1234567890\n\nMessage content here`
   - If no topic exists for the sender, a new topic is created with title "SMS: +1234567890"

2. **Telegram Replies to SMS**:
   - Any reply within a topic is sent back to the original SMS sender
   - System automatically extracts the target phone number from the topic
   - Text, photos, and audio can be converted to SMS format

## Cloudflare Workers KV API

The system uses Cloudflare Workers KV for persistent storage of mapping relationships. The following data structures are used:

### Key-Value Structure

1. **Device to Telegram Group**
   - Key: `device:<imei>`
   - Value: `tg_group_id`

2. **Conversation Thread Mapping**
   - Key: `thread:<tg_group_id>:<phone_number>`
   - Value: `topic_id`

3. **Reverse Device Lookup**
   - Key: `group:<tg_group_id>`
   - Value: `imei`

4. **Message Tracking**
   - Key: `msg:<message_id>`
   - Value: `{"group_id": tg_group_id, "msg_id": tg_msg_id}`

## API Implementation

### Python Library Requirements

```
telethon>=1.27.0
paho-mqtt>=2.0.0
workers-kv.py>=1.2.2
```

### Environment Variables

The following environment variables are required for configuration:

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