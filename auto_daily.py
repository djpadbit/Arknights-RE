from pyknights.api import ArknightsAPI
import json

# User defined stuff
friendUid = None
annihilationStage = "camp_01"
annihilationStageCost = 20
creditThreshold = 200
# For all recruitment data see
# https://github.com/Dimbreath/ArknightsData/blob/master/en-US/gamedata/excel/gacha_table.json
# key gachaTags for the tags
# key specialTagRarityTable for the special tags and prob
# key recruitPool for recruitment times (in minutes) and lmd prices
recruitmentTagsPref = [11,14,27,25,26,21,15,4,7,19,18,1]
# Very primitive system, just takes the n first tags in the list
recruitmentTagsNumber = 1
recruitmentDuration = 540*60 # 9h

# Constants
recruitmentTagsSpecial = [11,14]

try:
	with open("creds.json",'r',encoding="utf-8") as f:
		creds = json.load(f)
	if "userAgent" not in creds or "uid" not in creds or "deviceId" not in creds or "token" not in creds:
		raise ValueError()
except:
	print("No login data, check creds.json, you might need to run create_login.py")
	exit()

api = ArknightsAPI(creds["userAgent"])
api.login(creds["uid"],creds["token"],creds["deviceId"])
print("Syncing data")
gamedat = api.syncData()
with open("data1.json",'w',encoding="utf-8") as f:
	json.dump(api.getPlayerData(),f,indent=4)

origPay = gamedat['status']['payDiamond']
origFree = gamedat['status']['freeDiamond']
print(f"Logged in as {gamedat['status']['nickName']}#{gamedat['status']['nickNumber']} ({gamedat['status']['uid']}) at {api.getLoginTs()}")
print(f"Level {gamedat['status']['level']} with {gamedat['status']['exp']} exp")
print(f"Sanity {gamedat['status']['ap']}/{gamedat['status']['maxAp']}")
print(f"{origPay+origFree} Originite Prime ({origFree} Free, {origPay} Paid)")
print(f"{gamedat['status']['gold']} LMD, {gamedat['status']['diamondShard']} Orundum, {gamedat['status']['socialPoint']} Credits")

if gamedat["checkIn"]["canCheckIn"]:
	print("Checking in")
	print(api.getDailyRewards())

if gamedat["social"]["yesterdayReward"]["canReceive"]:
	print("Getting daily credits")
	print(api.getSocialCredit())

print("Getting mails")
mails = []
sysMails = []
metaMails = api.getMailMetaList()
print(metaMails)
for mail in metaMails["result"]:
	if mail["state"] == 0: # Mail is not collected
		if mail["type"] == 0:
			mails.append(mail["mailId"])
		else:
			sysMails.append(mail["mailId"])

if len(mails) > 0 or len(sysMails) > 0:
	print("Reading mails")
	print(api.getMails(mails,sysMails))
	print("Collecting mails")
	print(api.collectMails(mails,sysMails))
	#print("Deleting the mails")
	#print(api.deleteMails(mails,sysMails))

print("Syncing RIIC")
api.syncRIIC()
gamedat = api.getPlayerData()

types = []
clues = []
dailyClue = None
for room,data in gamedat["building"]["rooms"]["MEETING"].items():
	for val,type in enumerate(["daily","search"]):
		if data["socialReward"][type] > 0 and val not in types:
			types.append(val)
		for clue in data["ownStock"]:
			if clue["id"] not in clues:
				clues.append(clue["id"])
		if data["dailyReward"] is not None:
			dailyClue = data["dailyReward"]["id"]
if len(types) > 0:
	print("Getting Meeting Room credits")
	print(api.getMeetingReward(types))
if len(clues) > 0 and friendUid:
	print(f"Sending all {len(clues)} clues to friend")
	for idx in range(len(clues)):
		#print(clues)
		clue = clues[0]
		clues.remove(clues[0])
		print(api.sendClue(clue,friendUid))
if dailyClue is not None:
	print("Getting daily clue")
	if len(clues) < 10:
		print(api.getDailyClue())
		if friendUid:
			print("Sending it to friend")
			print(api.sendClue(dailyClue,friendUid))
	else:
		print("Too many clues")

print("Getting all trust")
print(api.getAllIntimacy())

print("Getting friend list")
friends = api.getFriendList()
print(friends)
for friend in friends["result"]:
	print(f"Visiting {friend['uid']}")
	api.visitFriend(friend["uid"])

gamedat = api.getPlayerData()

