using System.Text;
using dnlib.DotNet;

namespace DNFBDmp {
	public class FlatbufferDefinition {
		// Name of class sanitized, used as filename
		public string name;
		// Signature associated with this Flatbuffer
		public TypeSig type;
		// A list of dependencies
		public HashSet<FlatbufferDefinition> dependencies;
		// Is it already done ? (either processed or we are currently doing it)
		public bool isDone;
		// Should this be referenced as a array ? (for dicts & arrays)
		public bool isArray;
		// Is this a root type ? (for classes, not for enums)
		public bool isRootType;

		// Data within the file definition
		public string? data;

		public static Dictionary<TypeSig, FlatbufferDefinition> convTypes = new Dictionary<TypeSig, FlatbufferDefinition>();
		public static HashSet<string> names = new HashSet<string>();

		public static FlatbufferDefinition convert(TypeSig type, TypeResolver resolver) {
			type = type.RemovePinnedAndModifiers();
			string name = Utils.cleanupClassName(type.FullName);
			FlatbufferDefinition fbDef;
			if (convTypes.TryGetValue(type, out fbDef)) {
				if (fbDef.name != name)
					throw new Exception("Mismatched name for same typedef ??");
			} else {
				fbDef = new FlatbufferDefinition(name, type);
			}

			if (!fbDef.isDone && fbDef.data == null)
				fbDef.build(resolver);

			return fbDef;
		}

		private FlatbufferDefinition(string name, TypeSig type) {
			this.name = name;
			this.type = type;
			
			this.dependencies = new HashSet<FlatbufferDefinition>();
			this.data = null;
			this.isDone = false;
			this.isArray = false;
			this.isRootType = false;

			if (names.Contains(name))
				throw new Exception("Duplicate class name");

			convTypes.Add(type, this);
		}

		public string? getType() {
			if (!this.isDone)
				return null;
			if (this.isArray)
				return $"[{this.name}]";
			return this.name;
		}

		public string getFile() {
			return this.name + ".fbs";
		}

		public bool writeToFile(string? path = null) {
			if (!this.isDone || this.data == null)
				return false;

			string outFile = getFile();
			if (path != null)
				outFile = Path.Combine(path, outFile);

			File.WriteAllText(outFile, this.data);

			return true;
		}

		private static string? getPrimitiveType(IType type) {
			switch (type.FullName) {
				case "System.Boolean": return "bool";
				case "System.Char":    return "uint16";
				case "System.SByte":   return "int8";
				case "System.Byte":    return "uint8";
				case "System.Int16":   return "int16";
				case "System.UInt16":  return "uint16";
				case "System.Int32":   return "int32";
				case "System.UInt32":  return "uint32";
				case "System.Int64":   return "int64";
				case "System.UInt64":  return "uint64";
				case "System.Single":  return "float";
				case "System.Double":  return "double";
				case "System.String":  return "string";
			}
			return null;
		}

		// Gets the TypeSig of the type inside the array if it's one
		private static TypeSig? getArraySig(TypeSig sig) {
			string fullName = sig.FullName;
			if (sig.IsGenericInstanceType && (fullName.StartsWith("System.Collections.Generic.List") ||
				fullName.StartsWith("System.Collections.Generic.Stack") || fullName.StartsWith("System.Collections.Generic.HashSet"))) {
				GenericInstSig genericInstSig = sig.ToGenericInstSig();
				return genericInstSig.GenericArguments[0];
			} else if (sig.IsSZArray) {
				return sig.Next;
			}
			return null;
		}

		// Change out the generic type parameter with the real TypeSig if needed
		private static TypeSig handleGenericSig(TypeSig sig, IList<TypeSig>? genericArgs) {
			if (sig.IsGenericTypeParameter) {
				if (genericArgs == null)
					throw new Exception("Generic parameters null with generic argument");
				GenericVar genericVar = sig.ToGenericVar();
				sig = genericArgs[(int)genericVar.Number];
			} else if (sig.IsGenericMethodParameter) {
				throw new Exception("Generic Method param not supported");
			}
			return sig;
		}

