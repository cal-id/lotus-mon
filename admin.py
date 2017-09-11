from django.contrib import admin
from monitor.models import (GangliaGraph, CrashEvent, User, Host, Command,
                            Queue)

# Register your models here.
admin.site.register(CrashEvent)
admin.site.register(GangliaGraph)
admin.site.register(User)
admin.site.register(Host)
admin.site.register(Command)
admin.site.register(Queue)
