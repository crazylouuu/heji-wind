"""
ChemELN Cheminformatics Engine — RDKit-powered utilities.
Provides: SMILES/Molfile parsing, MW/formula, substructure search,
InChI/InChIKey conversion, molblock generation, structure image rendering.
"""
from rdkit import Chem
from rdkit.Chem import Descriptors, AllChem, Draw, rdMolDescriptors
from io import BytesIO
import base64
import json

def parse_smiles(smiles: str) -> dict:
    """Parse a SMILES string and return chemical info."""
    if not smiles or not smiles.strip():
        return {"valid": False, "error": "Empty SMILES"}
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"valid": False, "error": "Invalid SMILES"}
    return _mol_info(mol, smiles)


def parse_molfile(molfile: str) -> dict:
    """Parse a MDL mol block."""
    if not molfile or not molfile.strip():
        return {"valid": False, "error": "Empty molfile"}
    mol = Chem.MolFromMolBlock(molfile)
    if mol is None:
        return {"valid": False, "error": "Invalid molfile"}
    return _mol_info(mol, Chem.MolToSmiles(mol))


def _mol_info(mol, smiles: str) -> dict:
    """Extract all useful info from an RDKit Mol object."""
    try:
        inchi = Chem.MolToInchi(mol)
        inchikey = Chem.InchiToInchiKey(inchi) if inchi else ""
    except Exception:
        inchi, inchikey = "", ""
    try:
        canonical = Chem.MolToSmiles(mol, canonical=True)
    except Exception:
        canonical = smiles

    formula = rdMolDescriptors.CalcMolFormula(mol)
    mw = Descriptors.MolWt(mol)
    heavy_atoms = mol.GetNumHeavyAtoms()
    ring_count = rdMolDescriptors.CalcNumRings(mol)

    return {
        "valid": True,
        "smiles": canonical,
        "inchi": inchi,
        "inchikey": inchikey,
        "formula": formula,
        "mw": round(mw, 3),
        "heavy_atoms": heavy_atoms,
        "ring_count": ring_count,
    }


def render_structure_image(smiles: str, size: int = 400) -> str:
    """Render a 2D structure as base64 PNG."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ""
    AllChem.Compute2DCoords(mol)
    img = Draw.MolToImage(mol, size=(size, size))
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def substructure_search(target_smiles: str, query_smiles: str) -> bool:
    """Check if query is a substructure of target."""
    target = Chem.MolFromSmiles(target_smiles)
    query = Chem.MolFromSmiles(query_smiles)
    if target is None or query is None:
        return False
    return target.HasSubstructMatch(query)


def get_molblock(smiles: str) -> str:
    """Convert SMILES to MDL mol block."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ""
    # Add hydrogens for 3D, but for 2D mol block just use as-is
    mol = Chem.AddHs(mol)
    AllChem.Compute2DCoords(mol)
    mol = Chem.RemoveHs(mol)
    return Chem.MolToMolBlock(mol)


def smiles_to_inchikey(smiles: str) -> str:
    """Convert SMILES to InChIKey for compound deduplication."""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return ""
    inchi = Chem.MolToInchi(mol)
    if not inchi:
        return ""
    return Chem.InchiToInchiKey(inchi)


def calculate_reagent_table(substrate_mass_mg: float, substrate_mw: float,
                             reagents: list) -> list:
    """
    Auto-calculate a reagent table.
    reagents: [{"name":"", "smiles":"", "role":"reagent",
                 "ratio_type":"equiv"|"weight", "ratio_value":1.2,
                 "purity_pct":98.0, "density":0.789, "concentration":2.5}]

    Substrate moles (mmol) = substrate_mass_g * 1000 / substrate_mw.
    For each non-substrate reagent:
      - equiv mode: moles = substrate_moles * ratio_value;
        mass_g = moles * mw / 1000 / purity;
        volume_ml = moles / concentration or mass_g / density.
      - weight mode: mass_g = ratio_value * substrate_mass_g (no moles/volume).
    Mass unit is grams (mass_g); substrate_mass_mg is accepted for legacy callers.
    """
    substrate_mass_g = substrate_mass_mg / 1000.0 if substrate_mass_mg > 100 else substrate_mass_mg
    if substrate_mw <= 0 or substrate_mass_g <= 0:
        return reagents

    substrate_moles_mmol = substrate_mass_g * 1000 / substrate_mw  # mmol

    results = []
    for r in reagents:
        r = dict(r)  # copy
        mw = r.get("mw", 0)
        role = r.get("role", "reagent")
        ratio_type = r.get("ratio_type", "equiv")
        ratio_value = r.get("ratio_value")
        if ratio_value is None:
            ratio_value = r.get("equivalents", 0) or 0

        if role == "substrate":
            r["moles_mmol"] = round(substrate_moles_mmol, 4)
            r["mass_g"] = round(substrate_mass_g, 4)
        elif ratio_type == "weight":
            # Weight ratio: mass = ratio * substrate mass. No moles/volume.
            r["mass_g"] = round(ratio_value * substrate_mass_g, 4)
            r["moles_mmol"] = None
            r["volume_ml"] = None
        else:
            moles_mmol = substrate_moles_mmol * ratio_value
            r["moles_mmol"] = round(moles_mmol, 4)
            if mw > 0:
                purity = (r.get("purity_pct") or 100) / 100.0
                mass_g = (moles_mmol * mw / 1000.0) / purity if purity > 0 else moles_mmol * mw / 1000.0
                r["mass_g"] = round(mass_g, 4)
                density = r.get("density")
                concentration = r.get("concentration")
                if concentration and concentration > 0:
                    r["volume_ml"] = round(moles_mmol / concentration, 4)
                elif density and density > 0 and mass_g > 0:
                    r["volume_ml"] = round(mass_g / density, 4)
            else:
                r["mass_g"] = None
                r["volume_ml"] = None

        results.append(r)

    return results


def standardize_smiles(smiles: str) -> str:
    """Return a standardized canonical SMILES."""
    try:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return smiles
        return Chem.MolToSmiles(mol, canonical=True)
    except Exception:
        return smiles
