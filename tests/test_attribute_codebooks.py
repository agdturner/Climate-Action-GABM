"""Survey codebooks reuse GABM machinery without modifying its codebooks."""

import hashlib
import json
import subprocess
import sys

import pytest

from gabm.abm.attribute import GABMAttributeID, GABMAttributeMap
from gabm.abm.attributes.education import EducationID as GenericEducationID
from gabm.abm.attributes.income import IncomeID as GenericIncomeID
from gabm.abm.attributes.region import RegionID as GenericRegionID

from cag.abm.attributes.education import EducationID, SurveyEducationMap
from cag.abm.attributes.income import IncomeID, SurveyIncomeMap
from cag.abm.attributes.region import RegionID, UKRegionMap


@pytest.mark.parametrize(
    ("id_type", "generic_id_type", "map_type", "size", "fingerprint"),
    [
        (EducationID, GenericEducationID, SurveyEducationMap, 19,
         "3e46478070704b5fb88415db4dac3b88ae8eca04ae0f7d33b74f0983d042c16b"),
        (IncomeID, GenericIncomeID, SurveyIncomeMap, 16,
         "db539f1192abfd2d422f84a05c7ceec9791bbf1f09d168308e0f6bbac17993d6"),
        (RegionID, GenericRegionID, UKRegionMap, 14,
         "04d7416e607b5265e6bbef79e327ab8ccc62a960a3ac8d6675600e824f089dda"),
    ],
)
def test_survey_codebook_preserves_exact_codes_descriptions_and_order(
    id_type, generic_id_type, map_type, size, fingerprint,
):
    codebook = map_type()
    assert isinstance(codebook, GABMAttributeMap)
    assert issubclass(id_type, GABMAttributeID)
    assert id_type is not generic_id_type
    entries = [
        (key.id, attribute.id.id, attribute.description)
        for key, attribute in codebook.items()
    ]
    assert len(entries) == size
    assert hashlib.sha256(json.dumps(entries, ensure_ascii=True).encode()).hexdigest() == fingerprint
    for key, attribute in codebook.items():
        assert type(key) is id_type
        assert attribute.id is key
        assert codebook[id_type(key.id)] is attribute
        assert codebook.get(generic_id_type(key.id)) is None
        assert key != generic_id_type(key.id)
        assert generic_id_type(key.id) != key
        assert str(key) == f"{id_type.__name__}({key.id})"


@pytest.mark.parametrize("cag_first", [False, True])
def test_cag_and_gabm_codebooks_coexist_independently_of_import_order(cag_first):
    script = """
import importlib
import json
import sys
from gabm.abm.attribute import GABMAttributeID

def snapshot(module, id_name, map_name):
    id_type = getattr(module, id_name)
    constants = {
        name: value.id for name, value in vars(id_type).items()
        if isinstance(value, GABMAttributeID)
    }
    entries = [
        (key.id, attribute.id.id, attribute.description)
        for key, attribute in getattr(module, map_name)().items()
    ]
    return constants, entries

specs = [
    ("education", "EducationID", "EducationMap"),
    ("income", "IncomeID", "IncomeMap"),
    ("region", "RegionID", "RegionMap"),
]
mode = sys.argv[1]
before = {}
for name, id_name, map_name in specs:
    if mode == "before":
        if mode == "after":
            importlib.import_module("cag.abm.attributes." + name)
    module = importlib.import_module("gabm.abm.attributes." + name)
    before[name] = snapshot(module, id_name, map_name)
    original_constants = {
        key: value for key, value in vars(getattr(module, id_name)).items()
        if isinstance(value, GABMAttributeID)
    }
    existing_map = getattr(module, map_name)()
    importlib.import_module("cag.abm.attributes." + name)
    assert snapshot(module, id_name, map_name) == before[name]
    for key, value in original_constants.items():
        assert getattr(getattr(module, id_name), key) is value
    for key, attribute in existing_map.items():
        assert getattr(module, map_name)()[key].description == attribute.description
print(json.dumps(before, sort_keys=True))
"""
    actual = subprocess.run(
        [sys.executable, "-c", script, "before" if cag_first else "after"],
        capture_output=True, text=True, check=True,
    )
    baseline = subprocess.run(
        [sys.executable, "-c", script, "baseline"],
        capture_output=True, text=True, check=True,
    )
    assert json.loads(actual.stdout) == json.loads(baseline.stdout)
