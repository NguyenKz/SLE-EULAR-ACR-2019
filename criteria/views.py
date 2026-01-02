import json
from pathlib import Path

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods

from .forms import CriteriaForm
from .scoring import compute_score, get_domains
from .testcase_runner import normalize_suite, run_case


def _domain_blocks(form: CriteriaForm):
    """
    Django templates can't do dynamic dict-style indexing like `form[c.id]`,
    so we pre-bind fields here for easy rendering.
    """
    blocks = []
    for d in get_domains():
        fields = []
        for c in d.criteria:
            fields.append({"criterion": c, "bf": form[c.id]})
        blocks.append({"domain": d, "fields": fields})
    return blocks


def _radar_payload(result):
    """
    Build radar payload: one axis per domain, with value and max points.
    """
    domains = list(get_domains())
    max_by_id = {}
    label_by_id = {}
    for d in domains:
        label_by_id[d.id] = d.label
        max_by_id[d.id] = max((c.points for c in d.criteria), default=0) if d.max_in_domain else (d.criteria[0].points if d.criteria else 0)

    value_by_id = {}
    for ds in getattr(result, "domain_scores", []) or []:
        value_by_id[ds.domain_id] = ds.awarded_points

    axes = []
    for d in domains:
        axes.append(
            {
                "id": d.id,
                "label": label_by_id[d.id],
                "value": int(value_by_id.get(d.id, 0)),
                "max": int(max_by_id.get(d.id, 0)),
            }
        )
    return axes


@require_http_methods(["GET", "POST"])
def index(request: HttpRequest):
    if request.method == "POST":
        form = CriteriaForm(request.POST)
        if form.is_valid():
            result = compute_score(
                ana_positive=form.cleaned_ana_positive(),
                selections=form.cleaned_selections(),
            )
            return render(
                request,
                "criteria/result.html",
                {
                    "form": form,
                    "result": result,
                    "domain_blocks": _domain_blocks(form),
                    "radar_axes": _radar_payload(result),
                },
            )
    else:
        form = CriteriaForm()

    return render(
        request,
        "criteria/index.html",
        {"form": form, "domain_blocks": _domain_blocks(form)},
    )


def about(request: HttpRequest):
    return render(request, "criteria/about.html")


def theory(request: HttpRequest):
    return render(request, "criteria/theory.html", {"domains": get_domains()})


@ensure_csrf_cookie
def test_cases(request: HttpRequest):
    """
    Render docs/test_cases.json as a human-friendly page.
    """
    data = None
    error = None
    path = Path(__file__).resolve().parent.parent / "docs" / "test_cases.json"
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except FileNotFoundError:
        error = f"Không tìm thấy file: {path}"
    except Exception as e:
        error = f"Không đọc/parse được test_cases.json: {type(e).__name__}: {e}"

    return render(
        request,
        "criteria/test_cases.html",
        {"data": data, "error": error, "file_path": str(path)},
    )


@require_http_methods(["GET"])
def test_cases_normalized_json(request: HttpRequest):
    """
    Download a normalized schema-v2 JSON for easier UI loading/running.
    """
    path = Path(__file__).resolve().parent.parent / "docs" / "test_cases.json"
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    normalized = normalize_suite(data)
    return JsonResponse(normalized, json_dumps_params={"ensure_ascii": False, "indent": 2})


@require_http_methods(["POST"])
def test_cases_run(request: HttpRequest):
    """
    POST JSON:
      { "mode": "all" } or { "mode": "one", "id": "TC-09" }
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    mode = payload.get("mode", "all")
    wanted_id = payload.get("id")

    path = Path(__file__).resolve().parent.parent / "docs" / "test_cases.json"
    raw = path.read_text(encoding="utf-8")
    suite = json.loads(raw)

    results = []
    for group in suite.get("test_cases", []):
        for tc in group.get("cases", []):
            if mode == "one" and wanted_id and tc.get("id") != wanted_id:
                continue
            r = run_case(tc)
            results.append(
                {
                    "id": r.id,
                    "description": r.description,
                    "status": r.status,
                    "reason": r.reason,
                    "normalized_input": (
                        {
                            "ana_positive": r.normalized_input.ana_positive,
                            "selections": r.normalized_input.selections,
                        }
                        if r.normalized_input
                        else None
                    ),
                    "expected": (
                        {
                            "total_score": r.expected.total_score,
                            "meets_classification": r.expected.meets_classification,
                            "risk_tier": r.expected.risk_tier,
                            "domain_id": r.expected.domain_id,
                            "domain_score": r.expected.domain_score,
                        }
                        if r.expected
                        else None
                    ),
                    "actual": r.actual,
                    "diffs": r.diffs,
                }
            )

    summary = {
        "PASS": sum(1 for r in results if r["status"] == "PASS"),
        "FAIL": sum(1 for r in results if r["status"] == "FAIL"),
        "SKIP": sum(1 for r in results if r["status"] == "SKIP"),
        "ERROR": sum(1 for r in results if r["status"] == "ERROR"),
        "TOTAL": len(results),
    }
    return JsonResponse({"summary": summary, "results": results}, json_dumps_params={"ensure_ascii": False})


@require_http_methods(["POST"])
def api_score(request: HttpRequest):
    """
    POST JSON:
    {
      "ana_positive": true,
      "selections": { "fever": true, "leukopenia": false, ... }
    }
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON body"}, status=400)

    ana_positive = bool(payload.get("ana_positive"))
    selections = payload.get("selections") or {}
    if not isinstance(selections, dict):
        return JsonResponse({"error": "selections must be an object/dict"}, status=400)

    # Only accept known criterion IDs
    allowed_ids = {c.id for d in get_domains() for c in d.criteria}
    filtered = {k: bool(v) for k, v in selections.items() if k in allowed_ids}

    result = compute_score(ana_positive=ana_positive, selections=filtered)
    return JsonResponse(
        {
            "ana_positive": result.ana_positive,
            "eligible": result.eligible,
            "ineligible_reason": result.ineligible_reason,
            "total_score": result.total_score,
            "meets_classification": result.meets_classification,
            "risk_tier": result.risk_tier,
            "risk_note": result.risk_note,
            "domains": [
                {
                    "domain_id": ds.domain_id,
                    "domain_label": ds.domain_label,
                    "awarded_points": ds.awarded_points,
                    "awarded_criterion": (
                        {
                            "id": ds.awarded_criterion.id,
                            "label": ds.awarded_criterion.label,
                            "points": ds.awarded_criterion.points,
                        }
                        if ds.awarded_criterion
                        else None
                    ),
                    "selected_criteria": [
                        {"id": c.id, "label": c.label, "points": c.points}
                        for c in ds.selected_criteria
                    ],
                    "note": ds.note,
                }
                for ds in result.domain_scores
            ],
        }
    )
