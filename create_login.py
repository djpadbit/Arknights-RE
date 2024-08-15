from pyknights.api import ArknightsAPI
import json,sys

if len(sys.argv) < 3:
	print("Usage:")
	print(f"\t{sys.argv[0]} <YostarEmail> <deviceId>")
	exit()

email = sys.argv[1]
deviceId = sys.argv[2]

userAgent = "Dalvik/2.1.0 (Linux; U; Android 7.1.2; SM-G965N Build/QP1A.190711.020)"

api = ArknightsAPI(userAgent)

print("Requesting code...")
api.yostarRequestLogin(email)
code = int(input("Enter the code : "))
creds = api.yostarCreateLogin(email, code, deviceId)
creds["userAgent"] = userAgent

with open("creds.json",'w',encoding="utf-8") as f:
	json.dump(creds,f,indent=4)

print("Created creds.json with login info")