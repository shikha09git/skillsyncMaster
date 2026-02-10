"""
SkillSync - Main Views Module

This module contains all view functions for the SkillSync application including:
- Authentication (login, register, logout, password reset)
- Profile management
- Content management (posts, likes, comments)
- Social features (follow/unfollow)
- Real-time chat
- Search functionality
"""

import json
import logging

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed
from django.db.models import Q
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.conf import settings
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods, require_POST
from django.urls import reverse

from .forms import registerForm, contentForm, ProfileForm
from .models import (
    Content, Comment, Profile, PasswordResetOTP,
    FollowRequest, Follow, ChatRoom, Message
)

# Configure logger
logger = logging.getLogger(__name__)


# =============================================================================
# PUBLIC PAGES
# =============================================================================

def landing_page(request):
    """Landing page for unauthenticated users."""
    if request.user.is_authenticated:
        return redirect('home')
    return render(request, 'landing.html')


def home(request):
    """
    Main feed page showing all content posts.
    
    For authenticated users, also includes:
    - List of sent follow requests
    - List of users being followed
    """
    contents = Content.objects.select_related('created_by').prefetch_related(
        'likes', 'comment_set'
    ).order_by('-created_at')
    
    sent_requests = []
    following = []
    
    if request.user.is_authenticated:
        sent_requests = list(
            FollowRequest.objects.filter(sender=request.user)
            .values_list('receiver_id', flat=True)
        )
        following = list(
            Follow.objects.filter(follower=request.user)
            .values_list('following_id', flat=True)
        )
    
    context = {
        'contents': contents,
        'default_avatar': True,
        'sent_requests': sent_requests,
        'following': following,
    }
    return render(request, 'home.html', context)


def about(request):
    """About page."""
    return render(request, 'about.html')


# =============================================================================
# AUTHENTICATION
# =============================================================================

def register(request):
    """
    Handle user registration with welcome email and success notification.
    
    This view:
    - Validates user registration form
    - Creates new user account
    - Sends welcome email to new user
    - Shows success popup message
    - Redirects to login page
    """
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        form = registerForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                
                # Send welcome email (non-blocking - don't fail registration if email fails)
                email_sent = send_registration_welcome_email(user, user.email)
                
                if email_sent:
                    messages.success(
                        request,
                        f'✅ Registration Successful! Welcome {user.username}! 🎉\n\n'
                        f'A welcome email has been sent to {user.email}. Please check your inbox.',
                        extra_tags='registration_success'
                    )
                else:
                    messages.warning(
                        request,
                        f'✅ Registration Successful! Welcome {user.username}!\n\n'
                        f'Note: Welcome email could not be sent. You can proceed to login.',
                        extra_tags='registration_warning'
                    )
                
                return redirect('login')
            
            except Exception as e:
                logger.error(f"Registration error: {str(e)}")
                messages.error(
                    request,
                    '❌ Error during registration. Please try again.',
                    extra_tags='registration_error'
                )
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    field_name = field.replace('_', ' ').title()
                    messages.error(request, f'{field_name}: {error}')
    else:
        form = registerForm()
    
    return render(request, 'register.html', {'form': form})


def login_user(request):
    """Handle user login."""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '')
        
        if not username or not password:
            return render(request, 'login.html', {'error': 'Please enter both username and password.'})
        
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            # Redirect to 'next' parameter if exists, otherwise home
            next_url = request.GET.get('next', 'home')
            return redirect(next_url)
        else:
            return render(request, 'login.html', {'error': 'Invalid username or password.'})
    
    return render(request, 'login.html')


def logout_user(request):
    """Handle user logout."""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


