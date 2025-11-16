from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from .forms import registerForm, contentForm, ProfileForm
from .models import Content, Comment, Profile
from django.contrib import messages
from django.http import JsonResponse
from django.contrib.auth.models import User
import json

def home(request):
    contents = Content.objects.all().order_by('-created_at')
    context = {
        'contents': contents,
        'default_avatar': True
    }
    return render(request, 'home.html', context)

def register(request):
    if request.method == 'POST':
        form = registerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
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


@login_required
def delete_comment(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id)

    if request.user != comment.user:
        return JsonResponse({"success": False})

    post = comment.post
    comment.delete()

    return JsonResponse({
        "success": True,
        "post_id": post.id,
        "total_comments": post.comments.count()
    })
