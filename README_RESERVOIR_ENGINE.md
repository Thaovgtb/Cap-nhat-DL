# THUY LOI AI - Reservoir Engine Integration

Bản tích hợp `Reservoir Engine` vào Technical Module hiện tại.

## Chức năng
- Đọc mực nước thực tế từ `AI_DATA` như code hiện tại.
- Tự nhận diện 10 hồ có đường quan hệ Z-F-V từ bộ VBA đã khôi phục.
- Tính:
  - Z: mực nước hiện tại
  - F: diện tích mặt hồ
  - V: dung tích hiện tại
  - V/V(MNDBT): tỷ lệ dung tích so với MNDBT
  - Dung tích còn đến MNDBT
  - Chênh cao trình đến MNDBT
  - Trạng thái so với MNDBT/MNDGC
- Thuật toán chính: nội suy tuyến tính từng đoạn, theo logic VBA gốc.
- Bổ sung API: `/api/reservoir-state`.
- Bổ sung panel "Thông số hồ chứa · Z–F–V" trên dashboard.

## Dữ liệu đường quan hệ
`reservoir_curves.json` được bóc tách từ các module VBA:
PNinh2026, ThachBan2026, TruocDong2026, DongTien2026,
DongNghe2026, VinhTrinh2026, VietAN2026, HocKhe2026,
HoCau2026, HoaTrung2026.

## Lưu ý
- Các hàm Q xả/cửa van trong `CodeQtran2027.xla` chưa được đưa vào engine ở bản này.
- Với từng module, cách xử lý ngoài miền được giữ theo VBA gốc khi nhận diện được:
  strict / clamp / linear_extrapolate.
- Không thay đổi cơ chế đọc/ghi Google Sheets hiện tại.
