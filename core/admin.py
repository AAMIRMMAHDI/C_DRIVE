from django.contrib import admin
from .models import CustomUser, File, Folder, ShareToken

admin.site.register(CustomUser)
admin.site.register(File)
admin.site.register(Folder)
admin.site.register(ShareToken)