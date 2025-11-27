from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from .forms import registerForm, contentForm, ProfileForm
from .models import Content, Comment, Profile, PasswordResetOTP
from django.db.models import Q
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.models import User
import json
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string



def landing_page(request):
    return render(request, 'landing.html')


def home(request):
    contents = Content.objects.all().order_by('-created_at')
    context = {
        'contents': contents,
        'default_avatar': True
    }
    return render(request, 'home.html', context)

# def register(request):
#     if request.method == 'POST':
#         form = registerForm(request.POST)
#         if form.is_valid():
#             form.save()
#             return redirect('login')
#     else:
#         form = registerForm()
#     return render(request, 'register.html', {'form': form})

def register(request):
    """
    Handle user registration with welcome email and success notification
    
    This view:
    - Validates user registration form
    - Creates new user account
    - Sends welcome email to new user
    - Shows success popup message
    - Redirects to login page
    """
    if request.method == 'POST':
        form = registerForm(request.POST)
        if form.is_valid():
            try:
                # Save user to database
                user = form.save()
                
                # Send welcome email
                email_sent = send_registration_welcome_email(user, user.email)
                
                if email_sent:
                    # Success message with email confirmation
                    messages.success(
                        request,
                        f'✅ Registration Successful! Welcome {user.username}! 🎉\n\nA welcome email has been sent to {user.email}. Please check your inbox.',
                        extra_tags='registration_success'
                    )
                else:
                    # Success but email failed
                    messages.warning(
                        request,
                        f'✅ Registration Successful! Welcome {user.username}!\n\nNote: Welcome email could not be sent. You can proceed to login.',
                        extra_tags='registration_warning'
                    )
                
                return redirect('login')
            
            except Exception as e:
                messages.error(
                    request,
                    f'❌ Error during registration. Please try again.',
                    extra_tags='registration_error'
                )
                print(f"Registration error: {str(e)}")
        
        else:
            # Form validation errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    
    else:
        form = registerForm()
    
    return render(request, 'register.html', {'form': form})

def guest_login(request):
    user = authenticate(username='guest', password='guest123')
    if user is not None:
        Profile.objects.get_or_create(user=user)
        login(request, user)
        return redirect('home')
    else:
        guest_user, created = User.objects.get_or_create(username='guest')
        if created:
            guest_user.set_password('guest123')
            guest_user.save()
            Profile.objects.create(user=guest_user)
        login(request, guest_user)
        return redirect('home')

def login_user(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user:
            login(request, user)
            return redirect('home')
        else:
            return render(request, 'login.html', {'error': 'Invalid username or password'})
    return render(request, 'login.html')

def logout_user(request):
    logout(request)
    return redirect('login')

@login_required
def view_profile(request, username):
    user = get_object_or_404(User, username=username)
    profile, created = Profile.objects.get_or_create(user=user)
    user_posts = Content.objects.filter(created_by=user).order_by('-created_at')
    context = {'profile': profile, 'user_posts': user_posts}
    return render(request, 'profile_view.html', context)

@login_required
def edit_profile(request):
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

@login_required
def add_content(request):
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

@login_required
def like_content(request, course_id):
    post = get_object_or_404(Content, id=course_id)
    if request.user in post.likes.all():
        post.likes.remove(request.user)
        liked = False
    else:
        post.likes.add(request.user)
        liked = True

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'liked': liked, 'total_likes': post.likes.count()})
    return redirect('home')

@login_required
def add_comment(request, post_id):
    post = get_object_or_404(Content, id=post_id)

    if request.method == "POST":
        comment_body = ""

        # Check if AJAX sends JSON
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

        # Create comment
        comment = Comment.objects.create(user=request.user, content=post, body=comment_body)

        # Return JSON for AJAX
        return JsonResponse({
            'success': True,
            'id': comment.id,
            'username': comment.user.username,
            'body': comment.body,
            'created_at': comment.created_at.strftime("%Y-%m-%d %H:%M:%S")
        })

    return JsonResponse({'error': 'Invalid request'}, status=400)


@login_required
def delete_content(request, course_id):
    post = get_object_or_404(Content, id=course_id)
    if post.created_by == request.user:
        post.delete()
        messages.success(request, "Content deleted successfully!")
    else:
        messages.error(request, "You are not allowed to delete this content.")
    return redirect('home')

def about(request):
    return render(request, 'about.html')


# @login_required
# def delete_comment(request, comment_id):
#     comment = get_object_or_404(Comment, id=comment_id)

#     if request.user != comment.user:
#         return JsonResponse({"success": False})

#     post = comment.post
#     comment.delete()

#     return JsonResponse({
#         "success": True,
#         "post_id": post.id,
#         "total_comments": post.comments.count()
#     })


def content_detail(request, content_id):
    content = get_object_or_404(Content, id=content_id)
    comments = Comment.objects.filter(content=content).order_by('-created_at')
    return render(request, 'content_detail.html', {'content': content, 'comments': comments})


def search(request):
    """Search contents by keyword in title, description or instructor."""
    q = request.GET.get('q', '').strip()
    if q:
        contents = Content.objects.filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(instructor__icontains=q)
        ).order_by('-created_at')
    else:
        # If empty query, show all content (helps when user submits empty search)
        contents = Content.objects.all().order_by('-created_at')

    context = {
        'contents': contents,
        'query': q,
    }
    # Reuse the home template to keep styling and post layout consistent
    return render(request, 'home.html', context)


