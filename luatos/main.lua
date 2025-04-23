-- LuaTools needs PROJECT and VERSION information
PROJECT = "air_relay"
VERSION = "1.0.0"

log.info("main", PROJECT, VERSION)

-- Import required libraries
sys = require("sys")
require "sysplus" -- Required for HTTP library

-- Load configuration
local config = require("config")
log.info("MQTT", "Loaded configuration for", config.host)

-- Global MQTT client instance
local mqttc = nil

-- Will be set to IMEI
local client_id = nil 

-- MQTT topics
local TOPIC_SMS_INCOMING = "sms/incoming"
local TOPIC_SMS_OUTGOING = nil -- Will be set to "sms/outgoing/<imei>"
local TOPIC_SMS_STATUS = "sms/status" 
local TOPIC_DEVICE_STATUS = "device/status"

-- Message queue for storing failed outgoing messages
local message_queue = {}
local MAX_QUEUE_SIZE = 50 -- Limit queue size to prevent memory issues

-- Enable watchdog timer if available to prevent system freezes
if wdt then
    wdt.init(9000) -- Initialize watchdog with 9 second timeout
    sys.timerLoopStart(wdt.feed, 3000) -- Feed the watchdog every 3 seconds
end

-- Set DNS servers
socket.setDNS(nil, 1, "119.29.29.29")
socket.setDNS(nil, 2, "223.5.5.5")

