import subprocess,argparse,json,os,base64,bson
from pathlib import Path

parser = argparse.ArgumentParser(description='FlatBuffer data converter')
parser.add_argument("schema", help="Schema file")
parser.add_argument("bin", help="Binary file")
cmd_args = parser.parse_args()

schema = Path(cmd_args.schema).resolve()
input = Path(cmd_args.bin).resolve()

# Run flatc to generate the json from the binary file and the schema
cmd = ["flatc","--defaults-json","--strict-json","--json","--raw-binary",str(schema),"--",str(input)]
print(f"Running: {' '.join(cmd)}")
ret = subprocess.run(cmd)
if ret.returncode != 0:
	print(f"Return code is non zero ({ret.returncode}), flatc probably crashed.")
	print("You might be using the wrong schema or binary file")
	print("Or the schema is broken, which is also likely as i haven't tested it on all of them")
	exit()

out_file = Path(os.getcwd()).resolve() / (input.stem+".json")

# Now we just cleanup dicts to not a list of dicts of key value but rather a straight dict with the right keys and values
# I didn't implement the cleanup of multi dimension arrays, as i can't be arsed lmao and it's less common
with open(out_file,'r',encoding="utf-8") as f:
	data = json.load(f)

out_file.replace(out_file.with_suffix(".old.json"))

dict_keys = set(["key","value"])
jobj_keys = set(["jobj_bson"])

# Recursive function to fix the dicts
def fix_dict(dat):
	if isinstance(dat, list):
		is_dict = True
		for elem in dat:
			if not (isinstance(elem,dict) and elem.keys() == dict_keys):
				is_dict = False
				break
		if is_dict:
			return {elem["key"]:fix_dict(elem["value"]) for elem in dat}

		for i in range(len(dat)):
			dat[i] = fix_dict(dat[i])
		return dat
	elif isinstance(dat, dict):
		if dat.keys() == jobj_keys:
			try:
				return bson.loads(base64.b64decode(dat["jobj_bson"]))
			except Exception as e:
				print(f"JOBJ fix failed: {e}")
				return dat
		else:
			for key,value in dat.items():
				if not isinstance(value, dict) and not isinstance(value, list):
					continue
				dat[key] = fix_dict(value)
			return dat
	return dat

# Apply to the data
data = fix_dict(data)

# Write back
with open(out_file, 'w', encoding='utf-8') as f:
	json.dump(data, f, ensure_ascii=False, indent=2)