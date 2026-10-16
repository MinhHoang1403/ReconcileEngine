"""Safe CSV/XLSX readers that preserve source values and exact row lineage."""

from __future__ import annotations

import hashlib
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from smartrecon.ingest.structure import DetectedStructure, csv_rows, detect_structure, xlsx_rows

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
    structure: DetectedStructure
    source_row_numbers: tuple[int, ...]


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


def _validated_headers(headers: list[object]) -> list[str]:
    """Reject duplicate headers and label blank positions without assigning meaning."""
    normalized = [str(value).strip() if value is not None else "" for value in headers]
    if not normalized or not any(normalized):
        raise InputFileError("Header không có tên cột")
    duplicates = sorted({value for value in normalized if value and normalized.count(value) > 1})
    if duplicates:
        raise InputFileError(f"Header bị trùng: {', '.join(duplicates)}")
    return [value or f"Cột chưa đặt tên {index + 1}" for index, value in enumerate(normalized)]


def _frame_from_structure(rows: list[list[object]], structure: DetectedStructure) -> pd.DataFrame:
    headers = _validated_headers(list(structure.selected.columns))
    raw_rows = rows[structure.data_start_row_number - 1 :]
    populated = [row for row in raw_rows if any(value is not None and str(value).strip() for value in row)]
    width = len(headers)
    matrix = [list(row[:width]) + [None] * max(0, width - len(row)) for row in populated]
    return pd.DataFrame([row[:width] for row in matrix], columns=headers, dtype=object)


def _read_csv(
    path: Path,
    *,
    expected_feed: str | None,
    delimiter: str | None,
    header_row: int | None,
    header_depth: int | None,
) -> tuple[pd.DataFrame, DetectedStructure]:
    try:
        rows, selected_delimiter, encoding = csv_rows(path, delimiter)
        structure = detect_structure(
            {None: rows},
            expected_feed=expected_feed,
            delimiter=selected_delimiter,
            encoding=encoding,
            selected_header_row=header_row,
            selected_header_depth=header_depth,
        )
    except (UnicodeDecodeError, UnicodeError) as exc:
        raise InputFileError("CSV phải dùng UTF-8 hoặc UTF-8-SIG") from exc
    except ValueError as exc:
        raise InputFileError(str(exc)) from exc
    return _frame_from_structure(rows, structure), structure


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


def _read_xlsx(
    path: Path,
    sheet_name: str | None,
    *,
    expected_feed: str | None,
    header_row: int | None,
    header_depth: int | None,
) -> tuple[pd.DataFrame, str, DetectedStructure]:
    _validate_xlsx(path)
    try:
        sheets = xlsx_rows(path)
    except ValueError as exc:
        raise InputFileError(str(exc)) from exc
    if len(sheets) > MAX_SHEETS:
        raise InputFileError(f"Workbook vượt giới hạn {MAX_SHEETS} sheets")
    try:
        structure = detect_structure(
            sheets,
            expected_feed=expected_feed,
            selected_sheet=sheet_name,
            selected_header_row=header_row,
            selected_header_depth=header_depth,
        )
    except ValueError as exc:
        raise InputFileError(str(exc)) from exc
    selected = structure.selected.sheet_name
    if selected is None or selected not in sheets:
        raise InputFileError("Không tìm thấy sheet dữ liệu")
    return _frame_from_structure(sheets[selected], structure), selected, structure


def read_table(
    path: Path,
    *,
    sheet_name: str | None = None,
    expected_feed: str | None = None,
    delimiter: str | None = None,
    header_row: int | None = None,
    header_depth: int | None = None,
) -> RawTable:
    """Read one source while preserving IDs, exact source rows, and structure evidence."""
    if header_row is not None and header_row < 1:
        raise InputFileError("Số dòng header phải lớn hơn hoặc bằng 1")
    if header_depth is not None and header_depth not in {1, 2}:
        raise InputFileError("Độ sâu header chỉ hỗ trợ 1 hoặc 2 dòng")
    if delimiter is not None and delimiter not in {",", ";", "\t", "|"}:
        raise InputFileError("Dấu phân cách CSV không được hỗ trợ")
    suffix = _validate_path(path, {".csv", ".xlsx"})
    if suffix == ".csv":
        if sheet_name is not None:
            raise InputFileError("CSV không có sheet")
        frame, structure = _read_csv(
            path,
            expected_feed=expected_feed,
            delimiter=delimiter,
            header_row=header_row,
            header_depth=header_depth,
        )
        selected_sheet = None
    else:
        frame, selected_sheet, structure = _read_xlsx(
            path,
            sheet_name,
            expected_feed=expected_feed,
            header_row=header_row,
            header_depth=header_depth,
        )
    frame.columns = [str(column).strip() for column in frame.columns]
    _validate_shape(frame, f"{path.name}{f'/{selected_sheet}' if selected_sheet else ''}")
    digest = file_sha256(path)
    sheet_token = selected_sheet or "csv"
    source_file_id = hashlib.sha256(f"{digest}:{sheet_token}".encode()).hexdigest()[:24]
    return RawTable(
        source_file_id=source_file_id,
        original_filename=path.name,
        file_sha256=digest,
        sheet_name=selected_sheet,
        frame=frame,
        structure=structure,
        source_row_numbers=structure.source_row_numbers,
    )


def read_source_bundle(
    *,
    orders_path: Path | None = None,
    bank_path: Path | None = None,
    workbook_path: Path | None = None,
    orders_sheet: str | None = None,
    bank_sheet: str | None = None,
    orders_header_row: int | None = None,
    bank_header_row: int | None = None,
    orders_header_depth: int | None = None,
    bank_header_depth: int | None = None,
    orders_delimiter: str | None = None,
    bank_delimiter: str | None = None,
) -> RawSourceBundle:
    """Read two files or two workbook sheets with deterministic structure inspection."""
    separate = orders_path is not None or bank_path is not None
    workbook = workbook_path is not None
    if separate == workbook:
        raise InputFileError("Chọn đúng một chế độ: hai file hoặc một workbook")
    if workbook_path is not None:
        if bool(orders_sheet) != bool(bank_sheet):
            raise InputFileError("Cần chọn đủ cả hai sheet hoặc để hệ thống nhận diện")
        if orders_sheet and orders_sheet == bank_sheet:
            raise InputFileError("Cần chọn hai sheet khác nhau cho orders và bank")
        orders = read_table(
            workbook_path,
            sheet_name=orders_sheet,
            expected_feed="orders",
            header_row=orders_header_row,
            header_depth=orders_header_depth,
        )
        bank = read_table(
            workbook_path,
            sheet_name=bank_sheet,
            expected_feed="bank_transactions",
            header_row=bank_header_row,
            header_depth=bank_header_depth,
        )
        if orders.sheet_name == bank.sheet_name:
            raise InputFileError("Không thể tự phân biệt hai feed; cần chọn hai sheet khác nhau")
        return RawSourceBundle(orders=orders, bank_transactions=bank)
    if orders_path is None or bank_path is None:
        raise InputFileError("Cần đủ hai file orders và bank")
    return RawSourceBundle(
        orders=read_table(
            orders_path,
            expected_feed="orders",
            delimiter=orders_delimiter,
            header_row=orders_header_row,
            header_depth=orders_header_depth,
        ),
        bank_transactions=read_table(
            bank_path,
            expected_feed="bank_transactions",
            delimiter=bank_delimiter,
            header_row=bank_header_row,
            header_depth=bank_header_depth,
        ),
    )
