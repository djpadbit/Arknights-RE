from pyknights.api import ArknightsAPI
import json,sys

if len(sys.argv) < 2:
	print("Usage: [] is optional")
	print(f"\t{sys.argv[0]} <YostarEmail> [deviceId]")
	exit()

email = sys.argv[1]
deviceId = ArknightsAPI.generateDeviceId() if len(sys.argv) == 2 else sys.argv[2]

api = ArknightsAPI(deviceId)

print("Requesting code...")
api.yostarRequestLogin(email)
code = int(input("Enter the code : "))
creds = api.yostarCreateLogin(email, code)
creds["userAgent"] = api.getUserAgent()

with open("creds.json",'w',encoding="utf-8") as f:
	json.dump(creds,f,indent=4)

print("Created creds.json with login info")