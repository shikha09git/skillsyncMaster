from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
import json
from .models import ChatRoom, Message


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        self.user = self.scope['user']

        # Reject if not authenticated
        if not self.user.is_authenticated:
            await self.close()
            return

        # Verify user belongs to this chat
        if not await self.is_room_member():
            await self.close()
            return

        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message = data.get('message', '').strip()

            if not message:
                return

            # Save message to database (async-safe)
            saved = await self.save_message(message)

            if saved:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': message,
                        'username': self.user.username
                    }
                )
        except json.JSONDecodeError:
            pass

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'message': event['message'],
            'username': event['username']
        }))

    @database_sync_to_async
    def is_room_member(self):
        """Check if user belongs to this chat room."""
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            return self.user in [room.user1, room.user2]
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, message):
        """Save message to database."""
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            Message.objects.create(room=room, sender=self.user, text=message)
            return True
        except Exception:
            return False