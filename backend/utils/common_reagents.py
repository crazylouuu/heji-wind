"""
Built-in common reagent dictionary for MW lookup.
Maps common reagent names (Chinese / English / abbreviation) to chemical formulas.
MW is computed from the formula via formula_mw().

⚠️ 本文件由 scripts/build_chemistry_data.py 自动生成，请勿手改！
    数据源：shared/chemistry-data.json
    生成时间：2026-10-22 13:59:10
    条目数：233（CAS 唯一，含溶剂物性详表 + chemELN 试剂库合并）
"""

# (name, aliases, formula, cas)
COMMON_REAGENTS = [
    ("1,1,1-三氯乙烷(TCA)", ["1,1,1-Trichloroethane (TCA)"], "C2H3Cl3", "71-55-6"),
    ("1,2-二氯乙烷(DCE)", ["1,2-Dichloroethane (DCE)", "1,2-dichloroethane", "dce", "二氯乙烷"], "C2H4Cl2", "107-06-2"),
    ("1,2-二氯苯(o-DCB)", ["o-Dichlorobenzene (o-DCB)"], "C6H4Cl2", "95-50-1"),
    ("1,2-二甲氧基乙烷(DME·glyme)", ["1,2-Dimethoxyethane (DME, glyme)"], "C4H10O2", "110-71-4"),
    ("1,4-二氧六环", ["1,4-Dioxane", "1,4-二氧六环", "dioxane", "二噁烷"], "C4H8O2", "123-91-1"),
    ("18-冠-6", ["18-crown-6", "18冠6"], "C12H24O6", "17455-13-9"),
    ("2,2,2-三氟乙醇(TFE)", ["2,2,2-Trifluoroethanol (TFE)"], "C2H3F3O", "75-89-8"),
    ("2,6-二甲基吡啶(Lut)", ["2,6-Lutidine (Lut)"], "C7H9N", "108-48-5"),
    ("2-戊酮(MPK·甲基丙基酮)", ["2-Pentanone (MPK)"], "C5H10O", "107-87-9"),
    ("2-甲基四氢呋喃(2-MeTHF)", ["2-Methyltetrahydrofuran (2-MeTHF)", "2-me-thf", "2-methylthf"], "C5H10O", "96-47-9"),
    ("2-甲氧基乙醇(2-ME·甲基溶纤剂)", ["2-Methoxyethanol (2-ME)"], "C3H8O2", "109-86-4"),
    ("3-戊酮(DEK·二乙基酮)", ["3-Pentanone (DEK)"], "C5H10O", "96-22-0"),
    ("4-二甲氨基吡啶", ["dmap", "4-dimethylaminopyridine"], "C7H10N2", "1122-58-3"),
    ("BINAP", ["2,2'-双(二苯基膦)-1,1'-联萘", "binap"], "C44H32P2", "98327-87-8"),
    ("CDI", ["cdi", "羰基二咪唑", "carbonyldiimidazole", "1,1'-羰基二咪唑"], "C7H6N4O", "530-62-1"),
    ("Cu(OAc)2", ["醋酸铜", "copper(ii) acetate", "cu(oac)2"], "C4H6CuO4", "142-71-2"),
    ("CuBr", ["溴化亚铜", "copper(i) bromide", "cubr"], "CuBr", "7787-70-4"),
    ("CuCl", ["氯化亚铜", "copper(i) chloride", "cucl"], "CuCl", "7758-89-6"),
    ("CuI", ["碘化亚铜", "copper(i) iodide", "cui"], "CuI", "7681-65-4"),
    ("DABCO", ["三乙烯二胺", "1,4-diazabicyclo[2.2.2]octane"], "C6H12N2", "280-57-9"),
    ("DBU", ["1,8-二氮杂双环[5.4.0]十一碳-7-烯", "1,8-diazabicyclo[5.4.0]undec-7-ene"], "C9H16N2", "6674-22-2"),
    ("DCC", ["dcc", "二环己基碳二亚胺", "dicyclohexylcarbodiimide"], "C13H22N2", "538-75-0"),
    ("DIBAL-H", ["二异丁基氢化铝", "diisobutylaluminium hydride", "dibal"], "C8H19Al", "119-61-9"),
    ("DMI(1,3-二甲基-2-咪唑啉酮)", ["1,3-Dimethyl-2-imidazolidinone (DMI)"], "C5H10N2O", "80-73-9"),
    ("DMPU(1,3-二甲基丙撑脲)", ["1,3-Dimethyl-3,4,5,6-tetrahydro-2(1H)-pyrimidinone (DMPU)"], "C6H12N2O", "7226-23-5"),
    ("EDCI", ["edc", "1-(3-二甲氨基丙基)-3-乙基碳二亚胺盐酸盐", "edc·hcl", "1-ethyl-3-(3-dimethylaminopropyl)carbodiimide"], "C8H17N3", "1892-57-5"),
    ("EDTA", ["乙二胺四乙酸", "edta", "edta acid"], "C10H16N2O8", "60-00-4"),
    ("HATU", ["hatu", "o-(7-氮杂苯并三唑-1-基)-n,n,n',n'-四甲基脲六氟磷酸盐"], "C10H15F6N6OP", "148893-10-1"),
    ("HBTU", ["hbtu", "o-苯并三氮唑-n,n,n',n'-四甲基脲六氟磷酸盐"], "C11H16BF6N5OP", "94790-37-1"),
    ("HMPA(六甲基磷酰三胺)", ["Hexamethylphosphoramide (HMPA)"], "C6H18N3OP", "680-31-9"),
    ("HOBT", ["hobt", "1-羟基苯并三唑", "1-hydroxybenzotriazole"], "C6H5N3O", "123-33-1"),
    ("IBX", ["2-碘酰基苯甲酸", "2-iodoxybenzoic acid", "ibx"], "C7H5IO4", "61717-82-6"),
    ("KHMDS", ["六甲基二硅基氨基钾", "potassium bis(trimethylsilyl)amide", "khmds"], "C6H18KNSi2", "40949-94-8"),
    ("LDA", ["二异丙基氨基锂", "lithium diisopropylamide"], "C6H14LiN", "4111-54-0"),
    ("LiHMDS", ["六甲基二硅基氨基锂", "lithium bis(trimethylsilyl)amide", "lihmds"], "C6H18LiNSi2", "4039-32-1"),
    ("N,N-二甲基乙酰胺(DMAc)", ["N,N-Dimethylacetamide (DMAc)", "dmac", "n,n-二甲基乙酰胺", "二甲基乙酰胺"], "C4H9NO", "127-19-5"),
    ("N,N-二甲基甲酰胺(DMF)", ["N,N-Dimethylformamide (DMF)", "dmf", "n,n-dimethylformamide", "n,n-二甲基甲酰胺", "二甲基甲酰胺"], "C3H7NO", "68-12-2"),
    ("N-甲基吡咯烷酮(NMP)", ["1-甲基-2-吡咯烷酮", "N-Methyl-2-pyrrolidone (NMP)", "n-甲基吡咯烷酮", "nmp"], "C5H9NO", "872-50-4"),
    ("NBS", ["n-溴代琥珀酰亚胺", "n-bromosuccinimide", "nbs"], "C4H4BrNO2", "128-08-5"),
    ("NCS", ["n-氯代琥珀酰亚胺", "n-chlorosuccinimide", "ncs"], "C4H4ClNO2", "128-09-6"),
    ("NIS", ["n-碘代琥珀酰亚胺", "n-iodosuccinimide", "nis"], "C4H4INO2", "516-12-1"),
    ("NaHMDS", ["六甲基二硅基氨基钠", "sodium bis(trimethylsilyl)amide", "nahmds"], "C6H18NNaSi2", "1070-89-9"),
    ("PCC", ["氯铬酸吡啶盐", "pyridinium chlorochromate"], "C5H6ClCrNO", "26299-14-9"),
    ("Pd(dppf)Cl2", ["pd(dppf)cl2", "[1,1'-双(二苯基膦)二茂铁]二氯化钯", "dppf pdcl2"], "C34H28Cl2FeP2Pd", "72287-26-4"),
    ("TBTU", ["tbtu", "o-苯并三氮唑-n,n,n',n'-四甲基脲四氟硼酸"], "C11H16BF4N5O", "125700-67-6"),
    ("Xantphos", ["4,5-双二苯基膦-9,9-二甲基氧杂蒽", "xantphos"], "C39H32OP2", "161265-03-8"),
    ("dppp", ["1,3-双(二苯基膦)丙烷", "1,3-bis(diphenylphosphino)propane"], "C27H26P2", "6737-42-4"),
    ("mCPBA", ["间氯过氧苯甲酸", "3-chloroperoxybenzoic acid", "mcpba"], "C7H5ClO3", "937-14-4"),
    ("γ-丁内酯(GBL)", ["γ-Butyrolactone (GBL)"], "C4H6O2", "96-48-0"),
    ("丁酮(MEK)", ["2-Butanone (MEK)"], "C4H8O", "78-93-3"),
    ("三(邻甲基苯基)膦", ["p(o-tol)3", "tri-o-tolylphosphine"], "C21H21P", "6163-58-2"),
    ("三乙胺(TEA)", ["Triethylamine (TEA)", "et3n", "tea", "tea base", "triethylamine", "三乙基胺"], "C6H15N", "121-44-8"),
    ("三乙酰氧基硼氢化钠", ["nabh(oac)3", "sodium triacetoxyborohydride", "stab"], "C6H10BNNaO6", "56553-60-3"),
    ("三氟乙酸(TFA)", ["Trifluoroacetic acid (TFA)", "tfa", "trifluoroacetic acid"], "C2HF3O2", "76-05-1"),
    ("三氟乙酸酐", ["tfaa", "trifluoroacetic anhydride"], "C4F6O3", "407-25-0"),
    ("三氟化硼乙醚", ["bf3·et2o", "bf3 et2o", "boron trifluoride etherate"], "BF3.C4H10O", "109-63-7"),
    ("三氟甲苯(BTF)", ["Benzotrifluoride (BTF)"], "C7H5F3", "98-08-8"),
    ("三氯乙烯(TCE)", ["Trichloroethylene (TCE)"], "C2HCl3", "79-01-6"),
    ("三氯化磷", ["pcl3", "phosphorus trichloride"], "PCl3", "7719-12-2"),
    ("三氯化铝", ["alcl3", "aluminium chloride"], "AlCl3", "7446-70-0"),
    ("三氯氧磷", ["pocl3", "phosphoryl chloride", "磷酰氯"], "POCl3", "10025-87-3"),
    ("三溴化磷", ["pbr3", "phosphorus tribromide"], "PBr3", "7789-60-8"),
    ("三甘醇(TEG)", ["Triethylene glycol (TEG)"], "C6H14O4", "112-27-6"),
    ("三甘醇二甲醚(triglyme)", ["Triglyme"], "C8H18O4", "112-49-2"),
    ("三苯基膦", ["triphenylphosphine", "pph3", "三苯膦"], "C18H15P", "603-35-0"),
    ("丙腈(EtCN)", ["Propionitrile (EtCN)"], "C3H5N", "107-12-0"),
    ("丙酮(Me2CO)", ["Acetone (Me2CO)", "acetone", "dmk", "阿西通"], "C3H6O", "67-64-1"),
    ("丙酸乙酯(EP)", ["Ethyl propionate (EP)"], "C5H10O2", "105-37-3"),
    ("乙二胺(EDA)", ["Ethylenediamine (EDA)"], "C2H8N2", "107-15-3"),
    ("乙二醇(EG)", ["Ethylene glycol (EG)", "eg", "ethylene glycol", "甘醇"], "C2H6O2", "107-21-1"),
    ("乙腈(MeCN)", ["Acetonitrile (MeCN)", "acetonitrile", "mecn", "甲基氰"], "C2H3N", "75-05-8"),
    ("乙苯", ["Ethylbenzene"], "C8H10", "100-41-4"),
    ("乙酸(AcOH·冰醋酸)", ["Acetic acid (AcOH)", "acetic acid", "acoh", "冰醋酸", "醋酸"], "C2H4O2", "64-19-7"),
    ("乙酸丁酯(BuOAc)", ["n-Butyl acetate (BuOAc)"], "C6H12O2", "123-86-4"),
    ("乙酸乙酯(EtOAc)", ["Ethyl acetate (EtOAc)", "ea", "ethyl acetate", "etoac", "醋酸乙酯"], "C4H8O2", "141-78-6"),
    ("乙酸异丙酯(i-PrOAc)", ["Isopropyl acetate (i-PrOAc)"], "C5H10O2", "108-21-4"),
    ("乙酸异戊酯(i-AmOAc·香蕉水主成分)", ["Isoamyl acetate (i-AmOAc)"], "C7H14O2", "123-92-2"),
    ("乙酸甲酯(MeOAc)", ["Methyl acetate (MeOAc)"], "C3H6O2", "79-20-9"),
    ("乙酸酐(Ac2O)", ["Acetic anhydride (Ac2O)", "ac2o", "acetic anhydride", "醋酸酐"], "C4H6O3", "108-24-7"),
    ("乙酸铵", ["nh4oac", "ammonium acetate", "醋酸铵"], "C2H7NO2", "631-61-8"),
    ("乙醇(EtOH)", ["Ethanol (EtOH)", "ethanol", "etoh", "无水乙醇", "酒精"], "C2H6O", "64-17-5"),
    ("乙醇钠", ["sodium ethoxide", "naoet", "乙氧基钠"], "C2H5NaO", "141-52-6"),
    ("乙醚(Et2O)", ["Diethyl ether (Et2O)", "diethyl ether", "et2o", "ether", "二乙醚"], "C4H10O", "60-29-7"),
    ("二乙二醇二甲醚(diglyme·二甘醚)", ["Diethylene glycol dimethyl ether (diglyme)"], "C6H14O3", "111-96-6"),
    ("二异丙基乙胺(DIPEA·Hünig碱)", ["N,N-Diisopropylethylamine (DIPEA)", "diea", "hunig base", "hunig's base", "二异丙基乙胺"], "C8H19N", "7087-68-5"),
    ("二异丙醚(DIPE)", ["Diisopropyl ether (DIPE)"], "C6H14O", "108-20-3"),
    ("二氯甲烷(DCM)", ["Dichloromethane (DCM)", "dcm", "dichloromethane", "亚甲基氯"], "CH2Cl2", "75-09-2"),
    ("二甘醇(DEG)", ["Diethylene glycol (DEG)"], "C4H10O3", "111-46-6"),
    ("二甲亚砜(DMSO)", ["Dimethyl sulfoxide (DMSO)", "dimethyl sulfoxide", "dmso", "二甲基亚砜"], "C2H6OS", "67-68-5"),
    ("二甲苯(混合·Xyl)", ["Xylene (mixed, Xyl)", "xylene", "二甲苯类"], "C8H10", "1330-20-7"),
    ("二硫化碳", ["Carbon disulfide"], "CS2", "75-15-0"),
    ("二苯醚(Ph2O)", ["Diphenyl ether (Ph2O)"], "C12H10O", "101-84-8"),
    ("五氯化磷", ["pcl5", "phosphorus pentachloride"], "PCl5", "10026-13-8"),
    ("仲丁醇(s-BuOH)", ["2-Butanol (s-BuOH)"], "C4H10O", "78-92-2"),
    ("保险粉", ["连二亚硫酸钠", "sodium dithionite", "na2s2o4"], "Na2O4S2", "7775-14-6"),
    ("六氟异丙醇(HFIP)", ["Hexafluoroisopropanol (HFIP)"], "C3H2F6O", "920-66-1"),
    ("分子筛", ["molecular sieves", "4a分子筛"], "Na2O.Al2O3.2SiO2", "70955-01-0"),
    ("十氢萘(萘烷)", ["Decalin"], "C10H18", "91-17-8"),
    ("双氧水", ["h2o2", "hydrogen peroxide", "过氧化氢"], "H2O2", "7722-84-1"),
    ("叔丁醇(t-BuOH)", ["2-甲基-2-丙醇", "t-butanol", "tba", "tert-Butanol (t-BuOH)"], "C4H10O", "75-65-0"),
    ("叔丁醇钠", ["sodium tert-butoxide", "naotbu"], "C4H9NaO", "865-48-5"),
    ("叔丁醇钾", ["potassium tert-butoxide", "kotbu", "t-buok", "tbuok"], "C4H9KO", "865-47-4"),
    ("吗啉", ["Morpholine", "morpholine"], "C4H9NO", "110-91-8"),
    ("吡啶(Py)", ["Pyridine (Py)", "pyr", "pyridine", "氮杂苯"], "C5H5N", "110-86-1"),
    ("咪唑", ["imidazole"], "C3H4N2", "288-32-4"),
    ("哌啶(Pip)", ["Piperidine (Pip)", "piperidine"], "C5H11N", "110-89-4"),
    ("喹啉", ["Quinoline"], "C9H7N", "91-22-5"),
    ("四丁基溴化铵", ["tbab", "tetrabutylammonium bromide", "bu4nbr"], "C16H36BrN", "1643-19-2"),
    ("四丁基碘化铵", ["tbai", "tetrabutylammonium iodide", "bu4ni"], "C16H36IN", "311-28-4"),
    ("四三苯基膦钯", ["pd(pph3)4", "tetrakis(triphenylphosphine)palladium(0)", "四(三苯基膦)钯"], "C72H60P4Pd", "14221-01-3"),
    ("四氢呋喃(THF)", ["Tetrahydrofuran (THF)", "tetrahydrofuran", "thf", "四氢呋喃"], "C4H8O", "109-99-9"),
    ("四氯化碳(CTC)", ["Carbon tetrachloride (CTC)"], "CCl4", "56-23-5"),
    ("四氯化钛", ["ticl4", "titanium tetrachloride"], "TiCl4", "7550-45-0"),
    ("四氯化锡", ["sncl4", "tin tetrachloride"], "SnCl4", "7646-78-8"),
    ("均三甲苯(Mes)", ["Mesitylene (Mes)"], "C9H12", "108-67-8"),
    ("对二甲苯(p-Xyl)", ["p-Xylene"], "C8H10", "106-42-3"),
    ("对甲苯硼酸", ["p-tolylboronic acid", "4-甲基苯硼酸"], "C7H9BO2", "5720-05-0"),
    ("对甲苯磺酰氯", ["tscl", "tosyl chloride", "p-toluenesulfonyl chloride", "tscl"], "C7H7ClO2S", "98-59-9"),
    ("对甲苯磺酸", ["ptsa", "p-toluenesulfonic acid", "tsoh"], "C7H8O3S", "104-15-4"),
    ("尿素", ["urea", "脲"], "CH4N2O", "57-13-6"),
    ("异丁醇(i-BuOH)", ["Isobutanol (i-BuOH)"], "C4H10O", "78-83-1"),
    ("异丙醇(IPA)", ["2-丙醇", "Isopropanol (IPA)", "ipa", "isopropanol", "异丙基醇"], "C3H8O", "67-63-0"),
    ("异辛烷(2,2,4-三甲基戊烷)", ["Isooctane"], "C8H18", "540-84-1"),
    ("戴斯-马丁氧化剂", ["dess-martin periodinane", "dmp", "dess martin"], "C13H13IO8", "27507-45-9"),
    ("次氯酸钠", ["naocl", "sodium hypochlorite", "漂白水"], "NaClO", "7681-52-9"),
    ("正丁基锂", ["n-buli", "nbuli", "butyllithium", "丁基锂"], "C4H9Li", "109-72-8"),
    ("正丁醇(n-BuOH)", ["1-丁醇", "buoh", "n-Butanol (n-BuOH)", "n-butanol", "丁醇"], "C4H10O", "71-36-3"),
    ("正丙醇(n-PrOH)", ["1-Propanol (n-PrOH)"], "C3H8O", "71-23-8"),
    ("正己烷", ["hexane", "n-Hexane", "n-hexane", "己烷"], "C6H14", "110-54-3"),
    ("正庚烷", ["heptane", "n-Heptane", "n-heptane"], "C7H16", "142-82-5"),
    ("正戊烷", ["n-Pentane"], "C5H12", "109-66-0"),
    ("正戊醇(n-AmOH)", ["1-Pentanol (n-AmOH)"], "C5H12O", "71-41-0"),
    ("氟化钾", ["kf", "potassium fluoride"], "KF", "7789-23-3"),
    ("氟化铯", ["csf", "cesium fluoride"], "CsF", "13400-13-0"),
    ("氢化钙", ["cah2", "calcium hydride"], "CaH2", "7789-78-8"),
    ("氢化钠", ["nah", "sodium hydride"], "NaH", "7646-69-7"),
    ("氢化钾", ["kh", "potassium hydride"], "KH", "7693-26-7"),
    ("氢化铝锂", ["lialh4", "lah", "lithium aluminium hydride", "四氢铝锂"], "LiAlH4", "16853-85-3"),
    ("氢氧化钠", ["naoh", "sodium hydroxide", "烧碱", "火碱"], "NaOH", "1310-73-2"),
    ("氢氧化钾", ["koh", "potassium hydroxide"], "KOH", "1310-58-3"),
    ("氢溴酸", ["hbr", "hydrobromic acid"], "HBr", "10035-10-6"),
    ("氧气", ["oxygen", "o2"], "O2", "7782-44-7"),
    ("氨水", ["ammonia water", "nh3·h2o", "氢氧化铵", "ammonium hydroxide"], "NH3.H2O", "1336-21-6"),
    ("氯仿", ["Chloroform", "chcl3", "chloroform", "三氯甲烷"], "CHCl3", "67-66-3"),
    ("氯化亚砜", ["socl2", "thionyl chloride", "亚硫酰氯"], "SOCl2", "7719-09-7"),
    ("氯化钙", ["cacl2", "calcium chloride"], "CaCl2", "10043-52-4"),
    ("氯化钠", ["nacl", "sodium chloride", "食盐"], "NaCl", "7647-14-5"),
    ("氯化钯", ["pdcl2", "palladium chloride"], "PdCl2", "7647-10-1"),
    ("氯化铁", ["fecl3", "ferric chloride", "三氯化铁"], "FeCl3", "7705-08-0"),
    ("氯化锂", ["licl", "lithium chloride"], "LiCl", "7447-41-8"),
    ("氯化锌", ["zncl2", "zinc chloride"], "ZnCl2", "7646-85-7"),
    ("氯苯(PhCl)", ["Chlorobenzene (PhCl)", "chlorobenzene"], "C6H5Cl", "108-90-7"),
    ("氰基硼氢化钠", ["nabh3cn", "sodium cyanoborohydride"], "CH3BNNa", "25895-60-7"),
    ("水", ["Water", "h2o", "water", "纯水"], "H2O", "7732-18-5"),
    ("活性炭", ["activated carbon", "charcoal", "碳粉"], "C", "7440-44-0"),
    ("液氨", ["liquid ammonia", "nh3"], "NH3", "7664-41-7"),
    ("溴仿", ["Bromoform"], "CHBr3", "75-25-2"),
    ("溴化钾", ["kbr", "potassium bromide"], "KBr", "7758-02-3"),
    ("溴化锂", ["libr", "lithium bromide"], "LiBr", "7550-35-8"),
    ("溴化锌", ["znbr2", "zinc bromide"], "ZnBr2", "7699-45-8"),
    ("溴素", ["br2", "bromine", "液溴"], "Br2", "7726-95-6"),
    ("环丁砜", ["Sulfolane"], "C4H8O2S", "126-33-0"),
    ("环己烷", ["Cyclohexane", "cyclohexane", "环己烷"], "C6H12", "110-82-7"),
    ("环己酮", ["Cyclohexanone"], "C6H10O", "108-94-1"),
    ("环戊基甲醚(CPME)", ["Cyclopentyl methyl ether (CPME)"], "C6H12O", "5614-37-9"),
    ("甘油", ["Glycerol"], "C3H8O3", "56-81-5"),
    ("甲基叔丁基醚(MTBE)", ["Methyl tert-butyl ether (MTBE)", "methyl tert-butyl ether", "mtbe", "甲基叔丁基醚"], "C5H12O", "1634-04-4"),
    ("甲基异丁基酮(MIBK)", ["4-Methyl-2-pentanone (MIBK)"], "C6H12O", "108-10-1"),
    ("甲基环己烷(MCH)", ["Methylcyclohexane (MCH)"], "C7H14", "108-87-2"),
    ("甲磺酰氯", ["mscl", "methanesulfonyl chloride", "mesyl chloride"], "CH3ClO2S", "124-63-0"),
    ("甲磺酸", ["methanesulfonic acid", "msoh", "msa"], "CH4O3S", "75-75-2"),
    ("甲苯(Tol)", ["Toluene (Tol)", "toluene", "甲基苯"], "C7H8", "108-88-3"),
    ("甲酰胺", ["Formamide"], "CH3NO", "75-12-7"),
    ("甲酸(HCOOH)", ["Formic acid (HCOOH)", "formic acid", "hcooh"], "CH2O2", "64-18-6"),
    ("甲醇(MeOH)", ["Methanol (MeOH)", "ch3oh", "meoh", "methanol", "木醇"], "CH4O", "67-56-1"),
    ("甲醇钠", ["sodium methoxide", "naome", "nome", "甲氧化钠"], "CH3NaO", "124-41-4"),
    ("甲醛", ["formaldehyde", "福尔马林", "hcho"], "CH2O", "50-00-0"),
    ("盐酸", ["hcl", "hydrochloric acid", "氢氯酸", "氯化氢"], "HCl", "7647-01-0"),
    ("石油醚(PE)", ["Petroleum ether (PE)", "pet ether", "petroleum ether"], "混合烷烃", "8032-32-4"),
    ("硅胶", ["silica gel", "sio2", "二氧化硅"], "SiO2", "7631-86-9"),
    ("硝基甲烷(MeNO2)", ["Nitromethane (MeNO2)"], "CH3NO2", "75-52-5"),
    ("硝基苯(PhNO2)", ["Nitrobenzene (PhNO2)", "nitrobenzene"], "C6H5NO2", "98-95-3"),
    ("硝酸", ["hno3", "nitric acid"], "HNO3", "7697-37-2"),
    ("硝酸银", ["agno3", "silver nitrate"], "AgNO3", "7761-88-8"),
    ("硫代硫酸钠", ["na2s2o3", "sodium thiosulfate", "大苏打"], "Na2O3S2", "7772-98-7"),
    ("硫脲", ["thiourea"], "CH4N2S", "62-56-6"),
    ("硫酸", ["h2so4", "sulfuric acid"], "H2SO4", "7664-93-9"),
    ("硫酸钠", ["na2so4", "sodium sulfate"], "Na2SO4", "7757-82-6"),
    ("硫酸铜", ["cuso4", "copper sulfate", "五水硫酸铜"], "CuSO4", "7758-98-7"),
    ("硫酸镁", ["mgso4", "magnesium sulfate", "无水硫酸镁"], "MgSO4", "7487-88-9"),
    ("硼氢化钠", ["nabh4", "sodium borohydride"], "NaBH4", "16940-66-2"),
    ("硼氢化钾", ["kbh4", "potassium borohydride"], "KBH4", "13762-51-1"),
    ("硼酸", ["b(oh)3", "boric acid", "h3bo3"], "H3BO3", "10043-35-3"),
    ("碘", ["i2", "iodine", "碘单质"], "I2", "7553-56-2"),
    ("碘化钠", ["nai", "sodium iodide"], "NaI", "7681-82-5"),
    ("碘化钾", ["ki", "potassium iodide"], "KI", "7681-11-0"),
    ("碘化铵", ["nh4i", "ammonium iodide"], "H4IN", "12027-06-4"),
    ("碳酸丙烯酯(PC)", ["Propylene carbonate (PC)"], "C4H6O3", "108-32-7"),
    ("碳酸二甲酯(DMC)", ["Dimethyl carbonate (DMC)"], "C3H6O3", "616-38-6"),
    ("碳酸氢钠", ["nahco3", "sodium bicarbonate", "小苏打"], "NaHCO3", "144-55-8"),
    ("碳酸氢钾", ["khco3", "potassium bicarbonate"], "KHCO3", "298-14-6"),
    ("碳酸钠", ["na2co3", "sodium carbonate", "纯碱"], "Na2CO3", "497-19-8"),
    ("碳酸钾", ["k2co3", "potassium carbonate"], "K2CO3", "584-08-3"),
    ("碳酸铯", ["cs2co3", "cesium carbonate"], "Cs2CO3", "534-17-4"),
    ("磷酸", ["h3po4", "phosphoric acid"], "H3PO4", "7664-38-2"),
    ("磷酸钾", ["k3po4", "tripotassium phosphate"], "K3PO4", "7778-53-2"),
    ("红铝", ["red-al", "sodium bis(2-methoxyethoxy)aluminum hydride", "vitr"], "C6H16AlNaO4", "22722-98-1"),
    ("联硼酸频那醇酯", ["b2pin2", "bis(pinacolato)diboron", "双联频哪醇硼酸酯"], "C12H24B2O4", "73183-34-3"),
    ("臭氧", ["ozone", "o3"], "O3", "10028-15-6"),
    ("苄醇(BnOH·苯甲醇)", ["Benzyl alcohol (BnOH)"], "C7H8O", "100-51-6"),
    ("苯(PhH)", ["Benzene (PhH)", "benzene", "苯环"], "C6H6", "71-43-2"),
    ("苯甲酸乙酯(EtOBz)", ["Ethyl benzoate (EtOBz)"], "C9H10O2", "93-89-0"),
    ("苯甲醚(PhOMe)", ["Anisole (PhOMe)"], "C7H8O", "100-66-3"),
    ("苯甲醛", ["benzaldehyde"], "C7H6O", "100-52-7"),
    ("苯硼酸", ["phenylboronic acid", "phb(oh)2"], "C6H7BO2", "98-80-6"),
    ("苯磺酰氯", ["benzenesulfonyl chloride", "bscl"], "C6H5ClO2S", "98-09-9"),
    ("苯胺", ["aniline", "氨基苯"], "C6H7N", "62-53-3"),
    ("苯酚", ["phenol", "石炭酸"], "C6H6O", "108-95-2"),
    ("草酰氯", ["(cocl)2", "oxalyl chloride", "乙二酰氯"], "C2Cl2O2", "79-37-8"),
    ("过硫酸钾", ["k2s2o8", "potassium persulfate"], "K2O8S2", "7727-21-1"),
    ("邻二甲苯(o-Xyl)", ["o-Xylene"], "C8H10", "95-47-6"),
    ("醋酸碘苯", ["pida", "phli(oac)2", "iodobenzene diacetate"], "C10H13IO4", "7241-98-7"),
    ("醋酸钠", ["naoac", "sodium acetate", "乙酸钠"], "C2H3NaO2", "127-09-3"),
    ("醋酸钯", ["pd(oac)2", "palladium acetate", "乙酸钯"], "C4H6O4Pd", "3375-31-3"),
    ("醋酸钾", ["koac", "potassium acetate", "乙酸钾"], "C2H3KO2", "127-08-2"),
    ("重铬酸钾", ["k2cr2o7", "potassium dichromate"], "K2Cr2O7", "7778-50-9"),
    ("铁粉", ["iron", "fe", "铁"], "Fe", "7439-89-6"),
    ("锌粉", ["zinc", "zn", "锌"], "Zn", "7440-66-6"),
    ("锰粉", ["manganese", "mn"], "Mn", "7439-96-5"),
    ("镁屑", ["magnesium", "mg", "镁"], "Mg", "7439-95-4"),
    ("间二甲苯(m-Xyl)", ["m-Xylene"], "C8H10", "108-38-3"),
    ("频哪醇硼烷", ["hbpin", "pinacolborane"], "C6H13BO2", "25015-63-8"),
    ("高锰酸钾", ["kmno4", "potassium permanganate"], "KMnO4", "7722-64-7"),
]

