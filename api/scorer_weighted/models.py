# TODO: remove pylint skip once circular dependency removed
# pylint: disable=import-outside-toplevel
import logging
from typing import List, Union, Optional
from decimal import Decimal

from django.conf import settings
from django.db import models

log = logging.getLogger(__name__)

from ninja_schema import Schema


class ThresholdScoreEvidence:
    def __init__(self, success: bool, rawScore: Decimal, threshold: Decimal):
        self.type = "ThresholdScoreCheck"
        self.success = success
        self.rawScore = rawScore
        self.threshold = threshold


class ScoreData:
    # do multiple evidence types like:
    # Optional[List[Union[ThresholdScoreEvidence, RequiredStampEvidence]]]
    def __init__(
        self, score: Decimal, evidence: Optional[List[ThresholdScoreEvidence]]
    ):
        self.score = score
        self.evidence = evidence


def get_default_weights():
    """
    This function shall provide the default weights for the default scorer.
    It will load the weights from the settings
    """
    return settings.GITCOIN_PASSPORT_WEIGHTS


class Scorer(models.Model):
    class Type(models.TextChoices):
        WEIGHTED = "WEIGHTED", "Weighted"
        WEIGHTED_BINARY = "WEIGHTED_BINARY", "Weighted Binary"

    type = models.CharField(
        choices=Type.choices,
        default=Type.WEIGHTED,
        max_length=100,
    )

    def compute_score(self) -> List[ScoreData]:
        """Compute the score. This shall be overridden in child classes"""
        raise NotImplemented()


class WeightedScorer(Scorer):
    weights = models.JSONField(default=get_default_weights, blank=True, null=True)

    def compute_score(self, passport_ids) -> List[ScoreData]:
        """
        Compute the weighted score for the passports identified by `ids`
        Note: the `ids` are not validated. The caller shall ensure that these are indeed proper IDs, from the correct community
        """
        from .computation import calculate_weighted_score

        return [
            ScoreData(score=s, evidence=None)
            for s in calculate_weighted_score(self, passport_ids)
        ]


class BinaryWeightedScorer(Scorer):
    weights = models.JSONField(default=get_default_weights, blank=True, null=True)
    threshold = models.DecimalField(max_digits=10, decimal_places=5)

    def compute_score(self, passport_ids) -> List[ScoreData]:
        """
        Compute the weighted score for the passports identified by `ids`
        Note: the `ids` are not validated. The caller shall ensure that these are indeed proper IDs, from the correct community
        """
        from .computation import calculate_weighted_score

        rawScores = calculate_weighted_score(self, passport_ids)
        binaryScores = [
            Decimal(1) if s >= self.threshold else Decimal(0) for s in rawScores
        ]

        return list(
            map(
                lambda rawScore, binaryScore: ScoreData(
                    score=binaryScore,
                    evidence=list(
                        [
                            ThresholdScoreEvidence(
                                threshold=Decimal(str(self.threshold)),
                                rawScore=Decimal(rawScore),
                                success=bool(binaryScore),
                            )
                        ]
                    ),
                ),
                rawScores,
                binaryScores,
            )
        )
