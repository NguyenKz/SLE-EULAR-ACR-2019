from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .scoring import ScoreResult, compute_score, get_domains


@dataclass(frozen=True)
class NormalizedTestInput:
    ana_positive: bool
    selections: Dict[str, bool]  # criterion_id -> bool


@dataclass(frozen=True)
class NormalizedExpected:
    total_score: Optional[int] = None
    meets_classification: Optional[bool] = None
    risk_tier: Optional[str] = None
    domain_id: Optional[str] = None
    domain_score: Optional[int] = None


@dataclass(frozen=True)
class RunResult:
    id: str
    description: str
    status: str  # PASS/FAIL/SKIP/ERROR
    reason: Optional[str]
    normalized_input: Optional[NormalizedTestInput]
    expected: Optional[NormalizedExpected]
    actual: Optional[Dict[str, Any]]
    diffs: List[str]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def _map_selected_criteria_to_ids(selected: List[str]) -> Tuple[Dict[str, bool], List[str]]:
    """
    Map legacy human strings in docs/test_cases.json to internal criterion IDs.
    Returns (selections, warnings).
    """
    warnings: List[str] = []
    tokens = [_norm(x) for x in selected]

    selections: Dict[str, bool] = {}

    def add(cid: str):
        selections[cid] = True

    # Renal
    for t in tokens:
        if "proteinuria" in t:
            add("proteinuria")
        if "class iii" in t or "class iv" in t:
            add("renal_biopsy_class_iii_or_iv")
        if "class ii" in t or "class v" in t:
            add("renal_biopsy_class_ii_or_v")

    # Serosal
    for t in tokens:
        if "acute pericarditis" in t:
            add("acute_pericarditis")
        if "effusion" in t:
            add("pleural_or_pericardial_effusion")

    # Hematologic
    for t in tokens:
        if "leukopenia" in t:
            add("leukopenia")
        if "thrombocytopenia" in t:
            add("thrombocytopenia")
        if "hemolysis" in t:
            add("autoimmune_hemolysis")

    # Neuropsychiatric
    for t in tokens:
        if "delirium" in t:
            add("delirium")
        if "psychosis" in t:
            add("psychosis")
        if "seizure" in t:
            add("seizure")

    # Musculoskeletal
    for t in tokens:
        if "arthritis" in t or "joint" in t:
            add("joint_involvement")

    # Mucocutaneous
    for t in tokens:
        if "acute cutaneous" in t:
            add("acute_cutaneous")
        if "discoid" in t or "subacute cutaneous" in t:
            add("subacute_cutaneous_or_discoid")
        if "oral ulcer" in t or "mouth ulcer" in t:
            add("oral_ulcers")
        if "alopecia" in t:
            add("nonscarring_alopecia")

    # Complement (legacy file expresses Low C3 and Low C4 separately)
    low_c3 = any("low c3" in t for t in tokens)
    low_c4 = any("low c4" in t for t in tokens)
    if low_c3 and low_c4:
        add("low_c3_and_c4")
    elif low_c3 or low_c4:
        add("low_c3_or_c4")

    # Antiphospholipid (any positive => 2 points)
    if any("anti-cardiolipin" in t for t in tokens) or any("lupus anticoagulant" in t for t in tokens) or any("β2" in t or "b2gp1" in t for t in tokens):
        add("antiphospholipid_any")

    if not selections and selected:
        warnings.append("Không map được selected_criteria -> criterion IDs (cần chuẩn hóa JSON).")

    return selections, warnings