def guest_login(request):
    """
    Allow users to explore the platform as a guest.
    Creates a guest account if it doesn't exist.
    """
    GUEST_USERNAME = 'guest'
    GUEST_PASSWORD = 'guest123'
    
    user = authenticate(username=GUEST_USERNAME, password=GUEST_PASSWORD)
    
    if user is None:
        # Create guest user if doesn't exist
        guest_user, created = User.objects.get_or_create(
            username=GUEST_USERNAME,
            defaults={'email': 'guest@skillsync.local'}
        )
        if created:
            guest_user.set_password(GUEST_PASSWORD)
            guest_user.save()
        user = guest_user
    
    # Ensure profile exists
    Profile.objects.get_or_create(user=user)
    login(request, user)
    messages.info(request, 'You are logged in as a guest. Some features may be limited.')
    return redirect('home')


# =============================================================================
# PASSWORD RESET
# =============================================================================

def forgot_password(request):
    """Send OTP to user's email for password reset."""
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()
        
        if not email:
            messages.error(request, 'Please enter an email address.')
            return render(request, 'forgot_password.html')
        
        try:
            user = User.objects.get(email__iexact=email)
            otp_obj, created = PasswordResetOTP.objects.get_or_create(user=user)
            otp = otp_obj.generate_otp()
            
            if send_password_reset_email(user, otp, email):
                messages.success(request, 'OTP sent to your email address!')
                return redirect('verify_otp', user_id=user.id)
            else:
                messages.error(request, 'Error sending email. Please try again.')
        
        except User.DoesNotExist:
            # Don't reveal that the email doesn't exist (security best practice)
            messages.info(request, 'If this email exists in our system, you will receive an OTP.')
            return render(request, 'forgot_password.html')
        except Exception as e:
            logger.error(f"Password reset error: {str(e)}")
            messages.error(request, 'Error processing request. Please try again.')
    
    return render(request, 'forgot_password.html')


def verify_otp(request, user_id):
    """Verify OTP entered by user."""
    user = get_object_or_404(User, id=user_id)
    
    if request.method == 'POST':
        otp = request.POST.get('otp', '').strip()
        
        if not otp:
            messages.error(request, 'Please enter the OTP.')
            return render(request, 'verify_otp.html', {'user': user})
        
        try:
            otp_obj = PasswordResetOTP.objects.get(user=user)
            
            if not otp_obj.is_otp_valid():
                messages.error(request, 'OTP has expired. Please request a new one.')
                return redirect('forgot_password')
            
            if otp_obj.otp == otp:
                otp_obj.is_verified = True
                otp_obj.save()
                messages.success(request, 'OTP verified! Now set your new password.')
                return redirect('reset_password', user_id=user.id)
            else:
                messages.error(request, 'Invalid OTP. Please try again.')
        
        except PasswordResetOTP.DoesNotExist:
            messages.error(request, 'Please request OTP first.')
            return redirect('forgot_password')
    
    return render(request, 'verify_otp.html', {'user': user})


def reset_password(request, user_id):
    """Reset password after OTP verification."""
    user = get_object_or_404(User, id=user_id)
    
    try:
        otp_obj = PasswordResetOTP.objects.get(user=user)
        if not otp_obj.is_verified:
            messages.error(request, 'Please verify OTP first.')
            return redirect('verify_otp', user_id=user.id)
    except PasswordResetOTP.DoesNotExist:
        messages.error(request, 'Invalid request. Please start over.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        
        # Validation
        errors = []
        if not password1 or not password2:
            errors.append('Please enter password in both fields.')
        if password1 != password2:
            errors.append('Passwords do not match.')
        if len(password1) < 8:
            errors.append('Password must be at least 8 characters long.')
        
        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'reset_password.html', {'user': user})
        
        # Update password
        user.set_password(password1)
        user.save()
        
        # Clean up OTP record
        otp_obj.delete()
        
        messages.success(request, 'Password reset successful! Please log in with your new password.')
        return redirect('login')
    
    return render(request, 'reset_password.html', {'user': user})


# =============================================================================
# EMAIL HELPERS
# =============================================================================

