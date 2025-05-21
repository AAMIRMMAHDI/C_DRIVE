import os
import zipfile
from io import BytesIO
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth import authenticate, login
from .models import FileItem, UserProfile
from django.core.exceptions import ValidationError
import json

def login_view(request):
    if request.user.is_authenticated:
        return redirect('/files/')
    if request.method == 'POST':
        username = request.POST.get('login')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('/files/')
        else:
            return render(request, 'account/login.html', {'error': 'نام کاربری یا رمز عبور اشتباه است.'})
    return render(request, 'account/login.html')

@login_required
@require_GET
def dashboard_api(request):
    user_profile = UserProfile.objects.get_or_create(user=request.user)[0]
    parent_id = request.GET.get('parent_id')
    if parent_id:
        parent = get_object_or_404(FileItem, id=parent_id, user=request.user, item_type='folder')
        items = FileItem.objects.filter(user=request.user, parent=parent)
    else:
        items = FileItem.objects.filter(user=request.user, parent__isnull=True)
    items_data = [
        {
            'id': item.id,
            'name': item.name,
            'type': item.item_type,
            'size': item.size,
            'created_at': item.created_at.isoformat()
        } for item in items
    ]
    data = {
        'items': items_data,
        'storage_used': user_profile.storage_used,
        'storage_limit': user_profile.storage_limit,
        'parent_id': parent_id if parent_id else None
    }
    return JsonResponse(data)

@login_required
@require_POST
def upload_file_api(request):
    user_profile = UserProfile.objects.get(user=request.user)
    file = request.FILES.get('file')
    parent_id = request.POST.get('parent_id')
    parent = FileItem.objects.get(id=parent_id) if parent_id else None

    if not file:
        return JsonResponse({'error': 'No file provided'}, status=400)

    file_size = file.size
    if user_profile.storage_used + file_size > user_profile.storage_limit:
        return JsonResponse({'error': 'Storage limit exceeded'}, status=400)

    try:
        file_item = FileItem(
            user=request.user,
            name=file.name,
            item_type='file',
            file=file,
            parent=parent,
            size=file_size
        )
        file_item.save()
        user_profile.storage_used += file_size
        user_profile.save()
        return JsonResponse({'message': 'File uploaded successfully', 'id': file_item.id})
    except ValidationError as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_POST
def create_folder_api(request):
    try:
        data = json.loads(request.body)
        name = data.get('folder_name')
        parent_id = data.get('parent_id')
        parent = FileItem.objects.get(id=parent_id) if parent_id else None

        if not name:
            return JsonResponse({'error': 'Folder name is required'}, status=400)

        FileItem.objects.create(
            user=request.user,
            name=name,
            item_type='folder',
            parent=parent
        )
        return JsonResponse({'message': 'Folder created successfully'})
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

@login_required
@require_POST
def delete_item_api(request, item_id):
    item = get_object_or_404(FileItem, id=item_id, user=request.user)
    try:
        if item.item_type == 'file':
            user_profile = UserProfile.objects.get(user=request.user)
            user_profile.storage_used -= item.size
            user_profile.save()
        item.delete()
        return JsonResponse({'message': 'Item deleted successfully'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_GET
def download_item_api(request, item_id):
    item = get_object_or_404(FileItem, id=item_id, user=request.user)
    
    if item.item_type == 'file':
        response = HttpResponse(item.file, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{item.name}"'
        return response
    else:
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_item in item.children.all():
                if file_item.item_type == 'file':
                    file_path = file_item.file.path
                    zip_file.write(file_path, file_item.name)
        
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{item.name}.zip"'
        return response

@login_required
@require_POST
def move_item_api(request):
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        folder_id = data.get('folder_id')
        item = get_object_or_404(FileItem, id=item_id, user=request.user)
        folder = get_object_or_404(FileItem, id=folder_id, user=request.user, item_type='folder')
        item.parent = folder
        item.save()
        return JsonResponse({'message': 'Item moved successfully'})
    except (json.JSONDecodeError, ValidationError) as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
@require_POST
def rename_item_api(request):
    try:
        data = json.loads(request.body)
        item_id = data.get('item_id')
        new_name = data.get('new_name')
        item = get_object_or_404(FileItem, id=item_id, user=request.user)
        if not new_name:
            return JsonResponse({'error': 'New name is required'}, status=400)
        item.name = new_name
        item.save()
        return JsonResponse({'message': 'Item renamed successfully'})
    except (json.JSONDecodeError, ValidationError) as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def dashboard(request):
    return render(request, 'files/dashboard.html')