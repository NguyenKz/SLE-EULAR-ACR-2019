from django.test import Client, TestCase

from .scoring import compute_score


class ScoringTests(TestCase):
    def test_ana_negative_is_ineligible(self):
        r = compute_score(ana_positive=False, selections={"fever": True})
        self.assertFalse(r.eligible)
        self.assertEqual(r.total_score, 0)
        self.assertFalse(r.meets_classification)

    def test_max_in_domain_hematologic(self):
        # leukopenia=3, thrombocytopenia=4, autoimmune_hemolysis=4 -> max should be 4, not sum
        r = compute_score(
            ana_positive=True,
            selections={
                "leukopenia": True,
                "thrombocytopenia": True,
                "autoimmune_hemolysis": True,
            },
        )
        self.assertTrue(r.eligible)
        self.assertEqual(r.total_score, 4)

    def test_max_in_domain_neuropsychiatric(self):
        # delirium=2, psychosis=3, seizure=5 -> max = 5
        r = compute_score(
            ana_positive=True,
            selections={"delirium": True, "psychosis": True, "seizure": True},
        )
        self.assertEqual(r.total_score, 5)

    def test_max_in_domain_mucocutaneous(self):
        # oral_ulcers=2, discoid=4, acute_cutaneous=6 -> max = 6
        r = compute_score(
            ana_positive=True,
            selections={
                "oral_ulcers": True,
                "subacute_cutaneous_or_discoid": True,
                "acute_cutaneous": True,
            },
        )
        self.assertEqual(r.total_score, 6)

    def test_max_in_domain_serosal(self):
        # effusion=5, acute_pericarditis=6 -> max = 6
        r = compute_score(
            ana_positive=True,
            selections={"pleural_or_pericardial_effusion": True, "acute_pericarditis": True},
        )
        self.assertEqual(r.total_score, 6)

    def test_max_in_domain_renal(self):
        # proteinuria=4, class II/V=8, class III/IV=10 -> max = 10
        r = compute_score(
            ana_positive=True,
            selections={
                "proteinuria": True,
                "renal_biopsy_class_ii_or_v": True,
                "renal_biopsy_class_iii_or_iv": True,
            },
        )
        self.assertEqual(r.total_score, 10)

    def test_max_in_domain_complement(self):
        # low_c3_or_c4=3 vs low_c3_and_c4=4 -> max = 4
        r = compute_score(ana_positive=True, selections={"low_c3_or_c4": True, "low_c3_and_c4": True})
        self.assertEqual(r.total_score, 4)

    def test_risk_tier_boundaries(self):
        r9 = compute_score(ana_positive=True, selections={"fever": True, "proteinuria": True, "antiphospholipid_any": True})
        self.assertEqual(r9.total_score, 8)
        self.assertFalse(r9.meets_classification)
        self.assertEqual(r9.risk_tier, "Chưa đủ tiêu chuẩn")

        r10 = compute_score(ana_positive=True, selections={"renal_biopsy_class_iii_or_iv": True})
        self.assertEqual(r10.total_score, 10)
        self.assertTrue(r10.meets_classification)
        self.assertEqual(r10.risk_tier, "SLE Tiêu chuẩn")

        r19 = compute_score(
            ana_positive=True,
            selections={
                "renal_biopsy_class_ii_or_v": True,  # 8
                "acute_cutaneous": True,  # 6
                "leukopenia": True,  # 3
                "fever": True,  # 2
            },
        )
        self.assertEqual(r19.total_score, 19)
        self.assertEqual(r19.risk_tier, "SLE Tiêu chuẩn")

        # Exactly 20 => Ominous threshold
        r20b = compute_score(
            ana_positive=True,
            selections={"renal_biopsy_class_iii_or_iv": True, "acute_cutaneous": True, "antiphospholipid_any": True, "fever": True},
        )
        self.assertEqual(r20b.total_score, 20)
        self.assertEqual(r20b.risk_tier, "SLE Nguy cơ cao / Ominous")

    def test_classification_threshold_10(self):
        # renal biopsy class III/IV is 10 -> should meet classification immediately if ANA+
        r = compute_score(ana_positive=True, selections={"renal_biopsy_class_iii_or_iv": True})
        self.assertEqual(r.total_score, 10)
        self.assertTrue(r.meets_classification)

    def test_risk_tier_threshold_20(self):
        # 10 (renal III/IV) + 6 (acute cutaneous) + 6 (joint) = 22 => ominous
        r = compute_score(
            ana_positive=True,
            selections={
                "renal_biopsy_class_iii_or_iv": True,
                "acute_cutaneous": True,
                "joint_involvement": True,
            },
        )
        self.assertGreaterEqual(r.total_score, 20)
        self.assertEqual(r.risk_tier, "SLE Nguy cơ cao / Ominous")


class ApiTests(TestCase):
    def test_index_page_renders(self):
        c = Client()
        resp = c.get("/")
        self.assertEqual(resp.status_code, 200)

    def test_test_cases_page_renders(self):
        c = Client()
        resp = c.get("/test-cases/")
        self.assertEqual(resp.status_code, 200)

    def test_test_cases_normalized_json_downloads(self):
        c = Client()
        resp = c.get("/test-cases/normalized.json")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload.get("schema_version"), "internal_ids_v2")

    def test_test_cases_run_all(self):
        c = Client()
        resp = c.post(
            "/test-cases/run",
            data={"mode": "all"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("summary", payload)
        self.assertIn("results", payload)

    def test_api_score_ok(self):
        c = Client()
        resp = c.post(
            "/api/score",
            data={
                "ana_positive": True,
                "selections": {"renal_biopsy_class_iii_or_iv": True},
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["total_score"], 10)
        self.assertTrue(payload["meets_classification"])

    def test_api_filters_unknown_selection_keys(self):
        c = Client()
        resp = c.post(
            "/api/score",
            data={
                "ana_positive": True,
                "selections": {"renal_biopsy_class_iii_or_iv": True, "__hacker__": True},
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertEqual(payload["total_score"], 10)

    def test_api_rejects_selections_non_object(self):
        c = Client()
        resp = c.post(
            "/api/score",
            data={"ana_positive": True, "selections": ["renal_biopsy_class_iii_or_iv"]},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_api_score_rejects_bad_json(self):
        c = Client()
        resp = c.post("/api/score", data="{bad json", content_type="application/json")
        self.assertEqual(resp.status_code, 400)
