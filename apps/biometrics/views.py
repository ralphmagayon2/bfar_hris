# apps/biometrics/views.py
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

def devices(request):
    return render(request, 'biometrics/devices.html')

@csrf_exempt
def receive_push(request):
    if request.method == "POST":
        data = json.loads(request.body)
        print("Received biometric log:", data)
        return JsonResponse({"status": "ok"})
    return JsonResponse({"error": "POST required"}, status=405)

def status(request):
    return JsonResponse({
        "online": True
    })