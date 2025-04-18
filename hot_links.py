from pyknights.api import ArknightsAPI
import json

# Specify to get a specific version's hot update assets
asset_version = None

api = ArknightsAPI()
# We piggy-back of the api's request session

resp = api.session.get(api.getHotUpdateListURL(asset_version))
update_list = resp.json()

# Add the url for all the files
for asset in update_list["abInfos"]:
	asset["url"] = api.getHotUpdateAssetURL(asset["name"], asset_version)
for asset in update_list["packInfos"]:
	asset["url"] = api.getHotUpdateAssetURL(asset["name"], asset_version)

# Write it to disk
with open("hot_update_list.json", "w") as f:
	json.dump(update_list, f, indent=4, ensure_ascii=False)