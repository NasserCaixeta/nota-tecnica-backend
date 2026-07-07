import pytest

from app.core.validators import (
    normalize_cnpj,
    normalize_cpf,
    normalize_plate,
    validate_brazilian_plate,
    validate_cnpj,
    validate_cpf,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("123.456.789-09", "12345678909"),
        (" 12345678909 ", "12345678909"),
    ],
)
def test_normalize_cpf(raw: str, expected: str) -> None:
    assert normalize_cpf(raw) == expected


@pytest.mark.parametrize("value", ["12345678909", "529.982.247-25"])
def test_validate_cpf_accepts_valid_values(value: str) -> None:
    assert validate_cpf(value) == normalize_cpf(value)


@pytest.mark.parametrize("value", ["12345678901", "00000000000", "111.111.111-11", "123"])
def test_validate_cpf_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="CPF inválido"):
        validate_cpf(value)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("04.252.011/0001-10", "04252011000110"),
        (" 04252011000110 ", "04252011000110"),
    ],
)
def test_normalize_cnpj(raw: str, expected: str) -> None:
    assert normalize_cnpj(raw) == expected


@pytest.mark.parametrize("value", ["04.252.011/0001-10", "40.688.134/0001-61"])
def test_validate_cnpj_accepts_valid_values(value: str) -> None:
    assert validate_cnpj(value) == normalize_cnpj(value)


@pytest.mark.parametrize("value", ["12345678000190", "00000000000000", "11.111.111/1111-11", "123"])
def test_validate_cnpj_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="CNPJ inválido"):
        validate_cnpj(value)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("abc-1234", "ABC1234"),
        ("abc 1d23", "ABC1D23"),
    ],
)
def test_normalize_plate(raw: str, expected: str) -> None:
    assert normalize_plate(raw) == expected


@pytest.mark.parametrize("value", ["ABC1234", "abc-1234", "ABC1D23", "abc 1d23"])
def test_validate_brazilian_plate_accepts_old_and_mercosul(value: str) -> None:
    assert validate_brazilian_plate(value) in {"ABC1234", "ABC1D23"}


@pytest.mark.parametrize("value", ["AB12345", "ABC12D3", "ABC123", "ABC12345", "123ABCD"])
def test_validate_brazilian_plate_rejects_invalid_formats(value: str) -> None:
    with pytest.raises(ValueError, match="Placa inválida"):
        validate_brazilian_plate(value)