		// Find & return type of TypeSig, converts to FBDef if needed and adds to dependency
		private string? getType(TypeSig sig, TypeResolver resolver, IList<TypeSig>? genericArgs = null) {
			string? prim = getPrimitiveType(sig);
			if (prim != null)
				return prim;

			// Returns null if we're not an array, the type otherwise
			TypeSig? sigArray = getArraySig(sig);
			if (sigArray != null) {
				prim = getPrimitiveType(sigArray);
				if (prim != null)
					return $"[{prim}]";

				sigArray = handleGenericSig(sigArray, genericArgs);
				FlatbufferDefinition arrayFbDef = FlatbufferDefinition.convert(sigArray, resolver);
				if (arrayFbDef == null)
					return null;

				this.dependencies.Add(arrayFbDef);
				return $"[{arrayFbDef.getType()}]";
			}

			sig = handleGenericSig(sig, genericArgs);

			// If we're here that means this is probably a normal class, handle it
			FlatbufferDefinition fbDef = FlatbufferDefinition.convert(sig, resolver);
			if (fbDef == null)
				return null;

			this.dependencies.Add(fbDef);
			return fbDef.getType();
		}

		private static bool hasJsonIgnore(FieldDef field) { 
			foreach (CustomAttribute ca in field.CustomAttributes) {
				string fullName = ca.TypeFullName;
				if (fullName.StartsWith("Newtonsoft.Json.JsonIgnoreAttribute"))
					return true;
			}
			return false;
		}

		// Handles 
		private bool handleCustomFBS(TypeSig sig, IList<TypeSig>? genericArgs, TypeResolver resolver, FBSBuilder builder) {
			if (sig.FullName.StartsWith("System.Collections.Generic.Dictionary") || sig.FullName.StartsWith("Torappu.ListDict")) {
				Console.WriteLine("Is custom dict");

				if (genericArgs == null || genericArgs.Count != 2)
					throw new Exception("Bad dict generic args");

				string? keyType = getType(genericArgs[0], resolver);
				string? valueType = getType(genericArgs[1], resolver);

				if (keyType == null || valueType == null)
					throw new Exception("Couldn't get key or value type for dict");

				builder.beginTable(this.name);
				builder.addTableField("key", keyType);
				builder.addTableField("value", valueType);
				builder.endTable();

				this.isArray = true;
			} else if (sig.FullName.StartsWith("Newtonsoft.Json.Linq.JObject")) {
				Console.WriteLine("Is custom JObject");

				builder.beginTable(this.name);
				builder.addTableField("jobj_bson", "string");
				builder.endTable();
			} else {
				return false;
			}

			return true;
		}

