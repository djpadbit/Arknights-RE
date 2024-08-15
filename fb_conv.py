import subprocess,argparse,json,os,base64,bson
from pathlib import Path

parser = argparse.ArgumentParser(description='FlatBuffer data converter')
parser.add_argument("schema", help="Schema file")
parser.add_argument("bin", help="Binary file")
cmd_args = parser.parse_args()

schema = Path(cmd_args.schema).resolve()
input = Path(cmd_args.bin).resolve()

# Run flatc to generate the json from the binary file and the schema
cmd = ["flatc","--no-warnings","--defaults-json","--strict-json","--json","--raw-binary",str(schema),"--",str(input)]
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

dict_keys = set(["dict_key","dict_value"])
jobj_keys = set(["jobj_bson"])
arr_keys = set(["arr_values"])

# Recursive function to fix the dicts, nested single dim array and jobjects
def fix_dict(dat):
	if isinstance(dat, list):
		is_dict = True if len(dat) > 0 else False
		is_arr = True if len(dat) > 0 else False

		for elem in dat:
			if not (isinstance(elem,dict) and elem.keys() == dict_keys):
				is_dict = False
				break

		for elem in dat:
			if not (isinstance(elem,dict) and elem.keys() == arr_keys):
				is_arr = False
				break

		if is_dict:
			return {elem["dict_key"]:fix_dict(elem["dict_value"]) for elem in dat}
		elif is_arr:
			return [fix_dict(elem["arr_values"]) for elem in dat]

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