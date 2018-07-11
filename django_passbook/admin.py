from django.contrib import admin
from django_passbook.models import Pass, Registration, Log
from django_passbook import settings
from apns3 import APNs, Payload


def push_update(modeladmin, request, queryset):
    for r in queryset.all():
        # FIXME: use different certificates for different stores
        apns = APNs(use_sandbox=False,
                    cert_file=settings.PASSBOOK_CERT,
                    key_file=settings.PASSBOOK_CERT_KEY)
        apns.gateway_server.send_notification(r.push_token, Payload())


push_update.short_description = "Send a push notification to update Pass"


@admin.register(Registration)
class RegistrationAdmin(admin.ModelAdmin):
    list_display = ('device_library_identifier', 'push_token', 'pazz')
    actions = [push_update]


@admin.register(Pass)
class PassAdmin(admin.ModelAdmin):
    list_display = (
        'serial_number', 'pass_type_identifier', 'authentication_token',
        'updated_at',
    )


@admin.register(Log)
class LogAdmin(admin.ModelAdmin):
    list_display = ('message',)