# ---------------------------------------------------------------- 分类
# 是否溶剂：以 CAS 是否带物性数据判定（物性源自工具箱溶剂表；
# 纯试剂条目 polarity/bp/density 均为空）。用 CAS 而非中文名，
# 避免「乙醇」→「乙醇(EtOH)」这类合并改名导致失配。
# 溶剂 98 种 / 共 233 种
SOLVENT_CAS = {
    "100-41-4", "100-51-6", "100-66-3", "101-84-8", "105-37-3", "106-42-3",
    "107-06-2", "107-12-0", "107-15-3", "107-21-1", "107-87-9", "108-10-1",
    "108-20-3", "108-21-4", "108-24-7", "108-32-7", "108-38-3", "108-48-5",
    "108-67-8", "108-87-2", "108-88-3", "108-90-7", "108-94-1", "109-66-0",
    "109-86-4", "109-99-9", "110-54-3", "110-71-4", "110-82-7", "110-86-1",
    "110-89-4", "110-91-8", "111-46-6", "111-96-6", "112-27-6", "112-49-2",
    "121-44-8", "123-86-4", "123-91-1", "123-92-2", "126-33-0", "127-19-5",
    "1330-20-7", "141-78-6", "142-82-5", "1634-04-4", "540-84-1", "56-23-5",
    "56-81-5", "5614-37-9", "60-29-7", "616-38-6", "64-17-5", "64-18-6",
    "64-19-7", "67-56-1", "67-63-0", "67-64-1", "67-66-3", "67-68-5",
    "68-12-2", "680-31-9", "7087-68-5", "71-23-8", "71-36-3", "71-41-0",
    "71-43-2", "71-55-6", "7226-23-5", "75-05-8", "75-09-2", "75-12-7",
    "75-15-0", "75-25-2", "75-52-5", "75-65-0", "75-89-8", "76-05-1",
    "7732-18-5", "78-83-1", "78-92-2", "78-93-3", "79-01-6", "79-20-9",
    "80-73-9", "8032-32-4", "872-50-4", "91-17-8", "91-22-5", "920-66-1",
    "93-89-0", "95-47-6", "95-50-1", "96-22-0", "96-47-9", "96-48-0",
    "98-08-8", "98-95-3",
}

