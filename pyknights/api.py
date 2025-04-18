import requests,json,hmac,uuid,hashlib
import collections.abc
from datetime import datetime,timezone

# Used to debug using mitmproxy
#GLOBAL_PROXIES = {"http":"http://localhost:8080","https":"https://localhost:8080"}
#GLOBAL_SSL_VERIFY = False
GLOBAL_PROXIES = {}
GLOBAL_SSL_VERIFY = True

if GLOBAL_SSL_VERIFY is False:
	import urllib3
	urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Dict to JSON without spaces
def minJson(data,**kwargs):
	return json.dumps(data,separators=(',',':'),**kwargs)

class AiriSDKAPI:
	YOSTAR_API_BASE = "https://en-sdk-api.yostarplat.com/"
	YOSTAR_SDK_VERSION = "4.10.0"
	MD5_KEY = b"886c085e4a8d30a703367b120dd8353948405ec2"
	USER_AGENT = "okhttp/3.12.13"

	def __init__(self, deviceId, platform, channel, pid, language, versionCode):
		self.session = requests.Session()
		self.session.proxies = GLOBAL_PROXIES
		self.session.verify = GLOBAL_SSL_VERIFY
		self.session.headers["Accept-Encoding"] = "gzip"
		self.session.headers["User-Agent"] = AiriSDKAPI.USER_AGENT
		self.baseURL = AiriSDKAPI.YOSTAR_API_BASE
		self.deviceModel = "Emulator"
		self.platform = platform
		self.channel = channel
		self.versionCode = versionCode
		self.language = language
		self.pid = pid
		self.deviceId = deviceId
		self.token = None
		self.uid = None
		self.oldUid = None

	def setDeviceModel(self, deviceModel):
		self.deviceModel = deviceModel

	def _makeAuthHeader(self, pid, uid, token, padding):
		head = {}
		head["PID"] = pid
		head["Channel"] = self.channel
		head["Platform"] = self.platform
		head["Version"] = AiriSDKAPI.YOSTAR_SDK_VERSION
		head["GVersionNo"] = self.versionCode
		head["GBuildNo"] = ""
		head["Lang"] = self.language
		head["DeviceID"] = self.deviceId
		head["DeviceModel"] = self.deviceModel
		head["UID"] = uid
		head["Token"] = token
		head["Time"] = ArknightsAPI.getCurrentTs()

		headStr = minJson(head).encode("utf-8")
		if isinstance(padding, str):
			padding = padding.encode("utf-8")
		md5 = hashlib.md5(headStr + padding + AiriSDKAPI.MD5_KEY).hexdigest().upper()

		return minJson({"Head": head, "Sign": md5})

	def _doPost(self, endpoint, data):
		data = minJson(data,allow_nan=False).encode("utf-8")
		hdrs = {"Content-Type": "application/json", "Authorization": self._makeAuthHeader(self.pid, self.uid or "", self.token or "", data)}
		return self.session.post(self.baseURL + endpoint, data, headers=hdrs)

	def _checkResult(self, data):
		if "Code" not in data or "Msg" not in data or "Data" not in data:
			return None, "No Code,Msg or Data in data"
		code = data["Code"]
		msg = data["Msg"]

		if code == 200:
			return data["Data"],None

		return data["Data"],msg + f" ({code})"

	# Long login only, didn't implement quick login
	# Quick login uses the UID & Token in the Auth header
	def login(self, uid, token, account):
		postData = {
			"CheckAccount": 0,
			"Geetest": {"CaptchaID": None,"CaptchaOutput": None,"GenTime": None,"LotNumber": None,"PassToken": None},
			"OpenID": uid,
			"Secret": "",
			"Token": token,
			"Type": "yostar",
			"UserName": account
		}

		resp = self._doPost("/user/login",postData)
		if resp.status_code != 200:
			raise RuntimeError(f"AiriSDK Login failed: POST status is {resp.status_code}")
		data,res = self._checkResult(resp.json())
		if res:
			raise RuntimeError(f"AiriSDK Login failed: {res}")
		if "UserInfo" not in data or "Token" not in data["UserInfo"] or "ID" not in data["UserInfo"] or "UID2" not in data["UserInfo"]:
			raise ValueError("AiriSDK Login failed: No Token or ID or UID2")

		self.token = data["UserInfo"]["Token"]
		self.uid = data["UserInfo"]["ID"]
		self.oldUid = data["UserInfo"]["UID2"]

		print(f"AiriSDK Token: {self.token}")
		print(f"AiriSDK UID: {self.uid}")
		print(f"AiriSDK Old UID: {self.oldUid}")

	def yostarAuthRequest(self, email):
		postData = {"Account":email, "Randstr": "", "Ticket": ""}
		resp = self._doPost("/yostar/send-code",postData)
		if resp.status_code != 200:
			raise RuntimeError(f"AiriSDK Yostar Auth Request failed: POST status is {resp.status_code}")
		data,res = self._checkResult(resp.json())
		if res:
			raise RuntimeError(f"AiriSDK Yostar Auth Request failed: {res}")

		return data

	def yostarGetAuth(self, email, code):
		postData = {"Account": email, "Code": str(code)}
		resp = self._doPost("/yostar/get-auth",postData)
		if resp.status_code != 200:
			raise RuntimeError(f"AiriSDK Yostar Auth failed: POST status is {resp.status_code}")
		data,res = self._checkResult(resp.json())
		if res:
			raise RuntimeError(f"AiriSDK Yostar Auth failed: {res}")
		if "Account" not in data or "Token" not in data or "UID" not in data:
			raise ValueError("AiriSDK Yostar Auth failed: No account or token or uid")

		print(f"Yostar Account: {data['Account']}")
		print(f"Yostar Token: {data['Token']}")
		print(f"Yostar UID: {data['UID']}")
		return data

