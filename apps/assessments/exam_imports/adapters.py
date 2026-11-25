import csv
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from io import BytesIO, StringIO
from typing import Any
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from defusedxml.common import DefusedXmlException  # type: ignore[import-untyped]
from django.core.exceptions import ValidationError
from openpyxl import load_workbook  # type: ignore[import-untyped]
from openpyxl.utils.exceptions import InvalidFileException  # type: ignore[import-untyped]

MAX_ROWS = 5000
MAX_FILE_BYTES = 3 * 1024 * 1024
SCORE = re.compile(r"[+-]?[0-9]{1,18}(?:[.,][0-9]{1,10})?")


@dataclass(frozen=True)
class Result:
    row: int
    participant: str
    score: str
    raw_score: str = ""
    maximum: str = ""
    session: str = ""
    status: str = ""


@dataclass(frozen=True)
class ParsedResults:
    results: list[Result]
    errors: list[str]


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def numeric_score(value: str) -> str:
    if value and not SCORE.fullmatch(value):
        raise ValidationError("Nilai harus berupa angka.")
    return value.replace(",", ".")


def normalize(rows: Iterable[Result]) -> ParsedResults:
    results: list[Result] = []
    errors: list[str] = []
    for row in rows:
        if len(results) + len(errors) >= MAX_ROWS:
            raise ValidationError(f"Batas impor adalah {MAX_ROWS} baris data.")
        try:
            if not row.participant or len(row.participant) > 254:
                raise ValidationError("Pengenal peserta wajib dan maksimal 254 karakter.")
            if len(row.session) > 120 or len(row.status) > 120:
                raise ValidationError("Sesi atau status maksimal 120 karakter.")
            if any("\x00" in value for value in (row.participant, row.session, row.status)):
                raise ValidationError("Baris memuat karakter yang tidak dapat disimpan.")
            results.append(
                Result(
                    row.row,
                    row.participant,
                    numeric_score(row.score),
                    numeric_score(row.raw_score),
                    numeric_score(row.maximum),
                    row.session,
                    row.status,
                )
            )
        except ValidationError as error:
            errors.append(f"Baris {row.row}: {error.messages[0]}")
    if not results and not errors:
        raise ValidationError("Berkas belum berisi hasil ujian.")
    return ParsedResults(results, errors)


def read_csv(content: bytes, delimiter: str, columns: dict[str, str]) -> ParsedResults:
    try:
        reader = csv.reader(
            StringIO(content.decode("utf-8-sig"), newline=""), delimiter=delimiter, strict=True
        )
        headers = [value.strip() for value in next(reader, [])]
        if any(headers.count(column) != 1 for column in columns.values()):
            raise ValidationError(
                "Kolom yang diperlukan harus tersedia tepat satu kali pada kepala CSV."
            )
        positions = {key: headers.index(column) for key, column in columns.items()}

        def rows() -> Iterable[Result]:
            for values in reader:
                if not any(value.strip() for value in values):
                    continue
                if len(values) != len(headers):
                    raise ValidationError(
                        f"Jumlah kolom pada baris {reader.line_num} tidak sesuai."
                    )
                yield Result(
                    reader.line_num,
                    **{key: values[index].strip() for key, index in positions.items()},
                )

        return normalize(rows())
    except (UnicodeDecodeError, csv.Error) as error:
        raise ValidationError("Gunakan CSV UTF-8 dengan pemisah dan format yang sesuai.") from error


def read_examtool(content: bytes, options: dict[str, str]) -> ParsedResults:
    return read_csv(
        content,
        ";",
        {
            "participant": "Nomor Peserta",
            "score": "Nilai Akhir",
            "raw_score": "Jumlah Raw Nilai",
            "session": "Sesi",
        },
    )


def read_generic_csv(content: bytes, options: dict[str, str]) -> ParsedResults:
    columns = {
        key: options[key]
        for key in ("participant", "score", "raw_score", "session")
        if options.get(key)
    }
    if len(set(columns.values())) != len(columns):
        raise ValidationError("Gunakan kolom CSV yang berbeda untuk setiap pemetaan.")
    return read_csv(content, options["delimiter"], columns)


def moodle_rows(
    rows: Iterable[tuple[int, tuple]],
    email_column: int,
    grade_column: int,
    state_column: int | None,
    maximum: str,
) -> Iterable[Result]:
    for row_number, row in rows:
        if row_number > MAX_ROWS + 100:
            raise ValidationError("Jumlah baris worksheet melebihi batas impor.")
        email = text(row[email_column])
        grade = text(row[grade_column])
        if not email and (
            not any(text(cell) for cell in row)
            or any(text(cell).lower() == "overall average" for cell in row)
        ):
            continue
        status = text(row[state_column]) if state_column is not None else ""
        yield Result(
            row_number, email, "" if grade == "-" else grade, maximum=maximum, status=status
        )


def read_moodle(content: bytes, options: dict[str, str]) -> ParsedResults:
    try:
        with ZipFile(BytesIO(content)) as archive:
            entries = archive.infolist()
            if len(entries) > 2048 or sum(entry.file_size for entry in entries) > 32 * 1024 * 1024:
                raise ValidationError("Ukuran workbook setelah diekstrak melebihi batas.")
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True, keep_links=False)
        try:
            for sheet in workbook.worksheets:
                rows = enumerate(sheet.iter_rows(max_col=256, values_only=True), 1)
                for number, cells in rows:
                    if number > 20:
                        break
                    headers = [text(cell) for cell in cells]
                    grades = [
                        (index, label.removeprefix("Grade/"))
                        for index, label in enumerate(headers)
                        if label.startswith("Grade/")
                    ]
                    if headers.count("Email address") != 1 or len(grades) != 1:
                        continue
                    email_column = headers.index("Email address")
                    grade_column, maximum = grades[0]
                    state_column = headers.index("State") if "State" in headers else None

                    return normalize(
                        moodle_rows(rows, email_column, grade_column, state_column, maximum)
                    )
        finally:
            workbook.close()
    except (
        BadZipFile,
        InvalidFileException,
        DefusedXmlException,
        ParseError,
        OSError,
        KeyError,
        ValueError,
        IndexError,
        NotImplementedError,
        RuntimeError,
    ) as error:
        raise ValidationError("Workbook XLSX tidak dapat dibaca.") from error
    raise ValidationError("Header Moodle Email address dan Grade/<maksimum> tidak ditemukan.")


@dataclass(frozen=True)
class Adapter:
    slug: str
    label: str
    extension: str
    read: Callable[[bytes, dict[str, str]], ParsedResults]


ADAPTERS = {
    adapter.slug: adapter
    for adapter in (
        Adapter("moodle", "Moodle", ".xlsx", read_moodle),
        Adapter("examtool", "ExamTool", ".csv", read_examtool),
        Adapter("csv-lain", "CSV aplikasi lain", ".csv", read_generic_csv),
    )
}
