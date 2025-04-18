from typing import Optional

import workers_kv

from src.models.schemas import MessageTracking, PhoneTopicMapping


class Database:
    def __init__(self, account_id: str, namespace_id: str, api_key: str):
        self.namespace = workers_kv.Namespace(
            account_id=account_id, namespace_id=namespace_id, api_key=api_key
        )

    def get_device_group(self, imei: str) -> Optional[int]:
        """Get Telegram group ID for a device IMEI"""
        key = f"device:{imei}"
        value = self.namespace.read(key)
        return int(value) if value else None

    def set_device_group(self, imei: str, group_id: Optional[int]) -> None:
        """Map device IMEI to a Telegram group"""
        key = f"device:{imei}"
        if group_id is None:
            self.namespace.delete_one(key)
        else:
            self.namespace.write({key: str(group_id)})

    def get_thread_topic(self, group_id: int, phone: str) -> Optional[int]:
        """Get topic ID for a phone number in a group"""
        key = f"thread:{group_id}:{phone}"
        value = self.namespace.read(key)
        if isinstance(value, dict) and "topic_id" in value:
            return int(value["topic_id"])
        return int(value) if value else None

    def set_thread_topic(
        self, group_id: int, phone: str, topic_id: int, topic_title: str = None
    ) -> None:
        """Map a phone number to a topic in a group"""
        key = f"thread:{group_id}:{phone}"
        mapping = PhoneTopicMapping(
            group_id=group_id,
            topic_id=topic_id,
            topic_title=topic_title or f"SMS: {phone}",
            last_activity=int(__import__("time").time()),
        )
        self.namespace.write({key: mapping.dict()})

    def get_group_device(self, group_id: int) -> Optional[str]:
        """Get device IMEI for a Telegram group (reverse lookup)"""
        key = f"group:{group_id}"
        return self.namespace.read(key)

    def set_group_device(self, group_id: int, imei: Optional[str]) -> None:
        """Map a Telegram group to a device IMEI"""
        key = f"group:{group_id}"
        if imei is None:
            self.namespace.delete_one(key)
        else:
            self.namespace.write({key: imei})

    def track_message(self, message_id: str, group_id: int, msg_id: int) -> None:
        """Track an outgoing message for status updates"""
        key = f"msg:{message_id}"
        tracking = MessageTracking(group_id=group_id, msg_id=msg_id)
        self.namespace.write({key: tracking.dict()})

    def get_tracked_message(self, message_id: str) -> Optional[MessageTracking]:
        """Get tracking info for a message"""
        key = f"msg:{message_id}"
        data = self.namespace.read(key)
        if data:
            return MessageTracking(**data)
        return None

    def delete_tracked_message(self, message_id: str) -> None:
        """Delete tracking info for a message"""
        key = f"msg:{message_id}"
        self.namespace.delete_one(key)