def send_password_reset_email(user, otp, recipient_email):
    """
    Send password reset email with OTP using HTML template.
    
    Args:
        user: Django User object
        otp: One-time password (6 digits)
        recipient_email: User's email address
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        context = {
            'username': user.username,
            'otp': otp,
            'otp_validity': '5 minutes',
            'support_email': settings.DEFAULT_FROM_EMAIL,
        }
        
        html_message = render_to_string('emails/password_reset_email.html', context)
        
        send_mail(
            subject='Password Reset OTP - SkillSync',
            message=f'Your OTP for password reset is: {otp}. Valid for 5 minutes.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return True
    
    except Exception as e:
        logger.error(f"Error sending password reset email: {str(e)}")
        return False


def send_registration_welcome_email(user, recipient_email):
    """
    Send welcome email to newly registered user.
    
    Args:
        user: Django User object
        recipient_email: User's email address
    
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        context = {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name or user.username,
            'registration_date': user.date_joined.strftime('%B %d, %Y'),
            'support_email': settings.DEFAULT_FROM_EMAIL,
            'dashboard_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
        }
        
        html_message = render_to_string('emails/registration_welcome_email.html', context)
        
        send_mail(
            subject='Welcome to SkillSync! 🎉',
            message=f'Welcome {user.username}! Thank you for joining SkillSync.',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return True
    
    except Exception as e:
        logger.error(f"Error sending registration welcome email: {str(e)}")
        return False


# =============================================================================
# PROFILE MANAGEMENT
# =============================================================================

def view_profile(request, username):
    """
    View a user's public profile by username.
    
    Shows:
    - User info and bio
    - User's posts
    - Follower/following counts
    - Follow/unfollow button for authenticated users
    """
    user_obj = get_object_or_404(User, username=username)
    profile, created = Profile.objects.get_or_create(user=user_obj)
    
    # Check if current user follows this profile
    is_following = False
    is_own_profile = False
    
    if request.user.is_authenticated:
        is_own_profile = request.user == user_obj
        if not is_own_profile:
            is_following = Follow.objects.filter(
                follower=request.user,
                following=user_obj
            ).exists()
    
    # Get user's posts with optimized queries
    user_posts = Content.objects.filter(created_by=user_obj).prefetch_related(
        'likes', 'comment_set'
    ).order_by('-created_at')
    
    # Counts
    posts_count = user_posts.count()
    followers_count = Follow.objects.filter(following=user_obj).count()
    following_count = Follow.objects.filter(follower=user_obj).count()
    
    context = {
        'profile': profile,
        'user_posts': user_posts,
        'is_following': is_following,
        'is_own_profile': is_own_profile,
        'posts_count': posts_count,
        'followers_count': followers_count,
        'following_count': following_count,
    }
    return render(request, 'profile_view.html', context)


def profile(request, user_id):
    """
    View a user's public profile by user ID.
    Redirects to username-based URL for consistency.
    """
    user_obj = get_object_or_404(User, id=user_id)
    return redirect('view_profile', username=user_obj.username)


@login_required
def edit_profile(request):
    """Edit the current user's profile."""
    profile, created = Profile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = ProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully!")
            return redirect('view_profile', username=request.user.username)
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ProfileForm(instance=profile)
    
    return render(request, 'profile_edit.html', {'form': form})


def profile_dashboard(request, username):
    """
    Dashboard page showing followers and following lists with pagination.
    Publicly viewable; follow/unfollow actions require login.
    """
    profile_user = get_object_or_404(User, username=username)
    
    # Followers: people who follow profile_user
    followers_qs = Follow.objects.filter(
        following=profile_user
    ).select_related('follower', 'follower__profile').order_by('-id')
    followers_count = followers_qs.count()
    
    # Following: people that profile_user follows
    following_qs = Follow.objects.filter(
        follower=profile_user
    ).select_related('following', 'following__profile').order_by('-id')
    following_count = following_qs.count()
    
    # Check if viewer follows profile_user and precompute following IDs
    viewer_follows = False
    viewer_following_ids = set()
    
    if request.user.is_authenticated:
        viewer_follows = Follow.objects.filter(
            follower=request.user, following=profile_user
        ).exists()
        viewer_following_ids = set(
            Follow.objects.filter(follower=request.user)
            .values_list('following_id', flat=True)
        )
    
    # Pagination
    followers_page_number = request.GET.get('followers_page', 1)
    following_page_number = request.GET.get('following_page', 1)
    
    followers_paginator = Paginator(followers_qs, 12)
    following_paginator = Paginator(following_qs, 12)
    
    followers_page = followers_paginator.get_page(followers_page_number)
    following_page = following_paginator.get_page(following_page_number)
    
    context = {
        'profile_user': profile_user,
        'followers_page': followers_page,
        'following_page': following_page,
        'followers_count': followers_count,
        'following_count': following_count,
        'viewer_follows': viewer_follows,
        'viewer_following_ids': viewer_following_ids,
    }
    return render(request, 'profile_dashboard.html', context)


# =============================================================================
# CONTENT MANAGEMENT
# =============================================================================

@login_required
def add_content(request):
    """Create new content/post."""
    if request.method == "POST":
        form = contentForm(request.POST, request.FILES)
        if form.is_valid():
            content = form.save(commit=False)
            content.created_by = request.user
            content.save()
            messages.success(request, "Content added successfully!")
            return redirect('home')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = contentForm()
    
    return render(request, 'add_content.html', {'form': form})


def content_detail(request, content_id):
    """View a single content post with its comments."""
    content = get_object_or_404(
        Content.objects.select_related('created_by').prefetch_related('likes'),
        id=content_id
    )
    comments = Comment.objects.filter(content=content).select_related('user').order_by('-created_at')
    
    return render(request, 'content_detail.html', {
        'content': content,
        'comments': comments
    })


@login_required
def delete_content(request, course_id):
    """Delete a content post (owner only)."""
    post = get_object_or_404(Content, id=course_id)
    
    if post.created_by != request.user:
        messages.error(request, "You are not allowed to delete this content.")
        return redirect('home')
    
    post.delete()
    messages.success(request, "Content deleted successfully!")
    return redirect('home')


@login_required
def like_content(request, course_id):
    """Toggle like on a content post. Supports AJAX."""
    post = get_object_or_404(Content, id=course_id)
    
    if request.user in post.likes.all():
        post.likes.remove(request.user)
        liked = False
    else:
        post.likes.add(request.user)
        liked = True
    
    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'liked': liked,
            'total_likes': post.likes.count()
        })
    
    return redirect('home')