# ---------------------------------------------------------------- 索引

_BY_CAS = {r[3]: r for r in COMMON_REAGENTS}
_BY_NAME = {r[0]: r for r in COMMON_REAGENTS}
_BY_ALIAS = {}


def _short_name(name: str) -> str:
    """取括号前的主名：「乙醇(EtOH)」→「乙醇」。

    合并后的 name 常带英文缩写后缀（源自工具箱的命名习惯），
    但用户输入「乙醇」时也应能查到，因此主名单独建索引。
    """
    if "(" in name:
        return name.split("(", 1)[0].strip()
    return name.strip()


for _r in COMMON_REAGENTS:
    for _a in _r[1]:
        _BY_ALIAS.setdefault(_a.lower(), _r)
    # 主名（去括号后缀）也纳入别名索引，大小写不敏感
    _sn = _short_name(_r[0])
    if _sn:
        _BY_ALIAS.setdefault(_sn.lower(), _r)


def get_reagent(key: str):
    """按中文名/英文/别名/CAS 查找试剂，返回 (name, aliases, formula, cas) 或 None。

    匹配顺序：CAS → 完整名 → 别名/主名（大小写不敏感）。
    """
    if not key:
        return None
    k = key.strip()
    if k in _BY_CAS:
        return _BY_CAS[k]
    if k in _BY_NAME:
        return _BY_NAME[k]
    low = k.lower()
    if low in _BY_ALIAS:
        return _BY_ALIAS[low]
    return None