def _map_expected(tc: Dict[str, Any], selections: Dict[str, bool]) -> Tuple[Optional[NormalizedExpected], List[str]]:
    exp = tc.get("expected_output") or {}
    if not isinstance(exp, dict) or not exp:
        return None, []

    warnings: List[str] = []

    total_score = exp.get("total_score")
    domain_score = exp.get("domain_score")
    classification = exp.get("classification")
    risk_level = exp.get("risk_level")

    meets_classification: Optional[bool] = None
    if isinstance(classification, str):
        c = _norm(classification)
        if "not classified" in c:
            meets_classification = False
        elif "classified" in c:
            meets_classification = True

    risk_tier: Optional[str] = None
    if isinstance(risk_level, str):
        r = _norm(risk_level)
        if "low" == r:
            risk_tier = "Chưa đủ tiêu chuẩn"
        elif "moderate" in r or "standard" in r:
            risk_tier = "SLE Tiêu chuẩn"
        elif "high" in r or "ominous" in r:
            risk_tier = "SLE Nguy cơ cao / Ominous"

    domain_id: Optional[str] = None
    if domain_score is not None:
        # Infer a likely domain for legacy cases (optional)
        if any(k.startswith("renal_") or k == "proteinuria" for k in selections.keys()):
            domain_id = "renal"
        elif any(k.startswith("low_c3") for k in selections.keys()):
            domain_id = "complement"
        elif "antiphospholipid_any" in selections:
            domain_id = "antiphospholipid"
        elif any(k in selections for k in ("delirium", "psychosis", "seizure")):
            domain_id = "neuropsychiatric"

        if domain_id is None:
            warnings.append("expected_output.domain_score có nhưng không suy ra được domain_id.")

    return (
        NormalizedExpected(
            total_score=total_score if isinstance(total_score, int) else None,
            meets_classification=meets_classification,
            risk_tier=risk_tier,
            domain_id=domain_id,
            domain_score=domain_score if isinstance(domain_score, int) else None,
        ),
        warnings,
    )


def normalize_case(tc: Dict[str, Any]) -> Tuple[Optional[NormalizedTestInput], Optional[NormalizedExpected], List[str], str]:
    """
    Returns (normalized_input, normalized_expected, warnings, kind)
      - kind: "auto" if runnable by scoring engine, otherwise "manual"
    """
    warnings: List[str] = []

    # v2 format: kind + input.ana_positive + input.selections (criterion IDs)
    if isinstance(tc.get("kind"), str) and tc.get("kind") == "manual":
        return None, None, warnings, "manual"

    if isinstance(tc.get("input"), dict) and "ana_positive" in tc["input"] and "selections" in tc["input"]:
        ana_positive = tc["input"].get("ana_positive")
        selections_list = tc["input"].get("selections")
        if not isinstance(ana_positive, bool) or not isinstance(selections_list, list):
            return None, None, ["input v2 không hợp lệ (ana_positive bool, selections list)"], "manual"

        # Only allow known criterion IDs
        allowed_ids = {c.id for d in get_domains() for c in d.criteria}
        selections = {str(cid): True for cid in selections_list if str(cid) in allowed_ids}
        n_inp = NormalizedTestInput(ana_positive=ana_positive, selections=selections)

        exp_v2 = tc.get("expected")
        n_exp: Optional[NormalizedExpected] = None
        if isinstance(exp_v2, dict) and exp_v2:
            n_exp = NormalizedExpected(
                total_score=exp_v2.get("total_score") if isinstance(exp_v2.get("total_score"), int) else None,
                meets_classification=exp_v2.get("meets_classification")
                if isinstance(exp_v2.get("meets_classification"), bool)
                else None,
                risk_tier=exp_v2.get("risk_tier") if isinstance(exp_v2.get("risk_tier"), str) else None,
                domain_id=exp_v2.get("domain_id") if isinstance(exp_v2.get("domain_id"), str) else None,
                domain_score=exp_v2.get("domain_score") if isinstance(exp_v2.get("domain_score"), int) else None,
            )

        return n_inp, n_exp, warnings, "auto"

    if "action" in tc and "input" not in tc:
        return None, None, warnings, "manual"

    inp = tc.get("input") or {}
    if not isinstance(inp, dict):
        return None, None, ["input không hợp lệ"], "manual"

    ana_status = inp.get("ana_status")
    if not isinstance(ana_status, bool):
        return None, None, ["thiếu input.ana_status (bool)"], "manual"

    selected = inp.get("selected_criteria") or []
    if not isinstance(selected, list):
        return None, None, ["input.selected_criteria phải là list"], "manual"

    selections, warn_map = _map_selected_criteria_to_ids([str(x) for x in selected])
    warnings.extend(warn_map)

    n_inp = NormalizedTestInput(ana_positive=ana_status, selections=selections)
    n_exp, warn_exp = _map_expected(tc, selections)
    warnings.extend(warn_exp)

    return n_inp, n_exp, warnings, "auto"


def _domain_points(result: ScoreResult, domain_id: str) -> Optional[int]:
    for ds in result.domain_scores:
        if ds.domain_id == domain_id:
            return ds.awarded_points
    return None


