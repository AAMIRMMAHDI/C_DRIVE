from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpResponse, JsonResponse, FileResponse
from .models import CustomUser, File, Folder, ShareToken
import bcrypt
import os
from django.conf import settings
import mimetypes
import uuid
from django.utils import timezone

def index(request):
    return render(request, 'index.html')

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        if CustomUser.objects.filter(username=username).exists():
            messages.error(request, 'نام کاربری قبلاً ثبت شده است!')
            return redirect('register')
        user = CustomUser(username=username)
        user.set_password(password)
        user.save()
        messages.success(request, 'ثبت‌نام با موفقیت انجام شد!')
        return redirect('login')
    return render(request, 'register.html')

def login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        try:
            user = CustomUser.objects.get(username=username)
            if user.check_password(password):
                request.session['user_id'] = user.id
                request.session['username'] = user.username
                messages.success(request, 'ورود با موفقیت انجام شد!')
                return redirect('dashboard')
            else:
                messages.error(request, 'رمز عبور اشتباه است!')
        except CustomUser.DoesNotExist:
            messages.error(request, 'نام کاربری وجود ندارد!')
        return redirect('login')
    return render(request, 'login.html')

def logout(request):
    request.session.flush()
    messages.success(request, 'با موفقیت خارج شدید!')
    return redirect('login')

def dashboard(request):
    if 'user_id' not in request.session:
        messages.error(request, 'لطفاً ابتدا وارد شوید!')
        return redirect('login')
    user = CustomUser.objects.get(id=request.session['user_id'])
    folder_id = request.GET.get('folder_id')
    sort_by = request.GET.get('sort_by', 'created_at')
    sort_order = request.GET.get('sort_order', 'desc')
    query = request.GET.get('q', '')

    if folder_id:
        try:
            folder = Folder.objects.get(id=folder_id, user=user)
            parent_folder_id = folder.parent_folder_id
            folder_name = folder.name
            files = File.objects.filter(folder=folder)
            folders = Folder.objects.filter(parent_folder=folder)
        except Folder.DoesNotExist:
            messages.error(request, 'پوشه یافت نشد!')
            return redirect('dashboard')
    else:
        files = File.objects.filter(user=user, folder__isnull=True)
        folders = Folder.objects.filter(user=user, parent_folder__isnull=True)
        parent_folder_id = None
        folder_name = None

    if query:
        files = files.filter(original_filename__icontains=query)
        folders = folders.filter(name__icontains=query)

    if sort_by in ['original_filename', 'created_at', 'size']:
        order_prefix = '-' if sort_order == 'desc' else ''
        files = files.order_by(f'{order_prefix}{sort_by}')
        folders = folders.order_by(f'{order_prefix}name')

    # محاسبه درصد فضای استفاده‌شده
    storage_used = user.storage_used / 1048576  # تبدیل به مگابایت
    storage_limit = user.storage_limit / 1048576  # تبدیل به مگابایت
    storage_percentage = (storage_used / storage_limit * 100) if storage_limit > 0 else 0

    # تبدیل اندازه فایل‌ها به مگابایت
    files_with_mb = [
        {
            'id': file.id,
            'original_filename': file.original_filename,
            'size_mb': file.size / 1048576,  # تبدیل به مگابایت
            'created_at': file.created_at,
            'mime_type': file.mime_type,
        }
        for file in files
    ]

    # تعیین آیکون‌های مرتب‌سازی
    sort_icon_name = '↑' if sort_by == 'original_filename' and sort_order == 'asc' else '↓'
    sort_icon_date = '↑' if sort_by == 'created_at' and sort_order == 'asc' else '↓'
    sort_icon_size = '↑' if sort_by == 'size' and sort_order == 'asc' else '↓'

    context = {
        'username': user.username,
        'storage_used': storage_used,
        'storage_limit': storage_limit,
        'storage_percentage': storage_percentage,
        'files': files_with_mb,
        'folders': folders,
        'folder_id': folder_id,
        'parent_folder_id': parent_folder_id,
        'folder_name': folder_name,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'query': query,
        'sort_icon_name': sort_icon_name,
        'sort_icon_date': sort_icon_date,
        'sort_icon_size': sort_icon_size,
    }
    return render(request, 'dashboard.html', context)

