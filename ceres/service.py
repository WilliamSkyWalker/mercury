import requests
import json
def make_request(method,url, headers, params, body, auth,public_params):
    url = replace_placeholders(url,public_params)
    headers = replace_placeholders(headers,public_params)
    params = replace_placeholders(params,public_params)
    body = replace_placeholders(body,public_params)
    auth = replace_placeholders(auth,public_params)
    if method not in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
        raise ValueError("Invalid method")
    headers = json.loads(headers)
    for key in list(headers.keys()):
        if headers[key] is None:
            del headers[key]
    response = requests.request(method, url, headers=headers, params=params, data=body, auth=auth)
    return response
def replace_placeholders(text,public_params):
    for key, value in public_params.items():
        text = text.replace(f"{{{{{key}}}}}", str(value))
    return text

class Script:
    def __init__(self, script,type,global_params):
        self.script = script
        self.type = type
        self.global_params = global_params
    def run_script(self):
        if self.type == "python":
            global_params = self.global_params
            exec(self.script)

    def get_global_params(self):
        return self.global_params


