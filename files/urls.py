from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('', views.dashboard, name='dashboard'),
    path('api/', views.dashboard_api, name='dashboard_api'),
    path('api/upload/', views.upload_file_api, name='upload_file_api'),
    path('api/create_folder/', views.create_folder_api, name='create_folder_api'),
    path('api/delete/<int:item_id>/', views.delete_item_api, name='delete_item_api'),
    path('api/download/<int:item_id>/', views.download_item_api, name='download_item_api'),
    path('api/move/', views.move_item_api, name='move_item_api'),
    path('api/rename/', views.rename_item_api, name='rename_item_api'),
]