# =============================================================================
# COMMENTS
# =============================================================================

@login_required
def add_comment(request, post_id):
    """Add a comment to a content post. Supports AJAX."""
    post = get_object_or_404(Content, id=post_id)
    
    if request.method != "POST":
        return JsonResponse({'error': 'Invalid request method'}, status=405)
    
    comment_body = ""
    
    # Handle both JSON and form data
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body.decode('utf-8'))
            comment_body = data.get("body", "").strip()
        except (json.JSONDecodeError, UnicodeDecodeError):
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    else:
        comment_body = request.POST.get("body", "").strip()
    
    if not comment_body:
        return JsonResponse({'error': 'Comment cannot be empty'}, status=400)
    
    if len(comment_body) > 1000:
        return JsonResponse({'error': 'Comment is too long (max 1000 characters)'}, status=400)
    
    # Create comment
    comment = Comment.objects.create(
        user=request.user,
        content=post,
        body=comment_body
    )
    
    return JsonResponse({
        'success': True,
        'id': comment.id,
        'username': comment.user.username,
        'body': comment.body,
        'created_at': comment.created_at.strftime("%Y-%m-%d %H:%M:%S")
    })


@login_required
def delete_comment(request, comment_id):
    """Delete a comment (owner only). Supports AJAX."""
    comment = get_object_or_404(Comment, id=comment_id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    # Only comment owner can delete
    if request.user != comment.user:
        if is_ajax:
            return JsonResponse({
                'success': False,
                'error': 'You are not allowed to delete this comment.'
            }, status=403)
        messages.error(request, "You are not allowed to delete this comment.")
        return redirect(request.META.get("HTTP_REFERER", "home"))
    
    content_id = comment.content.id
    comment.delete()
    
    if is_ajax:
        return JsonResponse({'success': True, 'comment_id': comment_id})
    
    messages.success(request, "Comment deleted successfully!")
    return redirect('content_detail', content_id=content_id)


# =============================================================================
# SEARCH
# =============================================================================

def search(request):
    """Search contents by keyword in title, description, or instructor."""
    query = request.GET.get('q', '').strip()
    
    if query:
        contents = Content.objects.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(instructor__icontains=query)
        ).select_related('created_by').prefetch_related('likes').order_by('-created_at')
    else:
        contents = Content.objects.select_related('created_by').prefetch_related(
            'likes'
        ).order_by('-created_at')
    
    # Add pagination for better performance
    paginator = Paginator(contents, 20)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'contents': page_obj,
        'query': query,
        'page_obj': page_obj,
    }
    return render(request, 'home.html', context)


