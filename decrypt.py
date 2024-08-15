import argparse,sys
from pathlib import Path
import pyknights.converter as converter

parser = argparse.ArgumentParser(description='Arknights asset decrypter')
parser.add_argument("file", help="Input file(s) or pipe", nargs="+")
parser.add_argument("-e", "--encrypt", help="Encrypt", action="store_true")
parser.add_argument("-s", "--signonly", help="Sign only", action="store_true")
parser.add_argument("-as", "--cryptasign", help="Signed Cryptic A", action="store_true")
parser.add_argument("-a", "--crypta", help="Cryptic A", action="store_true")
parser.add_argument("-b", "--cryptb", help="Cryptic B", action="store_true")
parser.add_argument("-bd", "--battledat", help="BattleData", action="store_true")
parser.add_argument("-bs", "--battlesig", help="BattleSignature", action="store_true")
parser.add_argument("-o", "--output", help="Output file/folder or pipe", type=str)
cmd_args = parser.parse_args()

conv = None
if cmd_args.signonly:
	conv = converter.SignConverter()
elif cmd_args.cryptasign:
	conv = converter.CrypticConverterWithSign()
elif cmd_args.crypta:
	conv = converter.CrypticConverterA()
elif cmd_args.cryptb:
	conv = converter.CrypticConverterB()
elif cmd_args.battledat:
	conv = converter.BattleDataConverter()
elif cmd_args.battlesig:
	conv = converter.FinishBattleSignatureConverter()
else:
	print("Please give a converter to use")
	exit()

stdin = len(cmd_args.file) == 1 and cmd_args.file[0] == "-"
arg_stdout = cmd_args.output == "-"
stdout = arg_stdout if cmd_args.output else True if stdin else arg_stdout

for file in cmd_args.file:
	if stdin:
		fdat = sys.stdin.buffer.read()
		out_file = Path(cmd_args.output).resolve()
	else:
		file = Path(file).resolve()
		out_file = file.with_suffix(".enc" if cmd_args.encrypt else ".dec")
		if cmd_args.output:
			out = Path(cmd_args.output).resolve()
			if len(cmd_args.file) == 1:
				out_file = out 
			else:
				out_file = out/out_file.name

		fdat = file.read_bytes()

	if cmd_args.encrypt:
		data = conv.encode(fdat)
	else:
		data = conv.decode(fdat)

	if stdout:
		sys.stdout.buffer.write(data)
	else:
		out_file.parent.mkdir(parents=True, exist_ok=True)
		out_file.write_bytes(data)
