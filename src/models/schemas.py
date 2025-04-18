from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator

class Settings(BaseModel):
    """Application settings from environment variables"""
    # Telegram settings
    tg_api_id: int
    tg_api_hash: str
    tg_bot_token: str
    
    # MQTT settings
    mqtt_host: str
    mqtt_port: int
    mqtt_user: Optional[str] = None
    mqtt_password: Optional[str] = None
    mqtt_use_tls: bool = False
    
    # Cloudflare Workers KV settings
    cf_account_id: str
    cf_namespace_id: str
    cf_api_key: str
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = ""
        case_sensitive = False

class SMSMessage(BaseModel):
    """SMS message received from device"""
    sender: str = Field(..., description="Phone number of the SMS sender")
    recipient: Optional[str] = Field(None, description="Phone number that received the message")
    content: str = Field(..., description="Text content of the SMS message")
    timestamp: int = Field(..., description="Unix timestamp when the message was received")
    imei: str = Field(..., description="The IMEI number of the device that received the SMS")
    
    @validator('sender')
    def validate_phone_number(cls, v):
        # Simple validation for phone number format
        if not v.startswith('+'):
            return f"+{v}"
        return v

class OutgoingSMS(BaseModel):
    """SMS message to be sent to a phone number"""
    recipient: str = Field(..., description="Phone number to send the SMS to")
    content: str = Field(..., description="Text content to send")
    message_id: str = Field(..., description="Unique identifier for tracking message status")

class SMSStatus(BaseModel):
    """Status update for a sent SMS message"""
    message_id: str = Field(..., description="The unique identifier from the outgoing SMS")
    status: str = Field(..., description="Current status of the message (delivered, failed)")
    timestamp: int = Field(..., description="Unix timestamp of the status update")
    imei: str = Field(..., description="The IMEI number of the device reporting the status")

class DeviceStatus(BaseModel):
    """Status information for a device"""
    imei: str = Field(..., description="Device IMEI number")
    status: str = Field(..., description="Device status (online, offline, error)")
    signal_strength: int = Field(..., description="GSM signal strength percentage (0-100)")
    battery_level: int = Field(..., description="Battery level percentage (0-100)")
    timestamp: int = Field(..., description="Unix timestamp of the status update")

class PhoneTopicMapping(BaseModel):
    """Mapping between a phone number and a Telegram topic"""
    group_id: int
    topic_id: int
    topic_title: str
    last_activity: int

class MessageTracking(BaseModel):
    """Information for tracking an outgoing message"""
    group_id: int
    msg_id: int 