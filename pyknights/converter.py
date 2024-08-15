import struct,socket,base64,binascii,random
# Used for fixed bit-size variables in random implem
import numpy as np
# pycryptodome
import Crypto.Hash.MD5 as MD5
import Crypto.PublicKey.RSA as RSA
import Crypto.Cipher.AES as AES
import Crypto.Signature.pkcs1_15 as pkcs1_15
import Crypto.Util.Padding as Padding

class Converter:
	"""Base class of all the converters, identity function"""

	def encode(self, data: bytes, **kwargs) -> bytes:
		return data

	def decode(self, data: bytes, **kwargs) -> bytes:
		return data

class CrypticConverterA(Converter):
	OLD_TOKEN = b"8OjXUSNSi8yXC0u98mNWvh7MRLGhyEuQ"
	TOKEN = b"UITpAi82pHAWwnzqHRMCwPonJLIB3WCl"

	def __init__(self, token=TOKEN, **kwargs):
		super().__init__(**kwargs)
		self.mask = token[16:]
		self.aes_key = token[:16]
		assert(len(self.aes_key)==16 and len(self.mask)==16)

	def encode(self, data: bytes, **kwargs) -> bytes:
		data = super().encode(data, **kwargs)

		# Not sure about padding placment in case of <16 bytes
		data = Padding.pad(data, 16, style="pkcs7")

		# Caclulate IV
		iv = data[:16]
		iv_mask = bytes([self.mask[i] ^ iv[i] for i in range(16)])

		aes = AES.new(self.aes_key, AES.MODE_CBC, iv=iv)
		enc_data = aes.encrypt(data)
		return iv_mask + enc_data

	def decode(self, data: bytes, **kwargs) -> bytes:
		if len(data) < 32:
			raise RuntimeError("Not enough data, need at least 32 bytes")

		# Caclulate IV
		iv = bytes([self.mask[i] ^ data[i] for i in range(16)])

		aes = AES.new(self.aes_key, AES.MODE_CBC, iv=iv)
		dec_data = aes.decrypt(data[16:])
		return super().decode(Padding.unpad(dec_data, 16, style="pkcs7"), **kwargs)

