from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

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