# ---------------------------------------------------------------- 分子量计算
# Atomic weights for formula parsing
ATOMIC_WEIGHTS = {
    "H": 1.008, "D": 2.014, "He": 4.003, "Li": 6.94, "Be": 9.012,
    "B": 10.81, "C": 12.011, "N": 14.007, "O": 15.999, "F": 18.998,
    "Ne": 20.180, "Na": 22.990, "Mg": 24.305, "Al": 26.982, "Si": 28.085,
    "P": 30.974, "S": 32.06, "Cl": 35.45, "Ar": 39.948, "K": 39.098,
    "Ca": 40.078, "Ti": 47.867, "V": 50.942, "Cr": 51.996, "Mn": 54.938,
    "Fe": 55.845, "Co": 58.933, "Ni": 58.693, "Cu": 63.546, "Zn": 65.38,
    "Ga": 69.723, "Ge": 72.630, "As": 74.922, "Se": 78.971, "Br": 79.904,
    "Kr": 83.798, "Rb": 85.468, "Sr": 87.62, "Y": 88.906, "Zr": 91.224,
    "Nb": 92.906, "Mo": 95.95, "Ru": 101.07, "Rh": 102.91, "Pd": 106.42,
    "Ag": 107.87, "Cd": 112.41, "In": 114.82, "Sn": 118.71, "Sb": 121.76,
    "Te": 127.60, "I": 126.90, "Xe": 131.29, "Cs": 132.91, "Ba": 137.33,
    "La": 138.91, "Ce": 140.12, "Eu": 151.96, "Yb": 173.05, "Lu": 174.97,
    "Hf": 178.49, "Ta": 180.95, "W": 183.84, "Re": 186.21, "Os": 190.23,
    "Ir": 192.22, "Pt": 195.08, "Au": 196.97, "Hg": 200.59, "Tl": 204.38,
    "Pb": 207.2, "Bi": 208.98, "Th": 232.04, "U": 238.03,
}


