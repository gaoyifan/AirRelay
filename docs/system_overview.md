# SMS to Telegram Bridge - System Overview

## Introduction

The SMS to Telegram Bridge is a backend service that enables bidirectional communication between SMS messages and Telegram Group Forums. It serves as a relay system that forwards incoming SMS messages to dedicated Telegram topics and sends replies from Telegram back as SMS messages.

## Architecture

The system consists of the following components:

```
┌────────────┐     ┌─────────────┐     ┌───────────────┐
│            │     │             │     │               │
│  Air780E   │◄───►│  MQTT Broker│◄───►│ Bridge Service│
│  Device    │     │             │     │               │
│            │     │             │     │               │
└────────────┘     └─────────────┘     └─────┬─────────┘
                                             │
                                             │
                                             ▼
                   ┌─────────────┐     ┌───────────────┐
                   │             │     │               │
                   │  Cloudflare │◄───►│    Telegram   │
                   │  Workers KV │     │    API        │
                   │             │     │               │
                   └─────────────┘     └───────────────┘
```

## Key Components

### 1. Air780E Device
- GSM/LTE module responsible for sending and receiving SMS messages
- Connects to the bridge service via MQTT over TCP
- Identified by its unique IMEI number

### 2. MQTT Broker
- Message broker that facilitates communication between the device and the bridge service
- Uses standard MQTT protocol over TCP for reliable communication
- Handles message queuing and delivery guarantees

### 3. Bridge Service
- Core application that processes and routes messages between systems
- Listens for incoming SMS notifications and Telegram message events
- Maintains the mapping between phone numbers, devices, and Telegram topics
- Formats messages appropriately for each platform
- Uses aiomqtt for asynchronous MQTT communication

### 4. Cloudflare Workers KV
- Serverless key-value database used for storing mapping relationships
- Provides fast, low-latency access to critical mapping data
- Stores device-to-group, phone-to-topic, and message tracking information
- Implements client-side caching to reduce API calls

### 5. Telegram API (via Telethon)
- Interface to Telegram's MTProto API
- Manages Group Forum topics and messages
- Organizes conversations by creating topic threads for each SMS sender
- Handles message formatting and command processing

## Data Flow

### SMS to Telegram:
1. Device receives an SMS message
2. Device publishes the message to the MQTT topic `sms/incoming`
3. Bridge service receives the notification via aiomqtt client
4. Bridge service looks up the corresponding Telegram group and topic
5. If no topic exists for the sender, a new forum topic is created
6. Bridge service forwards the message to the appropriate Telegram topic

### Telegram to SMS:
1. User replies to a message in a Telegram Group Forum topic
2. Bridge service detects the reply via Telethon event handlers
3. Bridge service extracts the phone number from the topic mapping
4. Bridge service publishes an outgoing message to `sms/outgoing/<imei>`
5. Device sends the SMS and publishes delivery status to `sms/status`
6. Bridge service updates the message status in Telegram

## System Requirements
- Python 3.12 or higher
- MQTT broker with TCP support
- Telegram Bot API credentials
- Cloudflare Workers KV account
- Air780E module with MQTT capability 