// Mirrors the seeded districts and residue codes in seed/seed.py (the API has no list endpoint yet).
export const DISTRICTS = ["Lahore", "Sheikhupura", "Kasur", "Faisalabad", "Okara"] as const;

export const RESIDUES: { code: string; label: string }[] = [
  { code: "rice_straw", label: "Rice straw" },
  { code: "wheat_straw", label: "Wheat straw" },
  { code: "cotton_stalk", label: "Cotton stalk" },
  { code: "sugarcane_trash", label: "Sugarcane trash" },
];
