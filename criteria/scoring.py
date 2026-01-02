from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple


@dataclass(frozen=True)
class Criterion:
    id: str
    label: str
    points: int


@dataclass(frozen=True)
class Domain:
    id: str
    label: str
    criteria: Tuple[Criterion, ...]
    max_in_domain: bool = True
    note: Optional[str] = None


@dataclass(frozen=True)
class DomainScore:
    domain_id: str
    domain_label: str
    awarded_points: int
    awarded_criterion: Optional[Criterion]
    selected_criteria: Tuple[Criterion, ...]
    note: Optional[str] = None


@dataclass(frozen=True)
class ScoreResult:
    ana_positive: bool
    eligible: bool
    total_score: int
    meets_classification: bool
    risk_tier: str
    risk_note: str
    domain_scores: Tuple[DomainScore, ...]
    ineligible_reason: Optional[str] = None


def get_domains() -> Tuple[Domain, ...]:
    """
    EULAR/ACR 2019 config as described in main_doc.pdf (Bảng 1) including:
    - ANA entry criterion gate
    - max-in-domain rule (do not sum within a domain; take max)
    - classification threshold: total score >= 10
    - risk tiers: <10, 10-19, >=20
    """
    return (
        Domain(
            id="constitutional",
            label="Hiến pháp (Constitutional)",
            criteria=(Criterion("fever", "Sốt (>38°C)", 2),),
            max_in_domain=False,
        ),
        Domain(
            id="hematologic",
            label="Huyết học (Hematologic)",
            criteria=(
                Criterion("leukopenia", "Giảm bạch cầu (Leukopenia)", 3),
                Criterion("thrombocytopenia", "Giảm tiểu cầu (Thrombocytopenia)", 4),
                Criterion("autoimmune_hemolysis", "Tan máu tự miễn (Autoimmune hemolysis)", 4),
            ),
            max_in_domain=True,
        ),
        Domain(
            id="neuropsychiatric",
            label="Thần kinh tâm thần (Neuropsychiatric)",
            criteria=(
                Criterion("delirium", "Mê sảng (Delirium)", 2),
                Criterion("psychosis", "Loạn thần (Psychosis)", 3),
                Criterion("seizure", "Co giật (Seizure)", 5),
            ),
            max_in_domain=True,
        ),
        Domain(
            id="mucocutaneous",
            label="Da niêm mạc (Mucocutaneous)",
            criteria=(
                Criterion("nonscarring_alopecia", "Rụng tóc không sẹo", 2),
                Criterion("oral_ulcers", "Loét miệng", 2),
                Criterion("subacute_cutaneous_or_discoid", "Lupus da bán cấp / Dạng đĩa", 4),
                Criterion("acute_cutaneous", "Lupus da cấp tính", 6),
            ),
            max_in_domain=True,
        ),
        Domain(
            id="serosal",
            label="Thanh mạc (Serosal)",
            criteria=(
                Criterion("pleural_or_pericardial_effusion", "Tràn dịch màng phổi/tim", 5),
                Criterion("acute_pericarditis", "Viêm màng ngoài tim cấp", 6),
            ),
            max_in_domain=True,
        ),
        Domain(
            id="musculoskeletal",
            label="Cơ xương khớp (Musculoskeletal)",
            criteria=(Criterion("joint_involvement", "Viêm khớp / Đau khớp", 6),),
            max_in_domain=False,
        ),
        Domain(
            id="renal",
            label="Thận (Renal)",
            criteria=(
                Criterion("proteinuria", "Protein niệu > 0.5g/24h", 4),
                Criterion("renal_biopsy_class_ii_or_v", "Sinh thiết thận loại II hoặc V", 8),
                Criterion("renal_biopsy_class_iii_or_iv", "Sinh thiết thận loại III hoặc IV", 10),
            ),
            max_in_domain=True,
            note="Lưu ý: Sinh thiết loại III/IV có trọng số 10, đủ để phân loại nếu ANA (+).",
        ),
        Domain(
            id="antiphospholipid",
            label="Kháng thể Antiphospholipid",
            criteria=(
                Criterion(
                    "antiphospholipid_any",
                    "Anti-cardiolipin / Anti-β2GP1 / LAC (bất kỳ dương tính)",
                    2,
                ),
            ),
            max_in_domain=False,
        ),
        Domain(
            id="complement",
            label="Bổ thể (Complement)",
            criteria=(
                Criterion("low_c3_or_c4", "Giảm C3 HOẶC C4", 3),
                Criterion("low_c3_and_c4", "Giảm C3 VÀ C4", 4),
            ),
            max_in_domain=True,
        ),
        Domain(
            id="sle_specific_abs",
            label="Kháng thể đặc hiệu SLE",
            criteria=(Criterion("anti_dsdna_or_anti_sm", "Anti-dsDNA HOẶC Anti-Sm", 6),),
            max_in_domain=False,
        ),
    )


def _selected_criteria(dom: Domain, selections: Dict[str, bool]) -> List[Criterion]:
    return [c for c in dom.criteria if bool(selections.get(c.id))]


def _domain_award(dom: Domain, selected: List[Criterion]) -> Tuple[int, Optional[Criterion]]:
    if not selected:
        return 0, None
    if dom.max_in_domain:
        winner = max(selected, key=lambda c: c.points)
        return winner.points, winner
    # single-value domain(s)
    winner = selected[0]
    return winner.points, winner


def _risk_tier(total_score: int, eligible: bool) -> Tuple[str, str]:
    if not eligible:
        return (
            "Không đủ điều kiện tính điểm",
            "Chưa thể phân loại vì không đạt tiêu chuẩn đầu vào (ANA).",
        )
    if total_score < 10:
        return (
            "Chưa đủ tiêu chuẩn",
            "Score < 10: theo dõi thêm, chưa phân loại SLE theo EULAR/ACR 2019.",
        )
    if total_score < 20:
        return (
            "SLE Tiêu chuẩn",
            "10 ≤ Score < 20: đáp ứng tiêu chuẩn phân loại, cần đánh giá/điều trị theo phác đồ chuẩn.",
        )
    return (
        "SLE Nguy cơ cao / Ominous",
        "Score ≥ 20: cảnh báo nguy cơ cao (đặc biệt thận/thần kinh), cần theo dõi sát và cân nhắc điều trị tích cực sớm.",
    )


def compute_score(*, ana_positive: bool, selections: Dict[str, bool]) -> ScoreResult:
    if not ana_positive:
        tier, note = _risk_tier(0, False)
        return ScoreResult(
            ana_positive=False,
            eligible=False,
            total_score=0,
            meets_classification=False,
            risk_tier=tier,
            risk_note=note,
            domain_scores=tuple(),
            ineligible_reason="ANA âm tính: không đạt tiêu chuẩn đầu vào nên không tính điểm.",
        )

    domain_scores: List[DomainScore] = []
    total = 0
    for dom in get_domains():
        selected = _selected_criteria(dom, selections)
        awarded_points, awarded_criterion = _domain_award(dom, selected)
        total += awarded_points
        domain_scores.append(
            DomainScore(
                domain_id=dom.id,
                domain_label=dom.label,
                awarded_points=awarded_points,
                awarded_criterion=awarded_criterion,
                selected_criteria=tuple(selected),
                note=dom.note,
            )
        )

    tier, note = _risk_tier(total, True)
    return ScoreResult(
        ana_positive=True,
        eligible=True,
        total_score=total,
        meets_classification=total >= 10,
        risk_tier=tier,
        risk_note=note,
        domain_scores=tuple(domain_scores),
    )


