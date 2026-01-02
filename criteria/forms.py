from __future__ import annotations

from django import forms

from .scoring import get_domains


class CriteriaForm(forms.Form):
    full_name = forms.CharField(
        label="Họ và tên",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ví dụ: Nguyễn Văn A"}),
    )
    patient_code = forms.CharField(
        label="Mã",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Ví dụ: BN-0001"}),
    )

    ANA_CHOICES = (
        ("true", "Dương tính (ANA +)"),
        ("false", "Âm tính (ANA -)"),
    )

    ana_positive = forms.ChoiceField(
        label="Kháng thể kháng nhân (ANA) - tiêu chuẩn đầu vào",
        choices=ANA_CHOICES,
        widget=forms.RadioSelect,
        initial="true",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dynamically generate checkbox fields from single scoring config.
        for domain in get_domains():
            for c in domain.criteria:
                self.fields[c.id] = forms.BooleanField(
                    label=f"{c.label} ({c.points} điểm)",
                    required=False,
                )

    def cleaned_selections(self) -> dict[str, bool]:
        selections: dict[str, bool] = {}
        for domain in get_domains():
            for c in domain.criteria:
                selections[c.id] = bool(self.cleaned_data.get(c.id))
        return selections

    def cleaned_ana_positive(self) -> bool:
        return self.cleaned_data.get("ana_positive") == "true"

    def cleaned_patient_info(self) -> dict[str, str]:
        return {
            "full_name": (self.cleaned_data.get("full_name") or "").strip(),
            "patient_code": (self.cleaned_data.get("patient_code") or "").strip(),
        }