@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)

    # Only allow POST for AJAX deletion
    is_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if request.method != 'POST' and is_ajax:
        return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)

    if request.user == comment.user:   # Only comment owner can delete
        comment.delete()
        if is_ajax:
            return JsonResponse({'success': True, 'comment_id': comment_id})
        messages.success(request, "Comment deleted successfully!")
    else:
        if is_ajax:
            return JsonResponse({'success': False, 'error': 'You are not allowed to delete this comment.'}, status=403)
        messages.error(request, "You are not allowed to delete this comment.")

    # For non-AJAX requests, redirect back
    return redirect(request.META.get("HTTP_REFERER", "home"))



def forgot_password(request):
    """Send OTP to user's email"""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        
        if not email:
            messages.error(request, 'Please enter an email address.')
            return render(request, 'forgot_password.html')
        
        try:
            user = User.objects.get(email=email)
            otp_obj, created = PasswordResetOTP.objects.get_or_create(user=user)
            otp = otp_obj.generate_otp()
            
            # Send email with OTP using HTML template
            if send_password_reset_email(user, otp, email):
                messages.success(request, 'OTP sent to your email address!')
                return redirect('verify_otp', user_id=user.id)
            else:
                messages.error(request, 'Error sending email. Please try again.')
        
        except User.DoesNotExist:
            messages.error(request, 'Email address not found in our system.')
        except Exception as e:
            messages.error(request, 'Error processing request. Please try again.')
            print(f"Error: {str(e)}")
    
    return render(request, 'forgot_password.html')


def send_password_reset_email(user, otp, recipient_email):
    """
    Send password reset email with OTP using HTML template
    
    This function sends a professionally formatted HTML email to the user containing
    their one-time password (OTP) for password reset. It includes security warnings,
    usage instructions, and a responsive design that works on all devices.
    
    Args:
        user (User): Django User object containing username and other user details
        otp (str): One-time password generated for password reset (typically 6 digits)
        recipient_email (str): User's email address where OTP will be sent
    
    Returns:
        bool: True if email sent successfully, False otherwise
    
    Raises:
        Catches and logs any email sending exceptions internally
    
    Example:
        >>> user = User.objects.get(id=1)
        >>> otp = '123456'
        >>> success = send_password_reset_email(user, otp, 'user@example.com')
        >>> if success:
        ...     messages.success(request, 'OTP sent to your email!')
    """
    try:
        # Prepare context for email template
        context = {
            'username': user.username,
            'otp': otp,
            'otp_validity': '5 minutes',
            'support_email': settings.DEFAULT_FROM_EMAIL,
        }
        
        # Render HTML email template
        html_message = render_to_string('emails/password_reset_email.html', context)
        
        # Send email
        send_mail(
            subject='Password Reset OTP - SkillSync',
            message=f'Your OTP for password reset is: {otp}',  # Fallback plain text
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_message,  # Send HTML version
            fail_silently=False,
        )
        
        return True
    
    except Exception as e:
        print(f"Error sending password reset email: {str(e)}")
        return False

def verify_otp(request, user_id):
    """Verify OTP entered by user"""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('login')
    
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
    """Reset password after OTP verification"""
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        messages.error(request, 'User not found.')
        return redirect('login')
    
    try:
        otp_obj = PasswordResetOTP.objects.get(user=user)
        if not otp_obj.is_verified:
            messages.error(request, 'Please verify OTP first.')
            return redirect('verify_otp', user_id=user.id)
    except PasswordResetOTP.DoesNotExist:
        messages.error(request, 'Invalid request. Please start over.')
        return redirect('forgot_password')
    
    if request.method == 'POST':
        password1 = request.POST.get('password1', '').strip()
        password2 = request.POST.get('password2', '').strip()
        
        # Validation
        if not password1 or not password2:
            messages.error(request, 'Please enter password in both fields.')
            return render(request, 'reset_password.html', {'user': user})
        
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'reset_password.html', {'user': user})
        
        if len(password1) < 8:
            messages.error(request, 'Password must be at least 8 characters long.')
            return render(request, 'reset_password.html', {'user': user})
        
        # Update password
        user.set_password(password1)
        user.save()
        
        # Clean up OTP record
        otp_obj.delete()
        
        messages.success(request, 'Password reset successful! Please log in with your new password.')
        return redirect('login')
    
    return render(request, 'reset_password.html', {'user': user})

def send_registration_welcome_email(user, recipient_email):
    """
    Send welcome email to newly registered user
    
    This function sends a professionally formatted HTML email to welcome the user
    to SkillSync. It includes account details, getting started instructions, and
    encourages them to explore the platform.
    
    Args:
        user (User): Django User object containing username and other user details
        recipient_email (str): User's email address where welcome email will be sent
    
    Returns:
        bool: True if email sent successfully, False otherwise
    
    Raises:
        Catches and logs any email sending exceptions internally
    
    Example:
        >>> user = User.objects.create_user(username='john_doe', email='john@example.com')
        >>> success = send_registration_welcome_email(user, 'john@example.com')
        >>> if success:
        ...     messages.success(request, 'Welcome email sent!')
    """
    try:
        # Prepare context for email template
        context = {
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name or user.username,
            'registration_date': user.date_joined.strftime('%B %d, %Y'),
            'support_email': settings.DEFAULT_FROM_EMAIL,
            'dashboard_url': settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'https://skillsync.com',
        }
        
        # Render HTML email template
        html_message = render_to_string('emails/registration_welcome_email.html', context)
        
        # Send email
        send_mail(
            subject='Welcome to SkillSync! 🎉',
            message=f'Welcome {user.username}! Thank you for joining SkillSync.',  # Fallback plain text
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient_email],
            html_message=html_message,  # Send HTML version
            fail_silently=False,
        )
        
        return True
    
    except Exception as e:
        print(f"Error sending registration welcome email: {str(e)}")
        return False