def formula_mw(formula: str):
    """Compute molecular weight from a chemical formula string.

    Supports parentheses and hydrate dots, e.g. CuSO4.5H2O, Fe2(SO4)3.
    Returns float or None if unparseable.
    """
    if not formula:
        return None
    formula = formula.strip()

    def parse_segment(seg):
        total = 0.0
        i = 0
        while i < len(seg):
            ch = seg[i]
            if ch in "([":
                depth = 1
                j = i + 1
                while j < len(seg) and depth > 0:
                    if seg[j] in "([":
                        depth += 1
                    elif seg[j] in ")]":
                        depth -= 1
                    j += 1
                if depth != 0:
                    return None
                inner = parse_segment(seg[i + 1:j - 1])
                if inner is None:
                    return None
                # count following digits
                k = j
                num = ""
                while k < len(seg) and seg[k].isdigit():
                    num += seg[k]
                    k += 1
                total += inner * (int(num) if num else 1)
                i = k
            elif ch.isupper():
                sym = ch
                j = i + 1
                while j < len(seg) and seg[j].islower():
                    sym += seg[j]
                    j += 1
                if sym not in ATOMIC_WEIGHTS:
                    return None
                num = ""
                while j < len(seg) and (seg[j].isdigit() or seg[j] == "."):
                    if seg[j] == "." and not seg[j:j + 1].isdigit():
                        break
                    num += seg[j]
                    j += 1
                total += ATOMIC_WEIGHTS[sym] * (float(num) if num else 1.0)
                i = j
            else:
                return None
        return total

    # Split hydrates: CuSO4·5H2O / CuSO4.5H2O / Na2O.Al2O3.2SiO2
    total = 0.0
    for sep in ("·", "*"):
        formula = formula.replace(sep, ".")
    parts = formula.split(".")
    for idx, part in enumerate(parts):
        part = part.strip()
        if not part:
            return None
        # hydrate multiplier: leading integer
        mult = 1
        j = 0
        while j < len(part) and part[j].isdigit():
            j += 1
        if j > 0 and j < len(part) and part[j].isupper():
            mult = int(part[:j])
            part = part[j:]
        seg_mw = parse_segment(part)
        if seg_mw is None:
            return None
        total += seg_mw * mult

    return round(total, 3) if total > 0 else None