# =============================================================================
# FOLLOW SYSTEM
# =============================================================================

@login_required
def send_follow_request(request, user_id):
    """
    Create an immediate follow relationship.
    
    This view creates a Follow record immediately (not a request that needs approval).
    """
    receiver = get_object_or_404(User, id=user_id)
    
    # Prevent following yourself
    if request.user == receiver:
        messages.warning(request, "You cannot follow yourself.")
        return redirect('view_profile', username=receiver.username)
    
    # Create the follow relationship if it doesn't exist
    follow, created = Follow.objects.get_or_create(
        follower=request.user,
        following=receiver
    )
    
    if created:
        messages.success(request, f"You are now following {receiver.username}.")
    else:
        messages.info(request, f"You are already following {receiver.username}.")
    
    # Clean up any pending follow requests
    FollowRequest.objects.filter(sender=request.user, receiver=receiver).delete()
    
    # Redirect back to referrer or profile
    next_url = request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('view_profile', username=receiver.username)


@login_required
def unfollow(request, user_id):
    """Remove a follow relationship."""
    target = get_object_or_404(User, id=user_id)
    
    deleted_count, _ = Follow.objects.filter(
        follower=request.user,
        following=target
    ).delete()
    
    if deleted_count > 0:
        messages.success(request, f"You have unfollowed {target.username}.")
    
    # Redirect back to referrer or profile
    next_url = request.META.get('HTTP_REFERER')
    if next_url:
        return redirect(next_url)
    return redirect('view_profile', username=target.username)


@login_required
def accept_request(request, request_id):
    """Accept a follow request."""
    follow_request = get_object_or_404(FollowRequest, id=request_id)
    
    if follow_request.receiver != request.user:
        messages.error(request, "You cannot accept this request.")
        return redirect('home')
    
    # Create follow relationship
    Follow.objects.get_or_create(
        follower=follow_request.sender,
        following=follow_request.receiver
    )
    
    # Delete the request
    sender_username = follow_request.sender.username
    follow_request.delete()
    
    messages.success(request, f"You accepted {sender_username}'s follow request.")
    return redirect('home')


@login_required
def reject_request(request, request_id):
    """Reject a follow request."""
    follow_request = get_object_or_404(FollowRequest, id=request_id)
    
    if follow_request.receiver != request.user:
        messages.error(request, "You cannot reject this request.")
        return redirect('home')
    
    sender_username = follow_request.sender.username
    follow_request.delete()
    
    messages.info(request, f"You rejected {sender_username}'s follow request.")
    return redirect('home')


# =============================================================================
# CHAT SYSTEM
# =============================================================================

@login_required
def chat_list(request):
    """List all chat rooms for the current user."""
    rooms = ChatRoom.objects.filter(
        Q(user1=request.user) | Q(user2=request.user)
    ).select_related('user1', 'user2', 'user1__profile', 'user2__profile').order_by('-created_at')
    
    # Add last message preview for each room
    rooms_with_preview = []
    for room in rooms:
        other_user = room.user2 if room.user1 == request.user else room.user1
        last_message = room.messages.order_by('-timestamp').first()
        rooms_with_preview.append({
            'room': room,
            'other_user': other_user,
            'last_message': last_message,
        })
    
    return render(request, 'chat_list.html', {
        'rooms': rooms_with_preview
    })


