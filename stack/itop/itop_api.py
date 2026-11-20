#!/usr/bin/env python3
"""Petit client REST iTop : lit le jeton dans secrets/api_token (jamais affiche)."""
import json, sys, urllib.request, urllib.parse
URL = "https://itsm.e-delmotte.fr/webservices/rest.php?version=1.3"
TOKEN = open("/opt/stack/itop/secrets/api_token").read().strip()
def call(op):
    data = urllib.parse.urlencode({"json_data": json.dumps(op)}).encode()
    req = urllib.request.Request(URL, data=data, headers={"Auth-Token": TOKEN})
    return json.load(urllib.request.urlopen(req, timeout=60))
if __name__ == "__main__":
    print(json.dumps(call(json.loads(sys.stdin.read())), ensure_ascii=False)[:3000])