def _build_index():
    """Build alias -> entry lookup (lowercased)."""
    index = {}
    for name, aliases, formula, cas in COMMON_REAGENTS:
        entries = [name] + list(aliases)
        # 主名（去括号后缀）也进索引，保证「乙醇」能命中「乙醇(EtOH)」
        sn = _short_name(name)
        if sn:
            entries.append(sn)
        for a in entries:
            key = a.strip().lower()
            if key and key not in index:
                index[key] = (name, formula, cas)
    return index


_ALIAS_INDEX = _build_index()


def lookup_common_reagent(query: str):
    """Look up a reagent by name/alias/formula. Returns dict or None."""
    q = (query or "").strip()
    if not q:
        return None
    key = q.lower()
    # 1. exact alias match
    if key in _ALIAS_INDEX:
        name, formula, cas = _ALIAS_INDEX[key]
        mw = formula_mw(formula)
        if mw:
            return {"found": True, "source": "common", "name": name,
                    "formula": formula, "mw": mw, "cas": cas}
    # 2. try as a bare chemical formula, e.g. K2CO3, FeCl3, CuSO4.5H2O
    if any(c.isdigit() for c in q) and any(c.isalpha() for c in q):
        mw = formula_mw(q)
        if mw:
            return {"found": True, "source": "formula", "name": q,
                    "formula": q, "mw": mw, "cas": ""}
    # 3. partial match (contains), only for aliases of decent length
    for k, (name, formula, cas) in _ALIAS_INDEX.items():
        if len(k) >= 3 and len(key) >= 3 and (key in k or k in key):
            mw = formula_mw(formula)
            if mw:
                return {"found": True, "source": "common", "name": name,
                        "formula": formula, "mw": mw, "cas": cas}
    return None


def get_seeded_common_compounds():
    """Return built-in solvent/reagent entries as seed rows.

    Each row: (name, cas, formula, mw, category)
    category is 'solvent' if the CAS carries 物性数据（源自工具箱溶剂表）,
    otherwise 'reagent'.
    """
    rows = []
    for name, aliases, formula, cas in COMMON_REAGENTS:
        mw = formula_mw(formula)
        if mw is None:
            continue
        category = "solvent" if cas in SOLVENT_CAS else "reagent"
        rows.append((name, cas, formula, mw, category))
    return rows


if __name__ == "__main__":
    tests = ["乙醇", "NaOH", "K2CO3", "苯硼酸", "DCM", "MeOH", "Pd(PPh3)4",
             "CuSO4.5H2O", "Fe2(SO4)3", "THF", "HATU", "nabh4", "水"]
    for t in tests:
        print(f"{t:15s} =>", lookup_common_reagent(t))
