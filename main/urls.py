from django.urls import path
from . import views
from .views import delete_comment, delete_content

urlpatterns = [
    path('', views.landing_page, name='landing'),
    path('home/', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login_user, name='login'),
    path('guest-login/', views.guest_login, name='guest_login'),
    path('logout/', views.logout_user, name='logout'),
    path('add/', views.add_content, name='add_content'),
    path('like/<int:course_id>/', views.like_content, name='like_content'),
    path('add_comment/<int:post_id>/', views.add_comment, name='add_comment'),
    path('delete/<int:course_id>/', delete_content, name='delete_content'),
    path('profile/<str:username>/', views.view_profile, name='view_profile'),
    path('edit-profile/', views.edit_profile, name='edit_profile'),
    path('about/', views.about, name='about'),
    path('search/', views.search, name='search'),
    path('comment/delete/<int:comment_id>/', delete_comment, name='delete_comment'),
    path('content/<int:content_id>/', views.content_detail, name='content_detail'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-otp/<int:user_id>/', views.verify_otp, name='verify_otp'),
    path('reset-password/<int:user_id>/', views.reset_password, name='reset_password'),
]