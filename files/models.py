from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    storage_limit = models.BigIntegerField(default=2 * 1024 * 1024 * 1024)  # 2GB in bytes
    storage_used = models.BigIntegerField(default=0)

    def __str__(self):
        return self.user.username

class FileItem(models.Model):
    ITEM_TYPES = (
        ('file', 'File'),
        ('folder', 'Folder'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    item_type = models.CharField(max_length=10, choices=ITEM_TYPES)
    file = models.FileField(upload_to='user_files/%Y/%m/%d/', null=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    created_at = models.DateTimeField(auto_now_add=True)
    size = models.BigIntegerField(default=0)

    def clean(self):
        if self.item_type == 'file' and not self.file:
            raise ValidationError('File is required for file type.')
        if self.item_type == 'folder' and self.file:
            raise ValidationError('Folders cannot have files.')

    def __str__(self):
        return f"{self.name} ({self.item_type})"