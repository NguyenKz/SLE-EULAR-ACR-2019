# Test cases – SLE EULAR/ACR 2019 (theo cấu hình hệ thống)

> Lưu ý: bộ test case này bám theo **cấu hình đang implement trong `criteria/scoring.py`** (trích từ báo cáo `docs/main_doc.pdf`), gồm ANA gate + Max-in-Domain + ngưỡng 10 và phân tầng 20.

## 1) Nhóm “gate” ANA

- **TC-ANA-01 (ANA âm tính ⇒ dừng)**
  - **Input**: `ana_positive=false`, chọn bất kỳ tiêu chí nào (ví dụ `fever=true`)
  - **Expected**:
    - `eligible=false`
    - `total_score=0`
    - `meets_classification=false`
    - `risk_tier="Không đủ điều kiện tính điểm"`

## 2) Nhóm “Max-in-Domain”

- **TC-MAX-HEMA-01 (Huyết học: không cộng dồn)**
  - **Input**: ANA(+), chọn `leukopenia=true`, `thrombocytopenia=true`, `autoimmune_hemolysis=true`
  - **Expected**: domain Huyết học tính **4** (MAX), tổng = **4**

- **TC-MAX-NEURO-01**
  - **Input**: ANA(+), chọn `delirium=true`, `psychosis=true`, `seizure=true`
  - **Expected**: domain TKTT tính **5** (MAX)

- **TC-MAX-MUCO-01**
  - **Input**: ANA(+), chọn `oral_ulcers=true`, `subacute_cutaneous_or_discoid=true`, `acute_cutaneous=true`
  - **Expected**: domain Da-niêm mạc tính **6** (MAX)

- **TC-MAX-SER-01**
  - **Input**: ANA(+), chọn `pleural_or_pericardial_effusion=true`, `acute_pericarditis=true`
  - **Expected**: domain Thanh mạc tính **6** (MAX)

- **TC-MAX-RENAL-01**
  - **Input**: ANA(+), chọn `proteinuria=true`, `renal_biopsy_class_ii_or_v=true`, `renal_biopsy_class_iii_or_iv=true`
  - **Expected**: domain Thận tính **10** (MAX)

- **TC-MAX-COMP-01**
  - **Input**: ANA(+), chọn `low_c3_or_c4=true`, `low_c3_and_c4=true`
  - **Expected**: domain Bổ thể tính **4** (MAX)

## 3) Nhóm “biên” Score 10 và 20

- **TC-BND-09 (Score < 10)**
  - **Input**: ANA(+), `fever=true (2)`, `proteinuria=true (4)`, `antiphospholipid_any=true (2)`
  - **Expected**: tổng **8**, `meets_classification=false`, `risk_tier="Chưa đủ tiêu chuẩn"`

- **TC-BND-10 (Score = 10)**
  - **Input**: ANA(+), `renal_biopsy_class_iii_or_iv=true (10)`
  - **Expected**: tổng **10**, `meets_classification=true`, `risk_tier="SLE Tiêu chuẩn"`

- **TC-BND-19 (Score = 19)**
  - **Input**: ANA(+), `renal_biopsy_class_ii_or_v=true (8)`, `acute_cutaneous=true (6)`, `leukopenia=true (3)`, `fever=true (2)`
  - **Expected**: tổng **19**, `risk_tier="SLE Tiêu chuẩn"`

- **TC-BND-20+ (Score ≥ 20 ⇒ Ominous)**
  - **Input**: ANA(+), `renal_biopsy_class_iii_or_iv=true (10)`, `acute_cutaneous=true (6)`, `antiphospholipid_any=true (2)`, `fever=true (2)`
  - **Expected**: tổng **20**, `risk_tier="SLE Nguy cơ cao / Ominous"`

## 4) Nhóm API validation

- **TC-API-01 (selections có key lạ bị bỏ qua)**
  - **Input**: POST `/api/score` với `{"ana_positive": true, "selections": {"renal_biopsy_class_iii_or_iv": true, "__hacker__": true}}`
  - **Expected**: tổng = **10** (key lạ không ảnh hưởng)

- **TC-API-02 (selections không phải object ⇒ 400)**
  - **Input**: `{"ana_positive": true, "selections": ["renal_biopsy_class_iii_or_iv"]}`
  - **Expected**: HTTP **400**


