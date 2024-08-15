using System;
using System.ComponentModel.Design;
using System.Data.SqlTypes;
using System.IO;
using dnlib.DotNet;

namespace DNFBDmp {
	class MainClass {
		private static void Main(string[] args) {
			// Do some argument parsing
			if (args.Length == 0) {
				Console.WriteLine("Usage:");
				Console.WriteLine("\tDNFBDmp.exe <folder to DumyDLLs> [output folder]");
				Console.WriteLine();
				Console.WriteLine("If the output folder is not specified, defaults to 'output' in the current dir");
				return;
			}

			string outputFolder = args.Length >= 2 ? args[1] : @"output/";
			string inputFolder = args[0];

			// Load all the Dummy DLLs
			ModuleContext modCtx = ModuleDef.CreateModuleContext();
			TypeResolver resolver = new TypeResolver();
			foreach (string file in Directory.GetFiles(inputFolder, "*.dll")) {
				Console.WriteLine($"Loading DLL {file}");
				resolver.add(ModuleDefMD.Load(file, modCtx));
			}

			// Find the base class for flatbuffers converters
			TypeDef? fbLookupType = resolver.Find("Torappu.FlatBuffers.FlatLookupConverter", false);
			if (fbLookupType == null) {
				Console.WriteLine("Can't find base flatbuffers lookup converter type");
				return;
			}

			// Look for "entry points", aka non generic classes/structs 
			foreach (MethodDef met in fbLookupType.Methods) {
				string orName = met.Name;
				if (!orName.StartsWith("Unpack_"))
					continue;

				// Skip unpack to get real class name
				orName = orName[7..];
				string name = orName.Replace("_", ".");

				// We can safely ignore dicts as they are generic and we process them later on
				if (name.StartsWith("Key.") || name.StartsWith("Value."))
					continue;

				// Try to find type from the name string
				// Initially just the normal class
				// Then if not found, progressively add levels of subclass
				// This is not strictly necessary as i think all of the "real" entry classes
				// are not subclasses. (by real i mean what is actually wrote to a file as a singular table)
				TypeDef? curType = null;
				do {
					curType = resolver.Find(name, true);
					if (curType != null)
						break;
					name = Utils.replaceLast(name, ".", "+");
				} while (name.IndexOf(".") >= 0);


				// If we still didn't find it, that means it's probably a generic class...
				// We can safely ignore as it will get processed when the time comes.
				if (curType == null)
					continue;

				// Verify the class we got actually matches what we create
				// Just in case, report if mismatched.
				string qualName = Utils.cleanupClassName(curType.FullName);
				if (qualName != orName) {
					Console.WriteLine($"Mismatched class calculated: Converted='{qualName}' - Original='{orName}'");
					continue;
				}

				// If we reach here, that means this is real entry
				// Encapsulate it into a TypeSig, imitating a field
				// and send it to the flatbuffer converter
				FlatbufferDefinition.convert(new ClassSig(curType).RemovePinnedAndModifiers(), resolver);
			}

			// Create the folder, incase it doesn't exist
			Directory.CreateDirectory(outputFolder);
			// Now we write all the files
			Console.WriteLine("Writing to files");
			foreach (FlatbufferDefinition fbDef in FlatbufferDefinition.convTypes.Values)
				fbDef.writeToFile(outputFolder);
		}
	}
}