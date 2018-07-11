from datetime import datetime
import json

import django.dispatch
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import condition
from django_passbook.models import Pass, Registration, Log
from django.shortcuts import get_object_or_404
from django.db.models import Max


FORMAT = '%Y-%m-%d %H:%M:%S'
pass_registered = django.dispatch.Signal()
pass_unregistered = django.dispatch.Signal()

# ability to provide custom Pass model retrieval method
# must be empty/ommited or 'mypackage.mymodule.myfunc'
getpass_proc = getattr(settings, 'PASSBOOK_GET_PASS_PROCEDURE', None)
if getpass_proc:
    import importlib
    mod_name, func_name = getpass_proc.rsplit('.', 1)
    mod = importlib.import_module(mod_name)
    getpass_proc = getattr(mod, func_name)


# ability to provide custom Pass rendering method
renderpass_proc = getattr(settings, 'PASSBOOK_RENDER_PASS_PROCEDURE', None)
if renderpass_proc:
    import importlib
    mod_name, func_name = renderpass_proc.rsplit('.', 1)
    mod = importlib.import_module(mod_name)
    renderpass_proc = getattr(mod, func_name)


def registrations(request, device_library_id, pass_type_id):
    """
    Gets the Serial Numbers for Passes Associated with a Device
    """
    passes = Pass.objects.filter(
        registration__device_library_identifier=device_library_id,
        pass_type_identifier=pass_type_id
    )
    if passes.count() == 0:
        return HttpResponse(status=404)

    if 'passesUpdatedSince' in request.GET:
        passes = passes.filter(updated_at__gt=datetime.strptime(
            request.GET['passesUpdatedSince'], FORMAT))

    if passes:
        last_updated = passes.aggregate(Max('updated_at'))['updated_at__max']
        serial_numbers = [
            p.serial_number for p in passes.filter(
                updated_at=last_updated
            ).all()
        ]
        response_data = {'lastUpdated': last_updated.strftime(
            FORMAT), 'serialNumbers': serial_numbers}
        return HttpResponse(
            json.dumps(response_data),
            content_type="application/json"
        )
    else:
        return HttpResponse(status=204)


@csrf_exempt
def register_pass(request, device_library_id, pass_type_id, serial_number):
    """
    Registers/Unregisters a Device to Receive Push Notifications for a Pass
    """
    pass_ = get_pass(pass_type_id, serial_number)

    if request.META.get(
        'HTTP_AUTHORIZATION'
    ) != 'ApplePass %s' % pass_.authentication_token:
        return HttpResponse('ApplePass auth must be used', status=401)

    registration = Registration.objects.filter(
        device_library_identifier=device_library_id,
        pazz=pass_)

    if request.method == 'POST':
        if registration:
            return HttpResponse(status=200)
        body = json.loads(request.body)
        new_registration = Registration(
            device_library_identifier=device_library_id,
            push_token=body['pushToken'],
            pazz=pass_)
        new_registration.save()
        pass_registered.send(sender=pass_)
        return HttpResponse(status=201)

    elif request.method == 'DELETE':
        registration.delete()
        pass_unregistered.send(sender=pass_)
        return HttpResponse(status=200)

    else:
        return HttpResponse(status=400)


def latest_pass(request, pass_type_id, serial_number):
    return get_pass(pass_type_id, serial_number).updated_at


@condition(last_modified_func=latest_pass)
def latest_version(request, pass_type_id, serial_number):
    """
    Gets the latest version of a Pass
    """
    pass_ = get_pass(pass_type_id, serial_number)

    if request.META.get(
        'HTTP_AUTHORIZATION'
    ) != 'ApplePass %s' % pass_.authentication_token:
        return HttpResponse(status=401)

    response = HttpResponse(
        render_pass_data(pass_),
        content_type='application/vnd.apple.pkpass'
    )
    response['Content-Disposition'] = 'attachment; filename=pass.pkpass'
    return response


@csrf_exempt
def log(request):
    """
    Logs messages from devices
    """
    b = json.loads(request.body)
    for m in b['logs']:
        Log(message=m).save()
    return HttpResponse(status=200)


def get_pass(pass_type_id, serial_number):
    if getpass_proc:
        return getpass_proc(pass_type_id, serial_number)
    else:
        return get_object_or_404(
            Pass,
            pass_type_identifier=pass_type_id,
            serial_number=serial_number
        )


def render_pass_data(pass_):
    if renderpass_proc:
        return renderpass_proc(pass_)
    else:
        return pass_.data.read()