def run_case(tc: Dict[str, Any]) -> RunResult:
    tc_id = str(tc.get("id") or "")
    desc = str(tc.get("description") or "")

    try:
        n_inp, n_exp, warnings, kind = normalize_case(tc)
        if kind != "auto" or n_inp is None:
            return RunResult(
                id=tc_id,
                description=desc,
                status="SKIP",
                reason="Test case dạng manual/action (không chạy bằng engine tính điểm).",
                normalized_input=n_inp,
                expected=n_exp,
                actual=None,
                diffs=warnings,
            )

        result = compute_score(ana_positive=n_inp.ana_positive, selections=n_inp.selections)
        actual = {
            "total_score": result.total_score,
            "meets_classification": result.meets_classification,
            "risk_tier": result.risk_tier,
        }

        if n_exp and n_exp.domain_id:
            actual["domain_id"] = n_exp.domain_id
            actual["domain_score"] = _domain_points(result, n_exp.domain_id)

        diffs: List[str] = list(warnings)
        ok = True

        if n_exp is not None:
            if n_exp.total_score is not None and n_exp.total_score != result.total_score:
                ok = False
                diffs.append(f"total_score: expected {n_exp.total_score} != actual {result.total_score}")
            if n_exp.meets_classification is not None and n_exp.meets_classification != result.meets_classification:
                ok = False
                diffs.append(
                    f"meets_classification: expected {n_exp.meets_classification} != actual {result.meets_classification}"
                )
            if n_exp.risk_tier is not None and n_exp.risk_tier != result.risk_tier:
                ok = False
                diffs.append(f"risk_tier: expected {n_exp.risk_tier} != actual {result.risk_tier}")
            if n_exp.domain_score is not None and n_exp.domain_id:
                actual_domain = _domain_points(result, n_exp.domain_id)
                if actual_domain != n_exp.domain_score:
                    ok = False
                    diffs.append(f"{n_exp.domain_id}.domain_score: expected {n_exp.domain_score} != actual {actual_domain}")

        return RunResult(
            id=tc_id,
            description=desc,
            status="PASS" if ok else "FAIL",
            reason=None,
            normalized_input=n_inp,
            expected=n_exp,
            actual=actual,
            diffs=diffs,
        )
    except Exception as e:
        return RunResult(
            id=tc_id,
            description=desc,
            status="ERROR",
            reason=f"{type(e).__name__}: {e}",
            normalized_input=None,
            expected=None,
            actual=None,
            diffs=[],
        )


def normalize_suite(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Produce a schema-v2 JSON that is easy to run/load:
      - input.ana_positive (bool)
      - input.selections (list of criterion_ids)
      - expected: total_score/meets_classification/risk_tier/domain_id/domain_score
      - kind: auto/manual
    """
    out: Dict[str, Any] = {
        "schema_version": "internal_ids_v2",
        "test_suite": data.get("test_suite"),
        "version": data.get("version"),
        "test_cases": [],
    }

    for group in data.get("test_cases", []) if isinstance(data.get("test_cases"), list) else []:
        new_group = {"category": group.get("category"), "cases": []}
        for tc in group.get("cases", []) if isinstance(group.get("cases"), list) else []:
            n_inp, n_exp, warnings, kind = normalize_case(tc)
            new_tc: Dict[str, Any] = {
                "id": tc.get("id"),
                "description": tc.get("description"),
                "kind": kind,
            }
            if "medical_rationale" in tc:
                new_tc["medical_rationale"] = tc.get("medical_rationale")
            if "technical_logic" in tc:
                new_tc["technical_logic"] = tc.get("technical_logic")
            if "action" in tc:
                new_tc["action"] = tc.get("action")
            if warnings:
                new_tc["warnings"] = warnings
            if n_inp is not None:
                new_tc["input"] = {
                    "ana_positive": n_inp.ana_positive,
                    "selections": sorted([k for k, v in n_inp.selections.items() if v]),
                }
            if n_exp is not None:
                new_tc["expected"] = {
                    k: v
                    for k, v in {
                        "total_score": n_exp.total_score,
                        "meets_classification": n_exp.meets_classification,
                        "risk_tier": n_exp.risk_tier,
                        "domain_id": n_exp.domain_id,
                        "domain_score": n_exp.domain_score,
                    }.items()
                    if v is not None
                }
            new_group["cases"].append(new_tc)
        out["test_cases"].append(new_group)

    return out


