"""
Ethnicity module for Climate-Action-GABM.
"""
# Metadata
__author__ = ["Andy Turner <agdturner@gmail.com>"]
__version__ = "0.9.1"
__copyright__ = "Copyright (c) 2026 Climate-Action-GABM contributors, University of Leeds"

from gabm.abm.attribute import GABMAttributeID, GABMAttribute, GABMAttributeMap


class EthnicityID(GABMAttributeID):
    """Identifier for the survey's ethnicity categories."""

    def __init__(self, ethnicity_id: int):
        super().__init__(ethnicity_id)


class Ethnicity(GABMAttribute):
    """An ethnicity category and its persona description."""

    def __init__(self, ethnicity_id: EthnicityID, description: str):
        super().__init__(ethnicity_id, description)

EthnicityID.UNKNOWN = EthnicityID(0)
EthnicityID.WHITE = EthnicityID(1)
EthnicityID.ASIAN = EthnicityID(2)
EthnicityID.BLACK = EthnicityID(3)
EthnicityID.MIXED = EthnicityID(4)
EthnicityID.OTHER = EthnicityID(5)

class SurveyEthnicityMap(GABMAttributeMap):
    """
    A mapping of EthnicityIds to Ethnicity.

    By default, the map is initialized as follows::

        items: Dict[EthnicityID, Ethnicity] = {
            EthnicityID.UNKNOWN: Ethnicity(EthnicityID.UNKNOWN, "unknown"),
            EthnicityID.WHITE: Ethnicity(EthnicityID.WHITE, "white"),
            EthnicityID.ASIAN: Ethnicity(EthnicityID.ASIAN, "asian"),
            EthnicityID.BLACK: Ethnicity(EthnicityID.BLACK, "black"),
            EthnicityID.MIXED: Ethnicity(EthnicityID.MIXED, "mixed"),
            EthnicityID.OTHER: Ethnicity(EthnicityID.OTHER, "other")
        }
        super().__init__(items)
    """
    def __init__(self):
        """
        Initialize the Ethnicities object.
        """
        items: Dict[EthnicityID, Ethnicity] = {
            EthnicityID.UNKNOWN: Ethnicity(EthnicityID.UNKNOWN, "unknown"),
            EthnicityID.WHITE: Ethnicity(EthnicityID.WHITE, "white"),
            EthnicityID.ASIAN: Ethnicity(EthnicityID.ASIAN, "asian"),
            EthnicityID.BLACK: Ethnicity(EthnicityID.BLACK, "black"),
            EthnicityID.MIXED: Ethnicity(EthnicityID.MIXED, "mixed"),
            EthnicityID.OTHER: Ethnicity(EthnicityID.OTHER, "other")
        }
        super().__init__(items)