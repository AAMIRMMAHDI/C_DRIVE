from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upload/', views.upload, name='upload'),
    path('create_folder/', views.create_folder, name='create_folder'),
    path('delete/<int:file_id>/', views.delete_file, name='delete_file'),
    path('delete_folder/<int:folder_id>/', views.delete_folder, name='delete_folder'),
    path('rename/<int:file_id>/', views.rename, name='rename'),
    path('rename_folder/<int:folder_id>/', views.rename_folder, name='rename_folder'),
    path('download_file/<int:file_id>/', views.download_file, name='download_file'),
    path('download/<uuid:token>/', views.download_by_token, name='download_by_token'),
    path('preview/<int:file_id>/', views.preview, name='preview'),
    path('share/<int:file_id>/', views.share, name='share'),
    path('move_file/<int:file_id>/<int:folder_id>/', views.move_file, name='move_file'),
    path('search/', views.search, name='search'),
]