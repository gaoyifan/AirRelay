# SMS to Telegram Bridge - Device Integration Guide

This guide provides instructions for configuring the Luat Air780E module to work with the SMS to Telegram Bridge service.

## Air780E Overview

The Luat Air780E is a compact GSM/LTE module with the following features:
- 4G LTE Cat.1 connectivity
- SMS sending and receiving
- GSM/GPRS fallback
- MQTT client support
- LuaScript programming environment

## Hardware Requirements

1. Air780E module or development board
2. SIM card with SMS capability
3. Power supply (3.3V-4.2V)
4. Antenna
5. USB-to-Serial adapter for programming (if not using a development board)

## Software Requirements

1. LuaTools IDE for programming the module
2. Latest Air780E firmware supporting MQTT over WebSocket
3. SIM card with active service and sufficient credit for SMS

## Module Configuration

### Basic Setup

1. Insert the SIM card into the Air780E module
2. Connect the module to your computer using a USB cable
3. Open LuaTools IDE
4. Connect to the module's serial port
5. Verify the module is responding to AT commands:
   ```
   AT
   ```
   Expected response: `OK`

6. Check if the SIM card is recognized:
   ```
   AT+CPIN?
   ```
   Expected response: `+CPIN: READY` (if the SIM is ready)

7. Check network registration:
   ```
   AT+CREG?
   ```
   Expected response: `+CREG: 0,1` or `+CREG: 0,5` (if registered to the network)

8. Test SMS functionality:
   ```
   AT+CMGF=1
   ```
   Expected response: `OK` (set to text mode)

### Lua Script Implementation

Create a new Lua script in LuaTools IDE with the following functionality:

```lua
-- config.lua
-- Configuration parameters
local CONFIG = {
    MQTT_HOST = "your-broker-host.com",
    MQTT_PORT = 8083,  -- WebSocket port
    MQTT_CLIENT_ID = "",  -- Will be set to IMEI
    MQTT_USER = "username",  -- If authentication is required
    MQTT_PASSWORD = "password",  -- If authentication is required
    MQTT_USE_TLS = false,
    MQTT_KEEPALIVE = 300,
    DEBUG = true  -- Set to true for debug output
}

return CONFIG
```

```lua
-- main.lua
-- Main script for Air780E SMS to MQTT bridge

-- Import modules
local sys = require("sys")
local mqtt = require("mqtt")
local json = require("cjson")
local net = require("net")

-- Load configuration
local CONFIG = require("config")

-- Global variables
local mqttc = nil
local imei = ""
local ready = false

-- Get device IMEI
local function getIMEI()
    imei = mobile.imei()
    CONFIG.MQTT_CLIENT_ID = imei
    log.info("IMEI", imei)
end

-- Initialize SMS functionality
local function initSMS()
    -- Set SMS to text mode
    at.request("AT+CMGF=1")
    -- Configure SMS storage
    at.request("AT+CPMS=\"SM\",\"SM\",\"SM\"")
    -- Enable new SMS notifications
    at.request("AT+CNMI=2,1,0,0,0")
    
    log.info("SMS", "SMS system initialized")
end

-- Initialize MQTT client
local function initMQTT()
    -- Create MQTT client instance
    mqttc = mqtt.client(
        CONFIG.MQTT_CLIENT_ID, 
        CONFIG.MQTT_KEEPALIVE, 
        CONFIG.MQTT_USER, 
        CONFIG.MQTT_PASSWORD, 
        CONFIG.MQTT_CLEAN_SESSION
    )
    
    -- MQTT event callbacks
    mqttc:on(function(...)
        local event, msg, data = ...
        log.info("MQTT EVENT", event, msg, json.encode(data or {}))
        
        if event == "connect" then
            log.info("MQTT", "Connected to broker")
            -- Subscribe to outgoing SMS topic
            mqttc:subscribe("sms/outgoing/"..imei)
            
            -- Publish device status
            publishDeviceStatus("online")
            
            ready = true
        elseif event == "disconnect" then
            log.info("MQTT", "Disconnected")
            ready = false
        elseif event == "message" then
            handleMQTTMessage(msg, data)
        end
    end)
    
    -- Connect to the MQTT broker
    local wsURL = "ws"
    if CONFIG.MQTT_USE_TLS then wsURL = "wss" end
    wsURL = wsURL.."://"..CONFIG.MQTT_HOST..":"..CONFIG.MQTT_PORT.."/mqtt"
    
    log.info("MQTT", "Connecting to", wsURL)
    mqttc:connect(wsURL)
end

-- Handle incoming MQTT messages
function handleMQTTMessage(topic, data)
    if topic == "sms/outgoing/"..imei then
        log.info("SMS", "Outgoing SMS request received")
        local payload = json.decode(data)
        
        if payload and payload.recipient and payload.content and payload.message_id then
            sendSMS(payload.recipient, payload.content, payload.message_id)
        else
            log.error("SMS", "Invalid outgoing SMS format")
        end
    end
end

-- Send SMS message
function sendSMS(recipient, content, messageId)
    log.info("SMS", "Sending to", recipient, content)
    
    -- Remove '+' from the beginning of the number if present
    local number = recipient
    if string.sub(number, 1, 1) == "+" then
        number = string.sub(number, 2)
    end
    
    -- Send SMS AT command
    at.request("AT+CMGS=\""..number.."\"", content..string.char(26), function(_, success)
        local status = success and "delivered" or "failed"
        publishSMSStatus(messageId, status)
    end, 20000)
end

-- Handle incoming SMS
function onNewSMS(num, content)
    log.info("SMS", "Received", num, content)
    
    if ready and mqttc then
        -- Format the SMS data
        local smsData = {
            sender = num,
            recipient = "", -- The SIM card number (could be retrieved from carrier)
            content = content,
            timestamp = os.time(),
            imei = imei
        }
        
        -- Publish to MQTT
        mqttc:publish("sms/incoming", json.encode(smsData))
    else
        log.warn("SMS", "MQTT not ready, SMS queued")
        -- Could implement a queue system here
    end
end

-- Publish SMS delivery status
function publishSMSStatus(messageId, status)
    if ready and mqttc then
        local statusData = {
            message_id = messageId,
            status = status,
            timestamp = os.time(),
            imei = imei
        }
        
        mqttc:publish("sms/status", json.encode(statusData))
    end
end

-- Publish device status
function publishDeviceStatus(status)
    if ready and mqttc then
        -- Get signal quality
        local csq = mobile.csq()
        local signalStrength = csq > 0 and math.floor((csq / 31) * 100) or 0
        
        -- Get battery level (if available on your device)
        local batteryLevel = 100  -- Placeholder, implement actual battery reading if available
        
        local statusData = {
            imei = imei,
            status = status,
            signal_strength = signalStrength,
            battery_level = batteryLevel,
            timestamp = os.time()
        }
        
        mqttc:publish("device/status", json.encode(statusData))
    end
end

-- Register SMS callback
rtos.on(rtos.MSG_SMS, function(num, content)
    onNewSMS(num, content)
end)

-- Initialization function
local function init()
    getIMEI()
    initSMS()
    
    -- Wait for network registration
    sys.waitUntil("IP_READY")
    
    initMQTT()
    
    -- Schedule periodic status updates
    sys.timerLoopStart(publishDeviceStatus, 60000, "online")
end

-- Start the system
sys.taskInit(init)

-- Run the system event loop
sys.run()
```

