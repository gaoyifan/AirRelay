# Air780E SMS to Telegram Bridge - Device Code

This is the Air780E device code for the SMS to Telegram Bridge system. It handles SMS reception, transmission, and communication with the Bridge Service via MQTT.

## Features

- Receives SMS and forwards them to the MQTT broker
- Listens for outgoing SMS commands from the MQTT broker
- Reports device status periodically (signal strength, battery level)
- Reports SMS delivery status
- Automatic reconnection to the MQTT broker on connection loss
- Watchdog timer to prevent system freezes
- Message queuing system for storing and retrying messages when MQTT connection is lost

## Requirements

- Air780E module with LuatOS firmware
- SIM card with SMS capability
- MQTT broker to connect to (EMQX is used in the provided configuration)

## Configuration

Create a `config.lua` file based on the provided example file `config.lua.example` with your configuration parameters:

```lua
-- MQTT Connection Parameters
return {
    host = "your.mqtt.server.com",
    port = 8883,
    isssl = true,
    user = "your_username",
    pass = "your_password"
}
```

You can also adjust other settings in the `main.lua` file, such as:

```lua
-- Message queue configuration
local MAX_QUEUE_SIZE = 50 -- Maximum number of messages to store in queue
```

## MQTT Topics

The device uses the following MQTT topics:

- `sms/incoming`: The device publishes received SMS messages here
- `sms/outgoing/<imei>`: The device subscribes to this topic for SMS to send
- `sms/status`: The device publishes SMS delivery status updates here
- `device/status`: The device publishes its status information here

## Message Formats

### Incoming SMS (`sms/incoming`)

```json
{
  "sender": "+1234567890",
  "recipient": "+0987654321",
  "content": "Message text",
  "timestamp": 1621234567,
  "imei": "123456789012345"
}
```

### Outgoing SMS (`sms/outgoing/<imei>`)

```json
{
  "recipient": "+1234567890",
  "content": "Reply message",
  "message_id": "unique_id"
}
```

### SMS Status (`sms/status`)

```json
{
  "message_id": "unique_id",
  "status": "delivered",
  "timestamp": 1621234567,
  "imei": "123456789012345"
}
```

### Device Status (`device/status`)

```json
{
  "imei": "123456789012345",
  "status": "online",
  "signal_strength": 75,
  "battery_level": 85,
  "timestamp": 1621234567
}
```

## Message Queuing

The device implements a message queuing system that:

- Stores messages that can't be sent when the MQTT connection is down
- Processes and sends all queued messages upon reconnection
- Maintains a maximum queue size to prevent memory issues
- Prioritizes SMS messages over device status updates

## Installation

1. Upload the `main.lua` file to your Air780E module using LuaTools or another compatible tool
2. Make sure the SIM card is properly inserted and working
3. Power on the device and it will automatically connect to the network and MQTT broker

## Troubleshooting

- Check the log messages for errors or connection issues
- Verify the SIM card is properly inserted and has SMS capability
- Ensure the MQTT broker is accessible from the device's network
- Make sure the MQTT broker accepts connections from the device (check credentials and firewall settings)

## Additional Notes

- The device uses its IMEI number as the client ID for MQTT and as part of the outgoing SMS topic
- SMS delivery status reporting is based on successful sending, not actual delivery confirmation
- Battery level reporting is placeholder code and should be adjusted based on hardware capabilities
- Default DNS servers (119.29.29.29 and 223.5.5.5) are configured for China networks - adjust as needed for your region 