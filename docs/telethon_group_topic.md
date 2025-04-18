# Telethon 操作 Telegram 群组论坛主题（Forum Topic）指南

## 1. 前提与初始化

1. 安装 Telethon（建议 ≥1.27.0）  
   ```bash
   pip install telethon
   ```
2. 在 Telegram 上创建 Bot，获取 `api_id`、`api_hash` 和 `bot_token`。
3. 初始化客户端示例：
   ```python
   from telethon import TelegramClient

   api_id    = 123456
   api_hash  = "your_api_hash"
   bot_token = "your_bot_token"

   client = TelegramClient('bot_session', api_id, api_hash).start(bot_token=bot_token)
   ```

## 2. 相关 RPC 方法导入

```python
from telethon.tl.functions.channels import (
    CreateForumTopicRequest,
    EditForumTopicRequest,
    DeleteTopicRequest,
    ToggleForumTopicRequest
)
from telethon.errors.rpcerrorlist import ChatWriteForbiddenError
```

## 3. 创建新主题

```python
async def create_topic(client: TelegramClient, chat_id: int, title: str) -> int:
    """
    在群组中创建论坛主题，返回 topic_id。
    """
    try:
        result = await client(CreateForumTopicRequest(
            channel=chat_id,
            title=title
        ))
        for update in result.updates:
            if hasattr(update, 'id'):
                return update.id
        raise RuntimeError("未能从结果中提取 topic_id")
    except ChatWriteForbiddenError:
        raise PermissionError("缺少"管理话题"权限，无法创建主题")
```

- `channel`：群组 ID（通常为负数）  
- 返回：主题 ID

## 4. 编辑 & 重命名主题

```python
async def edit_topic_title(client: TelegramClient, chat_id: int, topic_id: int, new_title: str):
    await client(EditForumTopicRequest(
        channel=chat_id,
        topic_id=topic_id,
        title=new_title
    ))
```

## 5. 关闭／重开主题

```python
async def toggle_topic(client: TelegramClient, chat_id: int, topic_id: int, close: bool):
    await client(ToggleForumTopicRequest(
        channel=chat_id,
        topic_id=topic_id,
        closed=close
    ))
```

- `close=True`：关闭归档  
- `close=False`：重新开放

## 6. 删除主题

```python
async def delete_topic(client: TelegramClient, chat_id: int, topic_id: int):
    await client(DeleteTopicRequest(
        channel=chat_id,
        topic_id=topic_id
    ))
```

## 7. 从消息事件中获取 topic_id

```python
from telethon.tl.custom import Message

def get_topic_id(self: Message) -> int | None:
    if self.reply_to and self.reply_to.forum_topic:
        return self.reply_to.reply_to_top_id or self.reply_to.reply_to_msg_id
    return None

Message.get_topic_id = get_topic_id
```

使用示例：
```python
@client.on(events.NewMessage)
async def handler(event: Message):
    topic = event.get_topic_id()
    print("当前消息的主题 ID:", topic)
```

## 8. 在指定主题发送消息

- 新开主题内的顶层消息：
  ```python
  await client.send_message(
      entity=chat_id,
      message="这是发到主题的新消息",
      parse_mode="html",
      reply_to=topic_id   # 主题 ID
  )
  ```
- 回复主题中的某条消息（子回复）：
  ```python
  await client.send_message(
      entity=chat_id,
      message="这是对某条消息的回复",
      parse_mode="html",
      reply_to=message_id  # 要回复的消息的 msg_id
  )
  ```

## 9. 常见异常与容错

- `ChatWriteForbiddenError`：缺少"管理话题"或"发送消息"权限  
- 其他 RPC 错误：可使用重试（如 tenacity）处理  
- 消息长度超限（约 4096 字符）：可用 Telethon 内置或自定义的文本拆分工具

## 10. 进阶：列出 & 管理已有主题

Telethon 无原生接口获取全部主题，可通过业务层记录创建时的 `topic_id` 或扫描带 `forum_topic` 属性的历史消息来维护主题列表。

---

### 常用示例汇总

```python
async with client:
    chat_id  = -1001234567890
    # 1. 创建主题
    topic_id = await create_topic(client, chat_id, "新闻讨论")

    # 2. 在主题中发送消息
    await client.send_message(chat_id, "欢迎讨论！", reply_to=topic_id)

    # 3. 重命名主题
    await edit_topic_title(client, chat_id, topic_id, "重大新闻")

    # 4. 关闭主题
    await toggle_topic(client, chat_id, topic_id, close=True)

    # 5. 重新开放
    await toggle_topic(client, chat_id, topic_id, close=False)

    # 6. 删除主题
    await delete_topic(client, chat_id, topic_id)
``` 