class SignConverter(Converter):
	PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----\nMIGdMA0GCSqGSIb3DQEBAQUAA4GLADCBhwKBgQCvlvAc3e4BZc1vtc/45jTKMpDFcDsbYQUIRV9Y\njQToB4vaypDHbZvEWTktFZuoM5MMET/lo4H4fgtF5dN0ELHMhiod9NtANzsDXiJyALYdVdxgr6p2\nAUM3DYtlrBj1rmVDMMzvbebaHbaCoPfhJ3/w+uIVZI85f6CIK0CKnZ38hQIBEQ==\n-----END PUBLIC KEY-----"""

	def __init__(self, key=PUBLIC_KEY, **kwargs):
		super().__init__(**kwargs)
		self.key = RSA.import_key(key)
		self.has_private = self.key.has_private()
		self.sig = pkcs1_15.new(self.key)

	# Implemented just in case, but realistically you'll never get the private key
	# unless you have a couple of billons of dollars laying around
	def encode(self, data:bytes, **kwargs) -> bytes:
		data = super().encode(data, **kwargs)

		if not self.has_private:
			raise NotImplementedError("Can't encode without the private key...")

		sign = self.sig.sign(MD5.new(data))

		return sign + data

	def decode(self, data:bytes, verify=True, **kwargs) -> bytes:
		if len(data) < 128+1:
			raise RuntimeError("Not enough data, need at least 128+1 bytes")

		# First 128 bytes are the signature, rest is the data
		if verify:
			sign = data[:128]
			self.sig.verify(MD5.new(data[128:]), sign)

		return super().decode(data[128:], **kwargs)


class CrypticConverterWithSign(SignConverter, CrypticConverterA):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)

	def encode(self, data:bytes, **kwargs) -> bytes:
		return super().encode(data, **kwargs)

	def decode(self, data:bytes, verify=True, **kwargs) -> bytes:
		return super().decode(data, verify=verify, **kwargs)
	

class SharpNeatLibFastRandom:
	"""
	Based on https://github.com/giacomelli/GeneticSharp/blob/master/src/GeneticSharp.Domain/Randomizations/Externals/FastRandom.cs
	Not a great implem but works
	"""

	REAL_UNIT_INT = np.double(1.0) / (np.double(0x7FFFFFFF) + np.double(1.0))
	REAL_UNIT_UINT = np.double(1.0) / (np.double(0xFFFFFFFF) + np.double(1.0))
	Y = np.uint32(842502087)
	Z = np.uint32(3579807591)
	W = np.uint32(273326509)

	def __init__(self, seed: int):
		self.reinit(seed)

	# Seed must be 32 bit unsigned integer
	def reinit(self, seed: int):
		self.x = np.uint32(seed)
		self.y = self.Y
		self.z = self.Z
		self.w = self.W

	def _advance(self):
		t = np.uint32(self.x ^ (self.x << 11))
		self.x,self.y,self.z = self.y,self.z,self.w

		self.w = np.uint32(self.w ^ (self.w >> 19)) ^ (t ^ (t >> 8))

	def next(self, lower: int, upper: int) -> np.int32:
		lower, upper = np.int32(lower), np.int32(upper)

		if lower > upper:
			raise RuntimeError(f"Range is invalid, {lower} > {upper}")

		self._advance()

		range = upper - lower

		if range < 0:
			return lower + np.int32(self.REAL_UNIT_UINT * np.double(self.w) * np.double(np.int64(upper) - np.int64(lower)))

		return lower + np.int32(self.REAL_UNIT_INT * np.double(np.int32(0x7FFFFFFF & self.w)) * np.double(range))

	def next_double(self) -> np.double:
		self._advance()

		return np.double(self.REAL_UNIT_INT * np.int32(0x7FFFFFFF & self.w))


#Not tested with real data, decoding encoded data works though
class CrypticConverterB(Converter):
	ENC_START_SEED = struct.unpack("<I", MD5.new(b"0.577215").digest()[:4])[0]

	def __init__(self, seed=42, **kwargs):
		super().__init__(**kwargs)
		self.seed = np.uint32(seed)
		self.random = SharpNeatLibFastRandom(self.seed)

	# seed should be uint32
	def set_seed(self, seed: int):
		self.seed = np.uint32(seed)
		self.random.reinit(self.seed)

	def get_seed(self) -> np.uint32:
		return self.seed

	def rand(self) -> np.uint32:
		return np.uint32(self.random.next(0x0, 0x7FFFFFFF))

	# word & key should be uint32
	def crypt(self, word: int, key: int) -> np.uint32:
		return np.uint32(key) ^ np.uint32(word) ^ self.rand()

	def encode(self, data: bytes, **kwargs) -> bytes:
		data = super().encode(data, **kwargs)

		self.set_seed(self.ENC_START_SEED)

		seed = self.rand()
		self.set_seed(seed)

		or_size = len(data)

		out = bytearray()
		out += struct.pack("@II", socket.htonl(int(seed)), socket.htonl(int(len(data) ^ self.rand() ^ seed)))

		size = len(data)
		if size % 4 != 0:
			#print("Malformatted data, not divisible by 4, padding with zeros, don't except a miracle")
			data = data + b"\x00"*(4-(size%4))
			size = len(data)

		nb_ints = size//4
		ints = struct.unpack(f"@{nb_ints}I", data)

		last_val = or_size
		for i in ints:
			val = socket.htonl(i)
			out += struct.pack("@I", socket.htonl(int(val ^ last_val ^ self.rand())))
			last_val = val

		return out

	def decode(self, data: bytes, **kwargs) -> bytes:
		in_size = len(data)
		if in_size < 4*3:
			raise RuntimeError("Not enough data, need at least 12 bytes")

		if in_size % 4 != 0:
			#print("Malformatted data, not divisible by 4, padding with zeros, don't except a miracle")
			data = data + b"\x00"*(4-(in_size%4))
			in_size = len(data)

		seed, real_size = struct.unpack("!II", data[:8])

		self.set_seed(seed)

		real_size = real_size ^ seed ^ self.rand()

		print(real_size, in_size)

		nb_ints = (in_size-4*2)//4
		ints = struct.unpack(f"!{nb_ints}I", data[8:])

		out = bytearray()
		state = real_size
		for i in ints:
			state = np.uint32(state ^ i ^ self.rand())
			out += struct.pack("@I", socket.ntohl(int(state)))

		return super().decode(out[:real_size], **kwargs)

class FinishBattleSignatureConverter(Converter):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)

	def encode(self, data: bytes, **kwargs) -> bytes:
		data = super().encode(data, **kwargs)
		if len(data) < 1:
			return data

		return base64.b64encode(bytearray([i+7 for i in data]))

	def decode(self, data: bytes, **kwargs) -> bytes:
		if len(data) < 1:
			return data

		return super().decode(bytes([i-7 for i in base64.b64decode(data)]), **kwargs)

class BattleDataConverter(Converter):
	TOKEN = b"pM6Umv*^hVQuB6t&"

	def __init__(self, log_time=42, token=TOKEN, **kwargs):
		super().__init__(**kwargs)
		self.key = MD5.new(token+str(log_time).encode("utf-8")).digest()

	def encode(self, data: bytes, **kwargs) -> bytes:
		data = super().encode(data, **kwargs)

		data = Padding.pad(data, 16, style="pkcs7")

		iv = random.randbytes(16)

		aes = AES.new(self.key, AES.MODE_CBC, iv=iv)
		enc_data = aes.encrypt(data)

		return binascii.hexlify(enc_data+iv).upper()

	def decode(self, data: bytes, **kwargs) -> bytes:
		if len(data) < 64:
			raise RuntimeError("Not enough data, need at least 64 bytes")

		data = bytes.fromhex(data.decode("utf-8"))

		iv = data[-16:]
		aes = AES.new(self.key, AES.MODE_CBC, iv=iv)

		return super().decode(Padding.unpad(aes.decrypt(data[:-16]), 16, style="pkcs7"), **kwargs)