from django.http import HttpResponse
import json

def success_response(data,message=""):
    result = {
        "status": 200,
        "message": message,
        "data": data
    }

    return HttpResponse(json.dumps(result), content_type="application/json")

def failed_response(message="",code=500):
    result = {
        "status": code,
        "message": message
    }
    return HttpResponse(json.dumps(result), content_type="application/json")