class U8SDKAPI:
	# Full credit to https://github.com/Tao0Lu/Arknights_Checkin for the key
	HAMC_KEY = b"91240f70c09a08a6bc72af1a5c8d4670"

	def __init__(self, userAgent, unityVersion, baseURL, appId, channelId, subChannel, worldId, platformId):
		self.session = requests.Session()
		self.session.proxies = GLOBAL_PROXIES
		self.session.verify = GLOBAL_SSL_VERIFY
		self.session.headers["User-Agent"] = userAgent
		self.session.headers["X-Unity-Version"] = unityVersion
		self.baseURL = baseURL
		self.appId = appId
		self.channelId = channelId
		self.subChannel = subChannel
		self.worldId = worldId
		self.platformId = platformId
		self.token = None
		self.uid = None

	def _checkResult(self, data):
		if "result" not in data:
			return "no result in data"
		res = data["result"]
		del data["result"]
		if res == 0:
			return None
		if "error" in data:
			errorstr = data["error"]
			del data["error"]
			return f"{errorstr} ({res})"
		else:
			return f"result is {res}"

	# Data needs to be in the right order, seems to be sorted but idk
	def _sign(self, data):
		encoded = ""
		for key,value in data.items():
			encoded += f"&{key}={value}"
		return hmac.digest(U8SDKAPI.HAMC_KEY, encoded[1:].encode("utf-8"), "sha1").hex()

	def login(self, accessToken, uid, oldUid, deviceId, deviceId2="", deviceId3=""):
		extensionData = {"type":1,"uid":uid,"old_uid":str(oldUid),"token":accessToken}
		postData = {
			"appId":str(self.appId),
			"channelId":str(self.channelId),
			"extension":minJson(extensionData),
			"worldId":str(self.worldId),
			"platform":self.platformId,
			"subChannel":str(self.subChannel),
			"deviceId":deviceId,
			"deviceId2":deviceId2,
			"deviceId3":deviceId3
		}
		postData["sign"] = self._sign(postData)
		resp = self.session.post(self.baseURL+"/user/v1/getToken",json=postData)
		if resp.status_code != 200:
			raise RuntimeError(f"U8 Token failed: POST status is {resp.status_code}")
		data = resp.json()
		res = self._checkResult(data)
		if res:
			raise RuntimeError(f"U8 Token failed: {res}")
		if "token" not in data or "uid" not in data:
			raise ValueError("U8 Token failed: No token or UID")
		self.token = data["token"]
		self.uid = data["uid"]
		print(f"U8 Token: {self.token}")
		print(f"UID: {self.uid}")

