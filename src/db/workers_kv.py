from typing import Optional, Dict, Any, List

import workers_kv
from cachetools import LRUCache

from src.models.schemas import MessageTracking


class CachedNamespace:
    """
    A cache wrapper for workers_kv.Namespace that uses an LRUCache to avoid 
    frequent remote database requests.
    """
    def __init__(self, namespace: workers_kv.Namespace, cache_size: int = 65536):
        self.namespace = namespace
        self.cache = LRUCache(maxsize=cache_size)
    
    def read(self, key: str) -> Any:
        """Read a value from cache or underlying namespace if not in cache"""
        if key in self.cache:
            return self.cache[key]
        
        value = self.namespace.read(key)
        if value is not None:
            self.cache[key] = value
        return value
    
    def write(self, data: Dict[str, Any]) -> None:
        """Write data to underlying namespace and update cache"""
        self.namespace.write(data)
        
        # Update cache with new values
        for key, value in data.items():
            self.cache[key] = value
    
    def delete_one(self, key: str) -> None:
        """Delete a key from underlying namespace and cache"""
        self.namespace.delete_one(key)
        
        # Remove from cache if present
        if key in self.cache:
            del self.cache[key]
    
    def delete_many(self, keys: List[str]) -> None:
        """Delete multiple keys from underlying namespace and cache"""
        self.namespace.delete_many(keys)
        
        # Remove from cache if present
        for key in keys:
            if key in self.cache:
                del self.cache[key]
                
    def clear_cache(self) -> None:
        """Clear the in-memory cache without affecting the underlying namespace data"""
        self.cache.clear()


class Database:
    def __init__(self, account_id: str, namespace_id: str, api_key: str, cache_size: int = 1000):
        namespace = workers_kv.Namespace(
            account_id=account_id, namespace_id=namespace_id, api_key=api_key
        )
        self.namespace = CachedNamespace(namespace, cache_size=cache_size)

    def get_group_from_device(self, imei: str) -> Optional[int]:
        """Get Telegram group ID for a device IMEI"""
        key = f"device_to_group:{imei}"
        value = self.namespace.read(key)
        return int(value) if value else None

    def get_device_from_group(self, group_id: int) -> Optional[str]:
        """Get device IMEI for a Telegram group"""
        key = f"group_to_device:{group_id}"
        return self.namespace.read(key)

    def map_device_group(self, imei: str, group_id: int) -> None:
        """
        Map a device to a Telegram group and create the reverse mapping
        
        This method maintains both:
        - device_to_group:{imei} -> group_id
        - group_to_device:{group_id} -> imei
        """
        self.namespace.write({
            f"device_to_group:{imei}": str(group_id),
            f"group_to_device:{group_id}": imei
        })
    
    def delete_device_group(self, imei: str, group_id: int) -> None:
        """Remove device-group mappings for given parameters"""
        self.namespace.delete_many([
            f"device_to_group:{imei}",
            f"group_to_device:{group_id}"
        ])

    def get_topic_from_phone(self, group_id: int, phone: str) -> Optional[int]:
        """Get topic ID for a phone number in a group"""
        key = f"phone_to_topic:{group_id}:{phone}"
        value = self.namespace.read(key)
        if isinstance(value, dict) and "topic_id" in value:
            return int(value["topic_id"])
        return int(value) if value else None

    def get_phone_from_topic(self, group_id: int, topic_id: int) -> Optional[str]:
        """Get phone number for a topic ID in a group (reverse lookup)"""
        key = f"topic_to_phone:{group_id}:{topic_id}"
        return self.namespace.read(key)

    def map_phone_topic(
        self, group_id: int, phone: str, topic_id: int
    ) -> None:
        """
        Map a phone number to a topic in a group and create the reverse mapping
        
        This method maintains both:
        - phone_to_topic:{group_id}:{phone} -> topic_id
        - topic_to_phone:{group_id}:{topic_id} -> phone
        """
        self.namespace.write({
            f"phone_to_topic:{group_id}:{phone}": str(topic_id),
            f"topic_to_phone:{group_id}:{topic_id}": phone
        })

    def remove_phone_topic(
        self, group_id: int, phone: str, topic_id: int
    ) -> None:
        """Remove phone-to-topic and topic-to-phone mappings for given parameters"""
        self.namespace.delete_many([
            f"phone_to_topic:{group_id}:{phone}",
            f"topic_to_phone:{group_id}:{topic_id}"
        ])

    def track_message(self, message_id: str, group_id: int, msg_id: int) -> None:
        """Track an outgoing message for status updates"""
        key = f"msg:{message_id}"
        tracking = MessageTracking(group_id=group_id, msg_id=msg_id)
        self.namespace.write({key: tracking.model_dump_json()})

    def get_tracked_message(self, message_id: str) -> Optional[MessageTracking]:
        """Get tracking info for a message"""
        key = f"msg:{message_id}"
        data = self.namespace.read(key)
        return MessageTracking.model_validate_json(data) if data else None
        
    def delete_tracked_message(self, message_id: str) -> None:
        """Delete tracking info for a message"""
        key = f"msg:{message_id}"
        self.namespace.delete_one(key)
        
    # Admin management methods
    def is_admin(self, user_id: int) -> bool:
        """Check if a user is an admin"""
        key = f"admins"
        admins = self.namespace.read(key)
        if not admins:
            return False
        
        try:
            admin_list = [int(admin_id) for admin_id in admins.split(',')]
            return user_id in admin_list
        except Exception:
            return False
    
    def add_admin(self, user_id: int) -> bool:
        """Add a user as an admin"""
        key = f"admins"
        admins = self.namespace.read(key)
        
        if not admins:
            # First admin - just add the user
            self.namespace.write({key: str(user_id)})
            return True
        
        try:
            admin_list = [int(admin_id) for admin_id in admins.split(',')]
            if user_id in admin_list:
                # Already an admin
                return False
                
            admin_list.append(user_id)
            self.namespace.write({key: ",".join(str(admin_id) for admin_id in admin_list)})
            return True
        except Exception:
            return False
            
    def has_admins(self) -> bool:
        """Check if there are any admins registered"""
        key = f"admins"
        admins = self.namespace.read(key)
        return bool(admins)
    
    def get_admins(self) -> List[int]:
        """Get list of all admin user IDs"""
        key = f"admins"
        admins = self.namespace.read(key)
        
        if not admins:
            return []
            
        try:
            return [int(admin_id) for admin_id in admins.split(',')]
        except Exception:
            return []
        
    def clear_cache(self) -> None:
        """Clear the in-memory cache"""
        self.namespace.clear_cache()
