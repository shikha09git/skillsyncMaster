from django.urls import path
from . import views

urlpatterns = [
    # Public Pages
    path('', views.landing_page, name='landing'),
    path('home/', views.home, name='home'),
    path('about/', views.about, name='about'),
    path('search/', views.search, name='search'),

    # Authentication
    path('register/', views.register, name='register'),
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    path('guest-login/', views.guest_login, name='guest_login'),

    # Password Reset
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-otp/<int:user_id>/', views.verify_otp, name='verify_otp'),
    path('reset-password/<int:user_id>/', views.reset_password, name='reset_password'),

    # Content
    path('add/', views.add_content, name='add_content'),
    path('content/<int:content_id>/', views.content_detail, name='content_detail'),
    path('content/<int:course_id>/like/', views.like_content, name='like_content'),
    path('content/<int:course_id>/delete/', views.delete_content, name='delete_content'),

    # Comments
    path('content/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('comment/<int:comment_id>/delete/', views.delete_comment, name='delete_comment'),

    # Profile (FIXED: user_id route renamed to avoid conflict)
    path('user/<int:user_id>/', views.profile, name='profile'),
    path('profile/<str:username>/', views.view_profile, name='view_profile'),
    path('profile/<str:username>/dashboard/', views.profile_dashboard, name='profile_dashboard'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),

    # Follow System
    path('follow/<int:user_id>/', views.send_follow_request, name='send_follow_request'),
    path('unfollow/<int:user_id>/', views.unfollow, name='unfollow'),
    path('follow-request/<int:request_id>/accept/', views.accept_request, name='accept_request'),
    path('follow-request/<int:request_id>/reject/', views.reject_request, name='reject_request'),

    # Chat
    path('chats/', views.chat_list, name='chat_list'),
    path('chats/<int:room_id>/', views.chat_detail, name='chat_detail'),
    path('chat/<str:username>/', views.chat_room, name='chat_room'),
    path('chat/start/<int:user_id>/', views.start_chat, name='start_chat'),

    path('change-password/', views.change_password, name='change_password'),

    # Danger zone: delete account
    path('delete-account/', views.delete_account, name='delete_account'),
]