using dnlib.DotNet;

namespace DNFBDmp {
	// This class is just a manual resolver by iterating through the modules
	// and finding the right definition.
	// Maybe there was a way to do it with the module context int dnlib
	// but i couldn't get it to work, i might be dumb.
	public class TypeResolver {
		private List<ModuleDef> modules;

		public TypeResolver() {
			this.modules = new List<ModuleDef>();
		}

		public void add(ModuleDef module) {
			this.modules.Add(module);
		}

		public TypeDef? Find(string fullName, bool isReflectionName) {
			foreach (ModuleDef mod in this.modules) {
				TypeDef td = mod.Find(fullName, isReflectionName);
				if (td != null)
					return td;
			}
			return null;
		}

		public TypeDef? Find(TypeRef typeRef) {
			foreach (ModuleDef mod in this.modules) {
				TypeDef td = mod.Find(typeRef);
				if (td != null)
					return td;
			}
			return null;
		}

		public TypeDef? Find(ITypeDefOrRef typeRef) {
			foreach (ModuleDef mod in this.modules) {
				TypeDef td = mod.Find(typeRef);
				if (td != null)
					return td;
			}
			return null;
		}
	}
}