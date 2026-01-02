# SLE EULAR/ACR 2019 – Web tra cứu & phân tầng nguy cơ

Ứng dụng web (Django) giúp:

- Tính điểm theo tiêu chuẩn phân loại **EULAR/ACR 2019**
- Áp dụng **ANA** làm tiêu chuẩn đầu vào
- Tính điểm theo nguyên tắc **Max-in-Domain** (chỉ lấy điểm cao nhất trong mỗi miền)
- Phân tầng nguy cơ theo mô hình trong báo cáo: **Score < 10**, **10 ≤ Score < 20**, **Score ≥ 20**
- Nhập **họ tên / mã** và **Xuất PDF** phiếu kết quả

Logic/điểm số được triển khai theo báo cáo đồ án: [`docs/main_doc.pdf`](file:///Users/tracydt/Documents/code/doan_ppnckh/docs/main_doc.pdf).

## Cơ sở lý thuyết (EULAR/ACR 2019)

Trong ứng dụng, logic được triển khai theo các ý chính (xem trang `http://localhost:8000/theory/` để đọc đầy đủ):

- **Tiêu chuẩn đầu vào (ANA gate)**: chỉ chấm điểm khi **ANA dương tính**; nếu ANA âm tính → **không phân loại** theo EULAR/ACR 2019.
- **Nguyên tắc Max-in-Domain**: trong mỗi **miền (domain)**, nếu chọn nhiều tiêu chí thì **chỉ lấy tiêu chí có điểm cao nhất**.
- **Ngưỡng phân loại**: tổng điểm **≥ 10** (và ANA +) → **đủ tiêu chuẩn phân loại SLE**.
- **Phân tầng nguy cơ (theo báo cáo)**:
  - **Score < 10**: Không phân loại SLE
  - **10 ≤ Score < 20**: SLE
  - **Score ≥ 20**: SLE nguy cơ cao / Ominous

## Chạy bằng Docker

```bash
docker compose up --build
```

Mở `http://localhost:8000/`.

### Postgres (Docker)

Khi chạy bằng `docker compose`, hệ thống sẽ dùng **PostgreSQL** (service `db`) và tự chạy `migrate` trước khi start server.

## Chạy local (không Docker)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Ghi chú: tính năng **Xuất PDF** dùng session của Django, nên cần chạy `migrate` để tạo bảng `django_session`.

### Postgres (local – optional)

Nếu muốn dùng Postgres khi chạy local, export các biến môi trường:

```bash
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5432
export POSTGRES_DB=sleweb
export POSTGRES_USER=sleweb
export POSTGRES_PASSWORD=sleweb
python manage.py migrate
python manage.py runserver
```

## API

`POST /api/score` JSON:

```json
{
  "ana_positive": true,
  "selections": {
    "fever": true,
    "renal_biopsy_class_iii_or_iv": true
  }
}
```

Trả về: tổng điểm, đủ tiêu chuẩn hay không, phân tầng nguy cơ, và breakdown theo miền.

## Tham khảo (được trích trong báo cáo)

- Bài PubMed về “Ominosity”: `https://pubmed.ncbi.nlm.nih.gov/33452003/`
- Bài The Rheumatologist: `https://www.the-rheumatologist.org/article/using-the-2019-eular-acr-classification-criteria-to-predict-disease-severity-in-sle/`


