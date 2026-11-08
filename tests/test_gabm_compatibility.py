"""Contracts retained when adopting the published GABM 0.3 APIs."""

import pytest

from gabm.abm.attribute import GABMAttribute, GABMAttributeID, GABMAttributeMap
from gabm.abm.environment import Nation

from cag.abm.attributes.ethnicity import Ethnicity, EthnicityID, SurveyEthnicityMap
from cag.abm.attributes.family import Family, FamilyID, SurveyFamilyMap
from cag.abm.attributes.politics import Politics, PoliticsID, SurveyPoliticsMap
from cag.abm.environment import SurveyedNation


@pytest.mark.parametrize("id_type,attribute_type,map_type,size", [
    (PoliticsID, Politics, SurveyPoliticsMap, 9),
    (EthnicityID, Ethnicity, SurveyEthnicityMap, 6),
    (FamilyID, Family, SurveyFamilyMap, 3),
])
def test_survey_attribute_contract(id_type, attribute_type, map_type, size):
    mapping = map_type()
    assert isinstance(mapping, GABMAttributeMap)
    assert len(mapping) == size
    for ordinal in range(size):
        identifier = id_type(ordinal)
        assert isinstance(identifier, GABMAttributeID)
        assert identifier.id == ordinal
        assert str(identifier) == f"{id_type.__name__}({ordinal})"
        assert repr(identifier) == str(identifier)
        assert identifier == id_type(ordinal)
        assert identifier != id_type(size)
        assert identifier != GABMAttributeID(ordinal)
        assert hash(identifier) == hash(id_type(ordinal))
        attribute = mapping.get(identifier)
        assert isinstance(attribute, attribute_type)
        assert isinstance(attribute, GABMAttribute)
        assert attribute.id == identifier
        assert str(attribute) == (
            f"{attribute_type.__name__}(id={identifier}, "
            f"description='{attribute.description}')"
        )
        cloned = attribute_type(identifier, attribute.description)
        assert str(cloned) == str(attribute)
    assert mapping.get(id_type(0)).description == "unknown"
    assert mapping.get(id_type(size)) is None


def test_attribute_ids_keep_constructor_keyword_names():
    assert PoliticsID(politics_id=4) == PoliticsID.CENTRE
    assert EthnicityID(ethnicity_id=1) == EthnicityID.WHITE
    assert FamilyID(family_id=2) == FamilyID.PARENT
    assert Politics(
        politics_id=PoliticsID.CENTRE, description="centre",
    ).id == PoliticsID.CENTRE
    assert Ethnicity(
        ethnicity_id=EthnicityID.WHITE, description="white",
    ).id == EthnicityID.WHITE
    assert Family(
        family_id=FamilyID.PARENT, description="a parent",
    ).id == FamilyID.PARENT


def test_place_remains_an_alias_for_framework_name():
    nation = SurveyedNation(year=2024, place="United Kingdom")
    assert isinstance(nation, Nation)
    assert nation.year == 2024
    assert nation.place == nation.name == "United Kingdom"
    nation.place = "UK"
    assert nation.name == "UK"
    nation.name = "Britain"
    assert nation.place == "Britain"


def test_nation_preserves_supplied_survey_maps():
    ethnicity = SurveyEthnicityMap()
    politics = SurveyPoliticsMap()
    family = SurveyFamilyMap()
    nation = SurveyedNation(
        ethnicity_map=ethnicity, politics_map=politics, family_map=family,
    )
    assert nation.ethnicity_map is ethnicity
    assert nation.politics_map is politics
    assert nation.family_map is family
    assert nation.ethnicity_map.get(EthnicityID.ASIAN).description == "asian"


def test_default_ethnicity_map_uses_cag_survey_categories():
    nation = SurveyedNation()
    assert isinstance(nation.ethnicity_map, SurveyEthnicityMap)
    assert nation.ethnicity_map.get(EthnicityID.WHITE).description == "white"
    assert nation.ethnicity_map.get(EthnicityID.BLACK).description == "black"
