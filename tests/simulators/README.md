# Air780E Simulator

A testing utility that simulates an Air780E GSM/LTE module for the SMS to Telegram Bridge service.

## Overview

This simulator allows you to:

1. Simulate an Air780E device connecting to the MQTT broker
2. Send simulated SMS messages to the bridge service
3. Receive and process outgoing SMS messages from the bridge
4. Report device status (signal strength, battery level, etc.)
5. Provide SMS delivery status updates

## Usage

### Running the Simulator

To start the simulator with default settings:

```bash
python air780e_simulator.py
```

This will:
- Generate a random IMEI for the device
- Connect to an MQTT broker at localhost:1883
- Start publishing device status updates
- Listen for outgoing SMS commands

### Interactive Mode

For interactive testing, use the `--send-sms` flag:

```bash
python air780e_simulator.py --send-sms
```

This will provide a menu-driven interface to:
- Send simulated incoming SMS messages
- Update device status
- View device information

### Command Line Options

```
usage: air780e_simulator.py [-h] [--imei IMEI] [--mqtt-host MQTT_HOST]
                            [--mqtt-port MQTT_PORT] [--mqtt-user MQTT_USER]
                            [--mqtt-password MQTT_PASSWORD] [--mqtt-use-tls]
                            [--signal-strength SIGNAL_STRENGTH]
                            [--battery-level BATTERY_LEVEL] [--send-sms]

Air780E GSM/LTE module simulator

optional arguments:
  -h, --help            show this help message and exit
  --imei IMEI           Custom IMEI for the device
  --mqtt-host MQTT_HOST
                        MQTT broker host
  --mqtt-port MQTT_PORT
                        MQTT broker port
  --mqtt-user MQTT_USER
                        MQTT broker username
  --mqtt-password MQTT_PASSWORD
                        MQTT broker password
  --mqtt-use-tls        Use TLS for MQTT connection
  --signal-strength SIGNAL_STRENGTH
                        Initial signal strength (0-100)
  --battery-level BATTERY_LEVEL
                        Initial battery level (0-100)
  --send-sms            Enter interactive mode to send SMS messages
```

### Sending a Test SMS

There's also a standalone utility script for quickly sending test SMS messages:

```bash
python send_sms.py --sender "+1234567890" --message "Hello, world!" --imei "123456789012345"
```

Options:
```
  -s, --sender SENDER   Sender phone number
  -m, --message MESSAGE SMS message content
  -i, --imei IMEI       Device IMEI
  --mqtt-host MQTT_HOST
                        MQTT broker host
  --mqtt-port MQTT_PORT
                        MQTT broker port
  --mqtt-user MQTT_USER
                        MQTT broker username
  --mqtt-password MQTT_PASSWORD
                        MQTT broker password
  --mqtt-use-tls        Use TLS for MQTT connection
```

## MQTT Communication

The simulator communicates with the bridge service using the following MQTT topics:

### Published by simulator:
- `sms/incoming` - Incoming SMS messages to be forwarded to Telegram
- `sms/status` - Delivery status updates for outgoing SMS
- `device/status` - Device health and status updates

### Subscribed by simulator:
- `sms/outgoing/<imei>` - Outgoing SMS messages to be "sent" by the device

## Message Formats

The simulator follows the message formats defined in the API protocol documentation:

### Incoming SMS (`sms/incoming`)
```json
{
  "sender": "+1234567890",
  "recipient": "+10000000000",
  "content": "Message text",
  "timestamp": 1621234567,
  "imei": "123456789012345"
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