def upload(request):
    if 'user_id' not in request.session:
        return redirect('login')
    user = CustomUser.objects.get(id=request.session['user_id'])
    if request.method == 'POST':
        uploaded_file = request.FILES.get('file')
        folder_id = request.POST.get('folder_id')
        folder = Folder.objects.get(id=folder_id, user=user) if folder_id else None
        if uploaded_file:
            file_size = uploaded_file.size
            if user.storage_used + file_size > user.storage_limit:
                messages.error(request, 'فضای کافی ندارید!')
                return redirect('dashboard')
            # تولید نام فایل با UUID
            file_name = f"{uuid.uuid4()}_{uploaded_file.name}"
            file_path = os.path.join(settings.MEDIA_ROOT, file_name)
            # اطمینان از وجود پوشه media
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            # ذخیره فایل
            try:
                with open(file_path, 'wb+') as destination:
                    for chunk in uploaded_file.chunks():
                        destination.write(chunk)
            except Exception as e:
                messages.error(request, f'خطا در ذخیره فایل: {str(e)}')
                return redirect('dashboard')
            mime_type, _ = mimetypes.guess_type(uploaded_file.name)
            file = File(
                user=user,
                folder=folder,
                original_filename=uploaded_file.name,
                file_path=file_path,
                size=file_size,
                mime_type=mime_type or 'application/octet-stream',
            )
            file.save()
            user.storage_used += file_size
            user.save()
            messages.success(request, 'فایل با موفقیت آپلود شد!')
        else:
            messages.error(request, 'هیچ فایلی انتخاب نشده است!')
        return redirect('dashboard')
    return redirect('dashboard')

def create_folder(request):
    if 'user_id' not in request.session:
        return redirect('login')
    user = CustomUser.objects.get(id=request.session['user_id'])
    if request.method == 'POST':
        folder_name = request.POST.get('folder_name')
        parent_folder_id = request.POST.get('parent_folder_id')
        parent_folder = Folder.objects.get(id=parent_folder_id, user=user) if parent_folder_id else None
        if folder_name:
            Folder.objects.create(
                name=folder_name,
                user=user,
                parent_folder=parent_folder,
            )
            messages.success(request, 'پوشه با موفقیت ایجاد شد!')
        else:
            messages.error(request, 'نام پوشه نمی‌تواند خالی باشد!')
        return redirect('dashboard')
    return redirect('dashboard')

def delete_file(request, file_id):
    if 'user_id' not in request.session:
        return redirect('login')
    user = CustomUser.objects.get(id=request.session['user_id'])
    try:
        file = File.objects.get(id=file_id, user=user)
        user.storage_used -= file.size
        user.save()
        if os.path.exists(file.file_path):
            os.remove(file.file_path)
        file.delete()
        messages.success(request, 'فایل با موفقیت حذف شد!')
    except File.DoesNotExist:
        messages.error(request, 'فایل یافت نشد!')
    return redirect('dashboard')

def delete_folder(request, folder_id):
    if 'user_id' not in request.session:
        return redirect('login')
    user = CustomUser.objects.get(id=request.session['user_id'])
    try:
        folder = Folder.objects.get(id=folder_id, user=user)
        for file in folder.files.all():
            user.storage_used -= file.size
            if os.path.exists(file.file_path):
                os.remove(file.file_path)
        user.save()
        folder.delete()
        messages.success(request, 'پوشه با موفقیت حذف شد!')
    except Folder.DoesNotExist:
        messages.error(request, 'پوشه یافت نشد!')
    return redirect('dashboard')

def rename(request, file_id):
    if 'user_id' not in request.session:
        return redirect('login')
    user = CustomUser.objects.get(id=request.session['user_id'])
    if request.method == 'POST':
        new_name = request.POST.get('new_name')
        try:
            file = File.objects.get(id=file_id, user=user)
            if new_name:
                file.original_filename = new_name
                file.save()
                messages.success(request, 'نام فایل با موفقیت تغییر کرد!')
            else:
                messages.error(request, 'نام جدید نمی‌تواند خالی باشد!')
        except File.DoesNotExist:
            messages.error(request, 'فایل یافت نشد!')
    return redirect('dashboard')

def rename_folder(request, folder_id):
    if 'user_id' not in request.session:
        return redirect('login')
    user = CustomUser.objects.get(id=request.session['user_id'])
    if request.method == 'POST':
        new_name = request.POST.get('new_name')
        try:
            folder = Folder.objects.get(id=folder_id, user=user)
            if new_name:
                folder.name = new_name
                folder.save()
                messages.success(request, 'نام پوشه با موفقیت تغییر کرد!')
            else:
                messages.error(request, 'نام جدید نمی‌تواند خالی باشد!')
        except Folder.DoesNotExist:
            messages.error(request, 'پوشه یافت نشد!')
    return redirect('dashboard')

