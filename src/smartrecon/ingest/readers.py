"""Safe CSV/XLSX readers that preserve source values and file lineage."""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COLUMNS = 200
MAX_SHEETS = 20
MAX_XLSX_UNCOMPRESSED_BYTES = 200 * 1024 * 1024


class InputFileError(ValueError):
    """Raised when an input file fails format, structure, or size validation."""


@dataclass(frozen=True, slots=True)
class RawTable:
    """An immutable read result with source identity and text-preserving rows."""

    source_file_id: str
    original_filename: str
    file_sha256: str
    sheet_name: str | None
    frame: pd.DataFrame


@dataclass(frozen=True, slots=True)
class RawSourceBundle:
    orders: RawTable
    bank_transactions: RawTable


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_path(path: Path, expected_suffixes: set[str]) -> str:
    if not path.is_file():
        raise InputFileError(f"File không tồn tại: {path.name}")
    suffix = path.suffix.lower()
    if suffix not in expected_suffixes:
        raise InputFileError(f"Định dạng không hỗ trợ: {suffix or '(không có extension)'}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise InputFileError(f"File vượt giới hạn {MAX_FILE_BYTES // (1024 * 1024)} MB")
    return suffix


def _validate_shape(frame: pd.DataFrame, source_name: str) -> None:
    if frame.empty:
        raise InputFileError(f"{source_name} không có dòng dữ liệu")
    if len(frame) > MAX_ROWS:
        raise InputFileError(f"{source_name} vượt giới hạn {MAX_ROWS} dòng")
    if len(frame.columns) > MAX_COLUMNS:
        raise InputFileError(f"{source_name} vượt giới hạn {MAX_COLUMNS} cột")
    if frame.columns.duplicated().any():
        duplicates = sorted(set(frame.columns[frame.columns.duplicated()].astype(str)))
        raise InputFileError(f"Header bị trùng: {', '.join(duplicates)}")


def _read_csv(path: Path) -> pd.DataFrame:
    head = path.read_bytes()[:4096]
    if b"\x00" in head:
        raise InputFileError("CSV chứa byte NUL hoặc content không phải text")
    last_error: UnicodeDecodeError | None = None
    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return pd.read_csv(path, dtype="string", keep_default_na=False, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise InputFileError("CSV phải dùng UTF-8 hoặc UTF-8-SIG") from last_error


def _validate_xlsx(path: Path) -> None:
    if path.read_bytes()[:4] != b"PK\x03\x04" or not zipfile.is_zipfile(path):
        raise InputFileError("Nội dung không phải workbook XLSX hợp lệ")
    with zipfile.ZipFile(path) as archive:
        total_uncompressed = sum(item.file_size for item in archive.infolist())
        if total_uncompressed > MAX_XLSX_UNCOMPRESSED_BYTES:
            raise InputFileError("Workbook giải nén vượt giới hạn an toàn")
        names = set(archive.namelist())
        if "[Content_Types].xml" not in names or "xl/workbook.xml" not in names:
            raise InputFileError("Cấu trúc ZIP không phải workbook XLSX")
        if any(name.lower().endswith("vbaproject.bin") for name in names):
            raise InputFileError("Workbook có macro không được hỗ trợ")


def _read_xlsx(path: Path, sheet_name: str | None) -> tuple[pd.DataFrame, str]:
    _validate_xlsx(path)
    excel = pd.ExcelFile(path, engine="openpyxl")
    if len(excel.sheet_names) > MAX_SHEETS:
        raise InputFileError(f"Workbook vượt giới hạn {MAX_SHEETS} sheets")
    selected = sheet_name or (excel.sheet_names[0] if len(excel.sheet_names) == 1 else None)
    if selected is None:
        raise InputFileError("Workbook nhiều sheet cần chọn sheet rõ ràng")
    if selected not in excel.sheet_names:
        raise InputFileError(f"Không tìm thấy sheet: {selected}")
    return (
        pd.read_excel(path, sheet_name=selected, dtype="string", keep_default_na=False),
        selected,
    )


def read_table(path: Path, *, sheet_name: str | None = None) -> RawTable:
    """Read one source without type coercion that would discard leading zeros."""
    suffix = _validate_path(path, {".csv", ".xlsx"})
    if suffix == ".csv":
        if sheet_name is not None:
            raise InputFileError("CSV không có sheet")
        frame = _read_csv(path)
        selected_sheet = None
    else:
        frame, selected_sheet = _read_xlsx(path, sheet_name)
    frame.columns = [str(column).strip() for column in frame.columns]
    _validate_shape(frame, f"{path.name}{f'/{selected_sheet}' if selected_sheet else ''}")
    digest = file_sha256(path)
    sheet_token = selected_sheet or "csv"
    source_file_id = hashlib.sha256(f"{digest}:{sheet_token}".encode()).hexdigest()[:24]
    return RawTable(source_file_id, path.name, digest, selected_sheet, frame)


def read_source_bundle(
    *,
    orders_path: Path | None = None,
    bank_path: Path | None = None,
    workbook_path: Path | None = None,
    orders_sheet: str | None = None,
    bank_sheet: str | None = None,
) -> RawSourceBundle:
    """Read either two independent files or two distinct workbook sheets."""
    separate = orders_path is not None or bank_path is not None
    workbook = workbook_path is not None
    if separate == workbook:
        raise InputFileError("Chọn đúng một chế độ: hai file hoặc một workbook")
    if workbook_path is not None:
        if not orders_sheet or not bank_sheet or orders_sheet == bank_sheet:
            raise InputFileError("Cần chọn hai sheet khác nhau cho orders và bank")
        return RawSourceBundle(
            orders=read_table(workbook_path, sheet_name=orders_sheet),
            bank_transactions=read_table(workbook_path, sheet_name=bank_sheet),
        )
    if orders_path is None or bank_path is None:
        raise InputFileError("Cần đủ hai file orders và bank")
    return RawSourceBundle(orders=read_table(orders_path), bank_transactions=read_table(bank_path))