class ArknightsAPI:
	PASSPORT_BASE = "https://passport.arknights.global"
	NETCONFIG_URL = "https://ak-conf.arknights.global/config/prod/official/network_config"
	UNITY_VERSION = "2017.4.39f1"
	PLATFORM = "Android"
	PLATFORM_ID = 1
	APP_ID = 1
	CHANNEL = "googleplay"
	CHANNEL_ID = 3
	SUB_CHANNEL = 3
	WORLD_ID = 3

	YOSTAR_SDK_PID = "US-ARKNIGHTS"
	YOSTAR_SDK_LANGUAGE = "en"
	# 1000112 is for 28.4.01
	# Idealy scrape from something like apk-pure or use the playstore api
	# Don't know if being wrong affects the ability to log in
	PACKAGE_VERSIONCODE = "1000112"

	def __init__(self, deviceId=None, userAgent="Dalvik/2.1.0 (Linux; U; Android 7.1.2; SM-G965N Build/QP1A.190711.020)"):
		self.session = requests.Session()
		self.session.proxies = GLOBAL_PROXIES
		self.session.verify = GLOBAL_SSL_VERIFY
		self.session.headers["User-Agent"] = userAgent
		self.session.headers["X-Unity-Version"] = ArknightsAPI.UNITY_VERSION
		self.session.headers["Accept-Encoding"] = "gzip"
		self._fetchNetworkConfig()
		self._fetchABVersion()
		self.deviceId = deviceId if deviceId is not None else self.generateDeviceId()
		print(f"DeviceId: {self.deviceId}")
		self.airiSDK = AiriSDKAPI(deviceId, ArknightsAPI.PLATFORM.lower(), ArknightsAPI.CHANNEL, ArknightsAPI.YOSTAR_SDK_PID,
							ArknightsAPI.YOSTAR_SDK_LANGUAGE, ArknightsAPI.PACKAGE_VERSIONCODE)
		self.u8SDK = U8SDKAPI(userAgent, ArknightsAPI.UNITY_VERSION, self.u8sdk_base, ArknightsAPI.APP_ID,
							ArknightsAPI.CHANNEL_ID, ArknightsAPI.SUB_CHANNEL, ArknightsAPI.WORLD_ID, ArknightsAPI.PLATFORM_ID)
		self.seqnum = 0
		self.playerData = {}
		self.secret = None
		self.uid = None

	def getDeviceId(self):
		return self.deviceId

	def getUserAgent(self):
		return self.session.headers["User-Agent"]

	@staticmethod
	def generateDeviceId():
		return str(uuid.uuid4())

	def _getHotURL(self, path, version=None):
		if version is None:
			version = self.resVersion
		return f"{self.abhot_url}/{ArknightsAPI.PLATFORM}/assets/{version}/{path}"

	def getHotUpdateListURL(self, version=None):
		return self._getHotURL("hot_update_list.json", version)

	def getHotUpdateAssetURL(self, asset, version=None):
		asset = asset.replace("/","_").replace("\\","_").replace("#","__")
		if "." in asset:
			asset = ".".join(asset.split(".")[:-1])
		asset += ".dat"
		return self._getHotURL(asset, version)

	def _fetchNetworkConfig(self):
		# The actual GET in the game also specifies a sign parameter but it doesn't seem to matter
		resp = self.session.get(ArknightsAPI.NETCONFIG_URL)
		if resp.status_code != 200:
			raise RuntimeError(f"Network Config failed: GET status is {resp.status_code}")
		data = resp.json()
		if "content" not in data:
			raise ValueError("Network Config failed: No content")
		netCfg = json.loads(data["content"])
		if "configVer" not in netCfg or "funcVer" not in netCfg or "configs" not in netCfg:
			raise ValueError("Network Config failed: No funcVer or configs")
		self.networkVersion = netCfg["configVer"]
		cfgVer = netCfg["funcVer"]
		if cfgVer not in netCfg["configs"]:
			raise ValueError("Network Config failed: Didn't find config")
		netCfg = netCfg["configs"][cfgVer]
		if "network" not in netCfg:
			raise ValueError("Network Config failed: No network in config")
		netCfg = netCfg["network"]
		if "gs" not in netCfg or "u8" not in netCfg or "hv" not in netCfg:
			raise ValueError("Network Config failed: Not all urls")
		self.gameserver_base = netCfg["gs"]
		self.u8sdk_base = netCfg["u8"]
		self.abversion_url = netCfg["hv"].format(ArknightsAPI.PLATFORM)
		self.abhot_url = netCfg["hu"]
		print(f"Network Version: {self.networkVersion}")
		print(f"GS Base: {self.gameserver_base}")
		print(f"U8SDK Base: {self.u8sdk_base}")
		print(f"HotUpdate URL: {self.abhot_url}")
		print(f"ABVer URL: {self.abversion_url}")

	def _fetchABVersion(self):
		resp = self.session.get(self.abversion_url)
		if resp.status_code != 200:
			raise RuntimeError(f"AB Version failed: GET status is {resp.status_code}")
		data = resp.json()
		if "clientVersion" not in data or "resVersion" not in data:
			raise ValueError("AB Version failed: No clientVersion or resVersion")
		self.clientVersion = data["clientVersion"]
		self.resVersion = data["resVersion"]
		print(f"Client Version: {self.clientVersion}")
		print(f"Ressources Version: {self.resVersion}")

	def _doGSPost(self, endpoint, data=None, **kwargs):
		self.session.headers["seqnum"] = str(self.seqnum)
		if data is None:
			data = {}
		kwargs.pop("json",None)
		resp = self.session.post(self.gameserver_base+endpoint,json=data,**kwargs)
		self.seqnum += 1
		if resp.status_code != 200:
			raise RuntimeError(f"GS POST Failed: POST status is {resp.status_code} (data is {resp.json()})")
		return resp.json()

	def _updateHeaders(self):
		if self.secret is not None:
			self.session.headers["secret"] = self.secret
		elif "secret" in self.session.headers:
			del self.session.headers["secret"]

		if self.uid is not None:
			self.session.headers["uid"] = self.uid
		elif "uid" in self.session.headers:
			del self.session.headers["uid"]

	def _checkResult(self, data):
		if "result" not in data:
			raise ValueError("GS POST Failed: No result")
		res = data["result"]
		del data["result"]
		return res

	def _loginGS(self, u8Token, uid, deviceId, deviceId2="", deviceId3=""):
		postData = {"assetsVersion":self.resVersion,"clientVersion":self.clientVersion,"deviceId":deviceId,
					"deviceId2":deviceId2,"deviceId3":deviceId3,"networkVersion":self.networkVersion,
					"platform":ArknightsAPI.PLATFORM_ID,"token":u8Token,"uid":uid}
		data = self._doGSPost("/account/login",postData)
		# I don't know why it does it like that but the seqnum is set to 1 afterwards when logging it to another account
		# So the login post is actually still using the old seqnum
		self.seqnum = 1
		res = self._checkResult(data)
		if res != 0:
			raise RuntimeError(f"GS Login Failed: Result is {res}")
		if "secret" not in data or "uid" not in data:
			raise ValueError("GS Login Failed: No secre or uid")
		self.secret = data["secret"]
		self.uid = data["uid"]
		self._updateHeaders()
		print(f"GS Secret: {self.secret}")
		print(f"GS UID: {self.uid}")

	def login(self, uid, token, account, deviceId2="", deviceId3=""):
		# Do AiriSDK Login first to get the access token
		self.airiSDK.login(uid, token, account)
		# Then we can get the U8 token
		self.u8SDK.login(self.airiSDK.token, self.airiSDK.uid, self.airiSDK.oldUid, self.deviceId, deviceId2, deviceId3)
		# Finally we can login to the Game Server
		self._loginGS(self.u8SDK.token, self.u8SDK.uid, self.deviceId, deviceId2, deviceId3)

	def yostarRequestLogin(self, email):
		self.airiSDK.yostarAuthRequest(email)

	def yostarCreateLogin(self, email, code):
		data = self.airiSDK.yostarGetAuth(email, code)
		data["deviceId"] = self.deviceId
		return data

	# https://stackoverflow.com/questions/3232943/update-value-of-a-nested-dictionary-of-varying-depth
	def _updateData(self, srcData, updateData):
		for key, value in updateData.items():
			if isinstance(value, collections.abc.Mapping):
				srcData[key] = self._updateData(srcData.get(key, {}), value)
			else:
				srcData[key] = value
		return srcData

	def _handleDeltaData(self, data):
		if "playerDataDelta" not in data:
			raise ValueError("Player Delta Data: No data")
		deltaData = data["playerDataDelta"]
		if "modified" not in deltaData or "deleted" not in deltaData:
			raise ValueError("Player Delta Data: No modified or deleted")
		if len(deltaData["deleted"]) > 0:
			print("Deleted data",deltaData["deleted"])
			print(self.playerData)
			print("deleted data is not implemented cuz i don't have any examples xd")
		self.playerData = self._updateData(self.playerData, deltaData["modified"])
		del data["playerDataDelta"]

	def syncData(self):
		data = self._doGSPost("/account/syncData",{"platform":ArknightsAPI.PLATFORM_ID})
		res = self._checkResult(data)
		if res != 0:
			raise RuntimeError(f"Data Sync Failed: Result is {res}")
		if "user" not in data:
			raise ValueError("Data Sync Failed: No user")
		self.playerData = data["user"]
		return self.playerData

	def getDailyRewards(self):
		data = self._doGSPost("/user/checkIn")
		self._handleDeltaData(data)
		return data

	# Daily credits
	def getSocialCredit(self):
		data = self._doGSPost("/social/receiveSocialPoint")
		self._handleDeltaData(data)
		return data

	# Type can be MAIN,DAILY,WEEKLY
	def autoConfirmMissions(self, type):
		data = self._doGSPost("/mission/autoConfirmMissions",{"type":type})
		self._handleDeltaData(data)
		return data

	@staticmethod
	def getCurrentTs():
		return int(datetime.now().astimezone(timezone.utc).timestamp())

	def getMailMetaList(self, fromTs=None):
		if fromTs is None:
			fromTs = self.getCurrentTs()
		data = self._doGSPost("/mail/getMetaInfoList",{"from":fromTs})
		self._handleDeltaData(data)
		return data

	def getMails(self, mailIds, systemMailIds=None):
		if isinstance(mailIds,int):
			mailIds = [mailIds]
		if systemMailIds is None:
			systemMailIds = []
		elif isinstance(systemMailIds,int):
			systemMailIds = [systemMailIds]
		data = self._doGSPost("/mail/listMailBox",{"mailIdList":mailIds,"sysMailIdList":systemMailIds})
		self._handleDeltaData(data)
		return data

	def collectMails(self, mailIds, systemMailIds=None):
		if isinstance(mailIds,int):
			mailIds = [mailIds]
		if systemMailIds is None:
			systemMailIds = []
		elif isinstance(systemMailIds,int):
			systemMailIds = [systemMailIds]
		data = self._doGSPost("/mail/receiveAllMail",{"mailIdList":mailIds,"sysMailIdList":systemMailIds})
		self._handleDeltaData(data)
		return data

	def deleteMails(self, mailIds, systemMailIds=None):
		if isinstance(mailIds,int):
			mailIds = [mailIds]
		if systemMailIds is None:
			systemMailIds = []
		elif isinstance(systemMailIds,int):
			systemMailIds = [systemMailIds]
		data = self._doGSPost("/mail/removeAllReceivedMail",{"mailIdList":mailIds,"sysMailIdList":systemMailIds})
		self._handleDeltaData(data)
		return data

	def syncRIIC(self):
		data = self._doGSPost("/building/sync")
		self._handleDeltaData(data)
		return data

	def getAllIntimacy(self):
		data = self._doGSPost("/building/gainAllIntimacy")
		self._handleDeltaData(data)
		return data

	# The credit you get when you open up the base for the clues
	def getMeetingReward(self, types):
		if isinstance(types,int):
			types = [types]
		data = self._doGSPost("/building/getMeetingroomReward",{"type":types})
		self._handleDeltaData(data)
		return data

	def settleFactory(self, roomIds, supplement=True):
		if isinstance(roomIds,str):
			roomIds = [roomIds]
		data = self._doGSPost("/building/settleManufacture",{"roomSlotIdList":roomIds,"supplement":int(supplement)})
		self._handleDeltaData(data)
		return data

	def deliverOrders(self, roomIds):
		if isinstance(roomIds,str):
			roomIds = [roomIds]
		data = self._doGSPost("/building/deliveryBatchOrder",{"slotList":roomIds})
		self._handleDeltaData(data)
		return data

	def assignCharRoom(self, roomId, charIds):
		if isinstance(charIds,int):
			charIds = [charIds]
		data = self._doGSPost("/building/assignChar",{"charInstIdList": charIds, "roomSlotId": roomId})
		self._handleDeltaData(data)
		return data

	def getDailyClue(self):
		data = self._doGSPost("/building/getDailyClue")
		self._handleDeltaData(data)
		return data

	def sendClue(self, clueId, friendId):
		data = self._doGSPost("/building/sendClue",{"clueId":clueId,"friendId":friendId})
		self._handleDeltaData(data)
		return data

	# Gives a minimal friend list related to clues
	def getClueFriendList(self):
		data = self._doGSPost("/building/getClueFriendList")
		self._handleDeltaData(data)
		return data

	# Allows to search for users, pending friend requests and friends while sorting
	def getSortListInfo(self, type, keyList=None, params=None):
		if keyList is None:
			keyList = []
		if params is None:
			params = {}
		data = self._doGSPost("/social/getSortListInfo",{"type":type,"sortKeyList":keyList,"param":params})
		self._handleDeltaData(data)
		return data

	# Helper to search users by nick for the previous function
	def searchUser(self, nick, nickNumber=""):
		return self.getSortListInfo(0,["level"],{"nickName":nick,"nickNumber":nickNumber})

	# This gets the search result user's info, so level and stuff
	def getSearchInfo(self, uids):
		if isinstance(uids,str):
			uids = [uids]
		data = self._doGSPost("/social/searchPlayer",{"idList": uids})
		self._handleDeltaData(data)
		return data

	# Helper to get the friends sorted by level and share(?)
	def getFriendList(self):
		return self.getSortListInfo(1,["level","infoShare"])

	# This gets the friend's info, so level and stuff 
	def getFriendInfo(self, friendIds):
		if isinstance(friendIds,str):
			friendIds = [friendIds]
		data = self._doGSPost("/social/getFriendList",{"idList": friendIds})
		self._handleDeltaData(data)
		return data

	# Helper to get the list of friend requests
	def getPendingFriendRequest(self):
		return self.getSortListInfo(2)

	# This gets the friend request user's info, so level and stuff 
	def getPendingFriendRequestInfo(self, friendIds):
		if isinstance(friendIds,str):
			friendIds = [friendIds]
		data = self._doGSPost("/social/getFriendRequestList",{"idList": friendIds})
		self._handleDeltaData(data)
		return data

	# idk what afterbattle does tbh but it was set to 0 for the friend request i did
	def sendFriendRequest(self, friendId, afterBattle=0):
		data = self._doGSPost("/social/sendFriendRequest",{"afterBattle": afterBattle, "friendId": friendId})
		self._handleDeltaData(data)
		return data

	# Action: 1 is for accept, 0 maybe refuse ? idk, don't have data 
	def processFriendRequest(self, friendId, action):
		data = self._doGSPost("/social/processFriendRequest",{"action": action, "friendId": friendId})
		self._handleDeltaData(data)
		return data

	def visitFriend(self, friendId):
		data = self._doGSPost("/building/visitBuilding",{"friendId": friendId})
		self._handleDeltaData(data)
		return data

	def getSocialGoodList(self):
		data = self._doGSPost("/shop/getSocialGoodList")
		self._handleDeltaData(data)
		return data

	def buySocialGood(self, goodId):
		data = self._doGSPost("/shop/buySocialGood",{"count": 1, "goodId":goodId})
		self._handleDeltaData(data)
		return data

	def syncRecruitment(self):
		data = self._doGSPost("/gacha/syncNormalGacha")
		self._handleDeltaData(data)
		return data

	def startRecruitment(self, slotId, duration, tags=[], specialTagId=-1):
		if isinstance(tags,int):
			tags = [tags]
		data = self._doGSPost("/gacha/normalGacha",{"duration":duration,"slotId":slotId,"specialTagId":specialTagId,"tagList":tags})
		self._handleDeltaData(data)
		return data

	def finishRecruitment(self, slotId):
		data = self._doGSPost("/gacha/finishNormalGacha",{"slotId":slotId})
		self._handleDeltaData(data)
		return data

	# IDK what buy is but it's 0 when i use recruitment plans
	def speedupRecruitment(self, slotId, buy=0):
		data = self._doGSPost("/gacha/boostNormalGacha",{"slotId":slotId,"buy":buy})
		self._handleDeltaData(data)
		return data

	def getPoolDetail(self, poolId):
		data = self._doGSPost("/gacha/getPoolDetail",{"poolId":poolId})
		self._handleDeltaData(data)
		return data

	# Annihilation PRTS Total Proxy
	def doBattleSweep(self, instanceId, itemId, stageId):
		data = self._doGSPost("/campaignV2/battleSweep",{"instId":instanceId,"itemId":itemId,"stageId":stageId})
		self._handleDeltaData(data)
		return data

	# Batch rotate
	def doBatchRotation(self):
		data = self._doGSPost("/building/batchChangeWorkChar")
		self._handleDeltaData(data)
		return data

	# Batch rest for rotations
	def doBatchRest(self):
		data = self._doGSPost("/building/batchRestChar")
		self._handleDeltaData(data)
		return data

	def getPlayerData(self):
		return self.playerData

	# Used for battle data
	def getLoginTs(self):
		if "pushFlags" not in self.playerData:
			raise RuntimeError("pushFlags not in playerData")
		if "status" not in self.playerData["pushFlags"]:
			raise RuntimeError("status not in pushFlags in playerData")
		return self.playerData["pushFlags"]["status"]