def download_file(request, file_id):
    if 'user_id' not in request.session:
        return redirect('login')
    user = CustomUser.objects.get(id=request.session['user_id'])
    try:
        file = File.objects.get(id=file_id, user=user)
        response = FileResponse(open(file.file_path, 'rb'), as_attachment=True, filename=file.original_filename)
        return response
    except File.DoesNotExist:
        messages.error(request, 'فایل یافت نشد!')
        return redirect('dashboard')

def download_by_token(request, token):
    try:
        share_token = ShareToken.objects.get(token=token)
        file = share_token.file
        response = FileResponse(open(file.file_path, 'rb'), as_attachment=True, filename=file.original_filename)
        return response
    except ShareToken.DoesNotExist:
        return render(request, 'error.html', {'message': 'لینک اشتراک نامعتبر است!'})

def preview(request, file_id):
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'لطفاً ابتدا وارد شوید!'}, status=401)
    user = CustomUser.objects.get(id=request.session['user_id'])
    try:
        file = File.objects.get(id=file_id, user=user)
        return JsonResponse({
            'filename': file.original_filename,
            'url': f'/media/{os.path.basename(file.file_path)}',  # تغییر از /Uploads/ به /media/
            'mime_type': file.mime_type,
        })
    except File.DoesNotExist:
        return JsonResponse({'error': 'فایل یافت نشد!'}, status=404)

def share(request, file_id):
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'لطفاً ابتدا وارد شوید!'}, status=401)
    user = CustomUser.objects.get(id=request.session['user_id'])
    try:
        file = File.objects.get(id=file_id, user=user)
        token = ShareToken.objects.create(file=file)
        share_link = request.build_absolute_uri(f'/download/{token.token}/')
        return JsonResponse({'share_link': share_link})
    except File.DoesNotExist:
        return JsonResponse({'error': 'فایل یافت نشد!'}, status=404)

def move_file(request, file_id, folder_id):
    if 'user_id' not in request.session:
        return JsonResponse({'error': 'لطفاً ابتدا وارد شوید!'}, status=401)
    user = CustomUser.objects.get(id=request.session['user_id'])
    try:
        file = File.objects.get(id=file_id, user=user)
        folder = Folder.objects.get(id=folder_id, user=user)
        file.folder = folder
        file.save()
        return JsonResponse({'message': 'فایل با موفقیت جابه‌جا شد!'})
    except (File.DoesNotExist, Folder.DoesNotExist):
        return JsonResponse({'error': 'فایل یا پوشه یافت نشد!'}, status=404)

def search(request):
    if 'user_id' not in request.session:
        return redirect('login')
    query = request.GET.get('q', '')
    folder_id = request.GET.get('folder_id')
    sort_by = request.GET.get('sort_by', 'created_at')
    sort_order = request.GET.get('sort_order', 'desc')
    user = CustomUser.objects.get(id=request.session['user_id'])
    if folder_id:
        try:
            folder = Folder.objects.get(id=folder_id, user=user)
            files = File.objects.filter(folder=folder, original_filename__icontains=query)
            folders = Folder.objects.filter(parent_folder=folder, name__icontains=query)
            parent_folder_id = folder.parent_folder_id
            folder_name = folder.name
        except Folder.DoesNotExist:
            messages.error(request, 'پوشه یافت نشد!')
            return redirect('dashboard')
    else:
        files = File.objects.filter(user=user, folder__isnull=True, original_filename__icontains=query)
        folders = Folder.objects.filter(user=user, parent_folder__isnull=True, name__icontains=query)
        parent_folder_id = None
        folder_name = None
    if sort_by in ['original_filename', 'created_at', 'size']:
        order_prefix = '-' if sort_order == 'desc' else ''
        files = files.order_by(f'{order_prefix}{sort_by}')
        folders = folders.order_by(f'{order_prefix}name')
    context = {
        'username': user.username,
        'storage_used': user.storage_used / 1048576,  # تبدیل به مگابایت
        'storage_limit': user.storage_limit / 1048576,  # تبدیل به مگابایت
        'files': files,
        'folders': folders,
        'folder_id': folder_id,
        'parent_folder_id': parent_folder_id,
        'folder_name': folder_name,
        'sort_by': sort_by,
        'sort_order': sort_order,
        'query': query,
    }
    return render(request, 'dashboard.html', context)