-- Function to add a message to the queue
local function queue_message(topic, payload, qos)
    -- Check if we're at max capacity
    if #message_queue >= MAX_QUEUE_SIZE then
        -- Remove oldest message
        table.remove(message_queue, 1)
    end
    
    -- Add the new message to the queue
    table.insert(message_queue, {
        topic = topic,
        payload = payload,
        qos = qos,
        timestamp = os.time()
    })
    
    log.info("Queue", "Message queued. Queue size:", #message_queue)
end

-- Function to process the message queue
local function process_queue()
    if not mqttc then
        log.warn("Queue", "MQTT not initialized, can't process queue")
        return
    end
    
    log.info("Queue", "Processing message queue, size:", #message_queue)
    
    -- Process messages from oldest to newest
    while #message_queue > 0 do
        local msg = table.remove(message_queue, 1)
        log.info("Queue", "Publishing queued message to", msg.topic)
        
        local success = publish_with_retry(msg.topic, msg.payload, msg.qos)
        if not success then
            -- If publish_with_retry failed and couldn't re-queue, we would
            -- end up in an infinite loop, so we stop processing the queue
            log.warn("Queue", "Failed to publish message, stopping queue processing")
            break
        end
    end
    
    log.info("Queue", "Queue processing complete, remaining items:", #message_queue)
end

-- Function to publish MQTT message with retry logic
local function publish_with_retry(topic, payload, qos)
    if not mqttc then
        log.warn("MQTT", "MQTT client not initialized")
        queue_message(topic, payload, qos)
        return false
    end
    
    local msg_id = mqttc:publish(topic, payload, qos)
    
    if not msg_id and qos > 0 then
        log.warn("MQTT", "Failed to publish to", topic, "queuing for retry")
        queue_message(topic, payload, qos)
        return false
    end
    
    return msg_id ~= nil
end

-- Function to handle incoming SMS messages
local function handle_incoming_sms(phone_number, message_text)
    log.info("SMS", "Received SMS from:", phone_number, "Message:", message_text)
    
    -- Format as JSON according to the protocol specification
    local payload = {
        sender = phone_number,
        recipient = mobile.number() or "", -- Try to get the SIM phone number
        content = message_text,
        timestamp = os.time(),
        imei = mobile.imei()
    }
    
    -- Convert to JSON
    local json_payload = json.encode(payload)
    log.info("MQTT", "Publishing to", TOPIC_SMS_INCOMING, json_payload)
    
    -- Publish with retry
    publish_with_retry(TOPIC_SMS_INCOMING, json_payload, 1)
end

-- Function to send an SMS message
local function send_sms(recipient, content, message_id)
    log.info("SMS", "Sending SMS to:", recipient, "Message:", content, "ID:", message_id)
    
    -- Send the SMS
    local success = sms.send(recipient, content)
    
    -- Schedule a status update after sending
    sys.timerStart(function()
        -- Report delivery status
        local status_payload = {
            message_id = message_id,
            status = success and "delivered" or "failed",
            timestamp = os.time(),
            imei = mobile.imei()
        }
        
        -- Publish status update with retry
        publish_with_retry(TOPIC_SMS_STATUS, json.encode(status_payload), 1)
    end, 1000) -- Report status after 1 second
end

-- Function to publish device status
local function publish_device_status()
    -- Get signal strength
    local csq = mobile.csq()
    local signal_strength = 0
    if csq then
        -- Convert CSQ (0-31) to percentage (0-100)
        signal_strength = math.floor((csq / 31) * 100)
    end
    
    -- Get battery level if available
    local battery_level = 0
    if adc and adc.read then
        -- This is just a placeholder - actual implementation depends on hardware
        battery_level = 85 -- Example fixed value
    end
    
    local status_payload = {
        imei = mobile.imei(),
        status = "online",
        signal_strength = signal_strength,
        battery_level = battery_level,
        timestamp = os.time()
    }
    
    -- Handle device status separately - no retry
    if mqttc then
        local success = mqttc:publish(TOPIC_DEVICE_STATUS, json.encode(status_payload), 1)
        if not success then
            log.info("MQTT", "Device status not published - MQTT publish failed")
        end
    else
        log.info("MQTT", "Device status not published - MQTT not initialized")
    end
end

-- MQTT event callback function
local function on_mqtt_event(mqtt_client, event, data, payload)
    log.info("MQTT", "Event:", event, data)
    
    if event == "conack" then
        -- Connected to broker
        log.info("MQTT", "Connected to broker")
        
        -- Subscribe to outgoing SMS topic
        mqtt_client:subscribe(TOPIC_SMS_OUTGOING)
        log.info("MQTT", "Subscribed to", TOPIC_SMS_OUTGOING)
        
        -- Publish device status upon connection
        publish_device_status()
        
        -- Process any queued messages
        sys.timerStart(process_queue, 1000)
        
        -- Publish connection event
        sys.publish("mqtt_conack")
        
    elseif event == "recv" then
        -- Received a message
        log.info("MQTT", "Received message on topic:", data, "Payload:", payload)
        
        -- Process messages for sending SMS
        if data == TOPIC_SMS_OUTGOING then
            -- Parse the JSON payload
            local success, msg_data = pcall(json.decode, payload)
            if success and msg_data and msg_data.recipient and msg_data.content and msg_data.message_id then
                -- Send the SMS
                send_sms(msg_data.recipient, msg_data.content, msg_data.message_id)
            else
                log.error("MQTT", "Invalid outgoing SMS message format", payload)
                -- Could publish an error status back to the bridge
            end
        end
        
    elseif event == "disconnect" then
        -- Disconnected from broker
        log.info("MQTT", "Disconnected from broker")
    end
end

-- Network connection task
sys.taskInit(function()
    local imei = mobile.imei()
    log.info("Device", "IMEI:", imei)
    
    -- Set the client ID and outgoing SMS topic based on IMEI
    client_id = imei
    TOPIC_SMS_OUTGOING = "sms/outgoing/" .. imei
    
    -- Wait for network to be ready
    log.info("Network", "Waiting for network connection...")
    local success = sys.waitUntil("IP_READY", 120000) -- 2 minute timeout
    
    if not success then
        log.error("Network", "Failed to connect to network, rebooting...")
        -- Consider adding a reboot here if network connection consistently fails
        rtos.reboot()
    end
    
    log.info("Network", "IP ready.")
    
    log.info("MQTT", "Connecting to broker:", config.host, config.port)
    
    -- Create MQTT client
    mqttc = mqtt.create(nil, config.host, config.port, config.isssl)
    
    -- Configure MQTT client
    mqttc:auth(client_id, config.user, config.pass) -- Set user/pass if needed
    mqttc:keepalive(120) -- Keep alive interval in seconds
    mqttc:autoreconn(true, 5000) -- Auto reconnect with 5s delay
    
    -- Set up event handler for MQTT client
    mqttc:on(on_mqtt_event)
    
    -- Connect to MQTT broker
    mqttc:connect()
    
    -- Wait for successful connectin
    local connected = sys.waitUntil("mqtt_conack", 30000)
    if not connected then
        log.error("MQTT", "Failed to connect to broker, retrying...")
        -- Connection will be retried by autoreconn
    end
    
    -- Start periodic device status reporting
    sys.timerLoopStart(publish_device_status, 60000) -- Every 60 seconds
end)

-- SMS reception task
sys.subscribe("SMS_INC", function(phone_number, message_text)
    log.info("SMS", "Setting up SMS reception")
    
    if phone_number and message_text then
        handle_incoming_sms(phone_number, message_text)
    end
end)

-- Run the system
sys.run()