credits = gamedat["status"]["socialPoint"]
if credits > creditThreshold:
	print(f"Too much credits ({credits}), buying some stuff")
	socialGoods = api.getSocialGoodList()
	print(socialGoods)
	items = sorted(socialGoods["goodList"],key=lambda x:x["discount"],reverse=True)
	for purchased in gamedat["shop"]["SOCIAL"]["info"]:
		if purchased["count"] < 1:
			continue
		for item in items.copy():
			if purchased["id"] == item["goodId"]:
				items.remove(item)
	for item in items.copy():
		if item["item"]["type"] == "CHAR":
			items.remove(item)
			items.insert(0, item)
	while credits > creditThreshold:
		if len(items) < 1:
			print("No more items to buy")
			break
		currentItem = items[0]
		items.remove(currentItem)
		if currentItem["price"] > credits:
			continue
		print(f"Buying {currentItem['displayName']} for {currentItem['price']} (discounted at {currentItem['discount']*100}%)")
		print(api.buySocialGood(currentItem["goodId"]))
		credits -= currentItem['price']

gamedat = api.getPlayerData()

factories = []
for room,data in gamedat["building"]["rooms"]["MANUFACTURE"].items():
	if data["outputSolutionCnt"] > 0:
		factories.append(room)
if len(factories) > 0:
	print("Settling factories")
	print(api.settleFactory(factories))

tradingposts = []
for room,data in gamedat["building"]["rooms"]["TRADING"].items():
	if len(data["stock"]) > 0:
		tradingposts.append(room)
if len(tradingposts) > 0:
	print("Delivering trading post orders")
	print(api.deliverOrders(tradingposts))

print(api.syncRecruitment())
gamedat = api.getPlayerData()

print("Doing Recruitment")
for slotId,slotData in gamedat["recruit"]["normal"]["slots"].items():
	slotId = int(slotId)
	state = slotData["state"]
	currentTs = api.getCurrentTs()
	if state == 0: # Locked slot
		continue

	if state == 2 and slotData["realFinishTs"] > currentTs: # In progress slot
		continue

	if (state == 3 or state == 2) and slotData["realFinishTs"] <= currentTs: # state 3 -> Forced finished slot else normally finished
		print(f"Finishing recruitment on slot {slotId}")
		print(api.finishRecruitment(slotId))
		gamedat = api.getPlayerData()
		slotData = gamedat["recruit"]["normal"]["slots"][str(slotId)]
		state = 1

	if state == 1 and gamedat["status"]["recruitLicense"] > 0: # Open slot and has recruitment permits
		specialTag = -1
		tags = []
		nbTags = 0
		for tag in recruitmentTagsPref:
			if tag in slotData["tags"]:
				if tag in recruitmentTagsSpecial:
					if specialTag == -1:
						specialTag = tag
						nbTags += 1
					continue
				tags.append(tag)
				nbTags += 1
			if nbTags >= recruitmentTagsNumber:
				break
		print(f"Starting recruitment on slot {slotId} with tags {tags} for {recruitmentDuration} seconds")
		print(api.startRecruitment(slotId,recruitmentDuration,tags,specialTag))

# Annihilation stuff
# Find out if we have PRTS Proxy cards
if annihilationStage and "EXTERMINATION_AGENT" in gamedat["consumable"]:
	cards = []
	for sId in gamedat["consumable"]["EXTERMINATION_AGENT"]:
		item = gamedat["consumable"]["EXTERMINATION_AGENT"][sId]
		if item["count"] > 0:
			cards.append((int(sId),item["ts"]))
	print(f"Got {len(cards)} PRTS Proxy Annihilation cards")
	# Put the card that is going to expire the earliest at the end of the list, so we can pop it
	cards.sort(key=lambda x:x[1],reverse=True)
	# We continue doing Annihilation until we don't have anymore cards or we have max orundum or we don't have anymore sanity
	while len(cards) > 0 and gamedat["campaignsV2"]["campaignCurrentFee"] < gamedat["campaignsV2"]["campaignTotalFee"] and gamedat["status"]["ap"] >= annihilationStageCost:
		card = cards.pop()
		print(f"Doing PRTS Proxy Annihilation with ({card[0]},ts:{card[1]}), {gamedat['campaignsV2']['campaignCurrentFee']}/{gamedat['campaignsV2']['campaignTotalFee']}")
		print(api.doBattleSweep(card[0],"EXTERMINATION_AGENT",annihilationStage))

for i in ["MAIN","WEEKLY","DAILY"]:
	print(f"Confirming {i} missions")
	print(api.autoConfirmMissions(i))

with open("data2.json",'w',encoding="utf-8") as f:
	json.dump(api.getPlayerData(),f,indent=4)