from mitmproxy import contentviews
from mitmproxy import flow
from mitmproxy import http
from mitmproxy.addonmanager import Loader
from mitmproxy.contentviews.json import ViewJSON

from google.protobuf.json_format import MessageToJson
import lz4.block
# Compiled with protoc v25.4
import sls_pb2

class ViewSLS(ViewJSON):
	name = "sls-protobuf"

	def __call__(
		self,
		data: bytes,
		*,
		content_type: str = None,
		flow: flow.Flow = None,
		http_message: http.Message = None,
		**unknown_metadata,
	) -> contentviews.TViewResult:

		if "x-log-compresstype" in http_message.headers:
			comp = http_message.headers["x-log-compresstype"]
			if comp == "lz4":
				data = lz4.block.decompress(data, uncompressed_size=int(http_message.headers["x-log-bodyrawsize"]))
			elif comp == "zstd":
				# Not used here
				data = data
			else:
				raise RuntimeError(f"Unsupported compression type: {comp}")

		logGroup = sls_pb2.LogGroup()
		logGroup.ParseFromString(data)
		data = MessageToJson(logGroup).encode("utf-8")
		parent = super().__call__(data, content_type=content_type, flow=flow, http_message=http_message, **unknown_metadata)

		return "SLS Protobuf JSON", parent[1]

	def render_priority(
		self,
		data: bytes,
		*,
		content_type: str = None,
		flow: flow.Flow = None,
		http_message: http.Message = None,
		**unknown_metadata,
	) -> float:

		if http_message is not None and content_type is not None and content_type.startswith("application/x-protobuf") and "x-log-apiversion" in http_message.headers:
			# higher than normal protobuf
			return 2

		return 0


view = ViewSLS()

def load(loader: Loader):
	contentviews.add(view)

def done():
	contentviews.remove(view)
