from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta
import random
import string

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=100, blank=True)
    profession = models.CharField(max_length=100, blank=True)
    about = models.TextField(blank=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', default='profile_pics/default.jpg')

    def __str__(self):
        return self.user.username
    
    # ✅ ADD THIS METHOD - This is CRUCIAL
    def get_profile_picture_url(self):
        '''Returns profile picture URL if file exists, otherwise None'''
        if self.profile_picture:
            try:
                # Check if file actually exists
                if self.profile_picture.storage.exists(self.profile_picture.name):
                    # Make sure it's not the default placeholder
                    if 'default' not in self.profile_picture.name:
                        return self.profile_picture.url
            except:
                pass
        return None

class Content(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    instructor = models.CharField(max_length=100)
    duration = models.CharField(max_length=50)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    likes = models.ManyToManyField(User, related_name='liked_content', blank=True)

    # Upload fields
    image = models.ImageField(upload_to='content_images/', blank=True, null=True)
    video = models.FileField(upload_to='content_videos/', blank=True, null=True)
    pdf = models.FileField(upload_to='content_pdfs/', blank=True, null=True)

    def total_likes(self):
        return self.likes.count()

    def __str__(self):
        return self.title

class Comment(models.Model):
    content = models.ForeignKey(Content, on_delete=models.CASCADE, related_name='comment_set')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.content.title}"

# 🔹 Automatically create a profile for each new user
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class PasswordResetOTP(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='password_reset_otp')
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now=True)
    is_verified = models.BooleanField(default=False)
    
    def is_otp_valid(self):
        expiry_time = self.created_at + timedelta(minutes=5)
        return timezone.now() < expiry_time
    
    def generate_otp(self):
        self.otp = ''.join(random.choices(string.digits, k=6))
        self.is_verified = False
        self.save()
        return self.otp
    







class FollowRequest(models.Model):

    sender =models.ForeignKey(User,related_name='sent_requests',on_delete=models.CASCADE)
    receiver=models.ForeignKey(User,related_name='received_requests',on_delete=models.CASCADE)
    created_at=models.DateTimeField(auto_now_add=True)

class Follow(models.Model):
    follower=models.ForeignKey(User,related_name='following',on_delete=models.CASCADE)
    following=models.ForeignKey(User,related_name='followers',on_delete=models.CASCADE)





# for chat option 



class ChatRoom(models.Model):
    user1 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_user1')
    user2 = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chat_user2')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Chat between {self.user1.username} & {self.user2.username}"


class Message(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(User, on_delete=models.CASCADE)
    text = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.username}: {self.text[:20]}"

    