@login_required
def start_chat(request, user_id):
    """Start or open an existing chat with a user."""
    other_user = get_object_or_404(User, id=user_id)
    
    # Don't allow chatting with yourself
    if request.user == other_user:
        messages.warning(request, "You cannot chat with yourself.")
        return redirect('chat_list')
    
    # Check if chat already exists (check both directions)
    chat = ChatRoom.objects.filter(
        (Q(user1=request.user) & Q(user2=other_user)) |
        (Q(user1=other_user) & Q(user2=request.user))
    ).first()
    
    if not chat:
        # Create new chat room with consistent user ordering
        user1, user2 = sorted([request.user, other_user], key=lambda u: u.id)
        chat = ChatRoom.objects.create(user1=user1, user2=user2)
    
    return redirect('chat_detail', room_id=chat.id)


@login_required
def chat_room(request, username):
    """Chat with a user by username."""
    other_user = get_object_or_404(User, username=username)
    
    if request.user == other_user:
        messages.warning(request, "You cannot chat with yourself.")
        return redirect('chat_list')
    
    # Get or create room with consistent ordering
    user1, user2 = sorted([request.user, other_user], key=lambda u: u.id)
    room, created = ChatRoom.objects.get_or_create(user1=user1, user2=user2)
    
    if request.method == 'POST':
        text = request.POST.get('message', '').strip()
        if text:
            Message.objects.create(
                room=room,
                sender=request.user,
                text=text
            )
        return redirect('chat_room', username=other_user.username)
    
    chat_messages = room.messages.select_related('sender').order_by('timestamp')
    
    return render(request, 'chat_room.html', {
        'room': room,
        'messages': chat_messages,
        'other_user': other_user
    })


@login_required
def chat_detail(request, room_id):
    """View a specific chat room by ID."""
    chat = get_object_or_404(
        ChatRoom.objects.select_related('user1', 'user2'),
        id=room_id
    )
    
    # Verify user is part of this chat
    if request.user not in [chat.user1, chat.user2]:
        messages.error(request, "You don't have access to this chat.")
        return redirect('chat_list')
    
    other_user = chat.user2 if chat.user1 == request.user else chat.user1
    
    if request.method == 'POST':
        text = request.POST.get('message', '').strip()
        if text:
            Message.objects.create(
                room=chat,
                sender=request.user,
                text=text
            )
        return redirect('chat_detail', room_id=chat.id)
    
    chat_messages = chat.messages.select_related('sender').order_by('timestamp')
    
    return render(request, 'chat_detail.html', {
        'chat': chat,
        'messages': chat_messages,
        'other_user': other_user
    })






@login_required
def change_password(request):
    if request.method == 'POST':
        current = request.POST.get('current_password', '')
        new1 = request.POST.get('new_password', '')
        new2 = request.POST.get('confirm_password', '')

        if not request.user.check_password(current):
            messages.error(request, 'Current password is incorrect.')
            return redirect('edit_profile')

        if new1 != new2:
            messages.error(request, 'New passwords do not match.')
            return redirect('edit_profile')

        if len(new1) < 8:
            messages.error(request, 'New password must be at least 8 characters.')
            return redirect('edit_profile')

        request.user.set_password(new1)
        request.user.save()
        update_session_auth_hash(request, request.user)  # keep user logged in
        messages.success(request, 'Password updated successfully.')
        return redirect('edit_profile')

    return redirect('edit_profile')

@login_required
def delete_account(request):
    if request.method == 'POST':
        username = request.user.username
        request.user.delete()
        messages.success(request, f'Account "{username}" deleted.')
        return redirect('landing')  # or 'login'
    # For safety, only allow POST
    messages.error(request, 'Invalid request.')
    return redirect('edit_profile')