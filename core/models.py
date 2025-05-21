from django.db import models
from django.contrib.auth.models import AbstractUser
import uuid

class CustomUser(AbstractUser):
    storage_limit = models.BigIntegerField(default=8589934592)  # 8GB default
    storage_used = models.BigIntegerField(default=0)

    class Meta:
        verbose_name = 'کاربر'
        verbose_name_plural = 'کاربران'

class Folder(models.Model):
    name = models.CharField(max_length=255)
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='folders')
    parent_folder = models.ForeignKey('self', null=True, blank=True, on_delete=models.CASCADE, related_name='subfolders')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'پوشه'
        verbose_name_plural = 'پوشه‌ها'

class File(models.Model):
    user = models.ForeignKey('CustomUser', on_delete=models.CASCADE, related_name='files')
    folder = models.ForeignKey(Folder, null=True, blank=True, on_delete=models.CASCADE, related_name='files')
    original_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=512)
    size = models.BigIntegerField()
    mime_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'فایل'
        verbose_name_plural = 'فایل‌ها'

class ShareToken(models.Model):
    id = models.BigAutoField(primary_key=True)
    file = models.ForeignKey(File, on_delete=models.CASCADE, related_name='share_tokens')
    token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'توکن اشتراک'
        verbose_name_plural = 'توکن‌های اشتراک'