### Uploading and Testing

1. Upload both `config.lua` and `main.lua` to the Air780E module using LuaTools IDE
2. Set the script to auto-run on boot
3. Restart the module to apply changes
4. Monitor the debug output for successful initialization and connection to the MQTT broker
5. Test by sending an SMS to the module's phone number
6. Verify that the message appears in the Telegram group's topic

## Troubleshooting

### Common Issues

1. **Module not connecting to network**
   - Check antenna connection
   - Verify SIM card is active and properly inserted
   - Check network coverage in your area

2. **MQTT connection failures**
   - Verify broker address and port are correct
   - Check if authentication credentials are required and correctly configured
   - Ensure WebSocket support is enabled on the MQTT broker

3. **SMS not being received or sent**
   - Check if the SIM card has SMS functionality enabled
   - Verify sufficient credit on the SIM card
   - Check network signal strength
   - Ensure correct phone number format (try with and without country code)

4. **Messages not appearing in Telegram**
   - Verify MQTT messages are being published (check broker logs)
   - Check if the device IMEI is correctly bound to a Telegram group

### Debug Commands

Use the following AT commands for debugging:

1. Check signal strength:
   ```
   AT+CSQ
   ```

2. Check network registration status:
   ```
   AT+CREG?
   ```

3. Check SIM card status:
   ```
   AT+CPIN?
   ```

4. List SMS messages in storage:
   ```
   AT+CMGL="ALL"
   ```

5. Delete all SMS messages:
   ```
   AT+CMGD=1,4
   ```

## Advanced Configuration

### Power Optimization

For battery-powered operation, consider implementing the following optimizations:

1. Use PSM (Power Saving Mode) or eDRX when supported:
   ```
   AT+CPSMS=1
   ```

2. Adjust MQTT keepalive value based on message frequency

3. Implement deep sleep between operations when possible

### Security Considerations

1. Use TLS for MQTT connections (set `MQTT_USE_TLS = true` in config)
2. Store authentication credentials securely
3. Implement message authentication to prevent spoofing
4. Consider encryption for sensitive message content

### Multi-SIM Support

For deployments requiring failover or multiple carriers:

1. Use multiple modules, each with a different SIM
2. Implement a load balancing strategy based on network availability
3. Configure each module with a unique IMEI in the bridge service 