		public bool build(TypeResolver resolver) {
			if (this.data != null)
				return false;
			this.isDone = true;

			Console.WriteLine($"Building - {this.name} ({this.type.FullName})");

			// Contains includes
			StringBuilder header = new StringBuilder();
			// Easier building of the table
			FBSBuilder fbBuilder = new FBSBuilder();

			TypeSig sig = this.type;
			// Generic args if we have some
			IList<TypeSig>? genericArgs = null;
			// We're a class by default
			this.isRootType = true;

			if (sig.IsGenericInstanceType) {
				GenericInstSig genericSig = sig.ToGenericInstSig();
				Console.WriteLine($"Is generic {genericSig.GenericType.FullName}");
				genericArgs = genericSig.GenericArguments;
				sig = genericSig.GenericType;
			}

			if (handleCustomFBS(sig, genericArgs, resolver, fbBuilder)) {
				// Schemas with custom serializing functions
				Console.WriteLine("Was custom FBS");
			} else if (sig.IsSZArray) {
				// Single dim array with non trivial type
				TypeSig arraySig = sig.Next;

				string? type = getType(arraySig, resolver);
				if (type == null)
					throw new Exception("Can't find array type");

				fbBuilder.beginTable(this.name);
				fbBuilder.addTableField("value", type);
				fbBuilder.endTable();
			} else if (sig.IsArray) {
				// Multi-dim array, there is deadass only fucking one class using it,
				// Fuck you for making me do this thing
				// It's in Torappu.MapData which is referenced in Torappu.LevelData
				// but i can't find for the love of me the file where it stored so i can look at how it is written
				// So this'll be empty for now
				Console.WriteLine("Is multi-dim array");
			} else if (sig.IsTypeDefOrRef) {
				// Regular class, bulk of the classes
				// Get the TypeDef
				ITypeDefOrRef classSig = sig.ToTypeDefOrRef();
				TypeDef? def = resolver.Find(classSig);
				if (def == null)
					throw new Exception($"Couldn't find class ? {classSig.FullName}");

				if (def.IsEnum) {
					// Enum
					TypeSig enumSig = def.GetEnumUnderlyingType();
					if (!enumSig.IsPrimitive)
						throw new Exception("Enum of non primitve type");

					string? primType = getPrimitiveType(enumSig);
					if (primType == null || !(primType.StartsWith("int") || primType.StartsWith("uint")))
						throw new Exception($"Invalid primitive type for enum: {primType}");

					fbBuilder.beginEnum(this.name, primType);
					int nbFields = def.Fields.Count;
					bool hasZero = false;
					// ignore the first one as it is the actual value
					for (int i = 1; i < nbFields; i++) {
						FieldDef field = def.Fields[i];
						if (!field.HasConstant)
							throw new Exception("Enum's field without a value");

						fbBuilder.addEnumValue(field.Name, field.Constant.Value);
						if (Convert.ToInt32(field.Constant.Value) == 0)
							hasZero = true;
					}
					// Hack to fix enums not working when no zero is defined...
					// We can't know what the default value of the flatbuffer is
					// So just signal we got the default value
					if (!hasZero)
						fbBuilder.addEnumValue("ENUM_DEFAULT_VALUE", 0);
					fbBuilder.endEnum();
					this.isRootType = false;
				} else {
					// Normal class
					fbBuilder.beginTable(this.name);
					foreach (FieldDef field in def.Fields) {
						if (field.IsStatic || field.IsNotSerialized || hasJsonIgnore(field))
							continue;

						TypeSig fieldSig = handleGenericSig(field.FieldType, genericArgs);

						//Console.WriteLine($"\t{field.Name} - {def.FullName} ({fieldSig.FullName})");
						string? type = getType(fieldSig, resolver, genericArgs);
						//Console.WriteLine($"\t\t{field.Name} - {def.FullName} ({fieldSig.FullName}) -> {type}");
						Console.WriteLine($"\t{field.Name} - {fieldSig.TypeName} ({field.FieldType.FullName}) - {type}");
						if (type == null)
							throw new Exception($"Can't find type for field '{field.Name}' ({field.FieldType.FullName}) in {def.FullName}");
						fbBuilder.addTableField(field.Name, type);
					}
					fbBuilder.endTable();
				}
			} else {
				// We don't know, should not happen in the first place
				throw new Exception("Unhandled type");
			}

			// Process dependencies
			foreach (FlatbufferDefinition fb in this.dependencies)
				header.AppendLine($"include \"{fb.getFile()}\";");

			Console.WriteLine($"Done - {this.name} ({this.type.FullName})");

			// Put together everything to make the FBS file
			this.data = header.ToString() + "\n"
						+ fbBuilder.build();

			if (this.isRootType)
				this.data += $"\nroot_type {this.name};";

			// Cleanup because all my homies hate CRLF Windows dogshit
			this.data = this.data.Replace("\r\n", "\n");

			return true;
		}
	}
}