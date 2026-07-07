import re

CPF_LENGTH = 11
CNPJ_LENGTH = 14
OLD_PLATE_PATTERN = re.compile(r"^[A-Z]{3}[0-9]{4}$")
MERCOSUL_PLATE_PATTERN = re.compile(r"^[A-Z]{3}[0-9][A-Z][0-9]{2}$")


def only_digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


def normalize_cpf(value: str) -> str:
    return only_digits(value)


def normalize_cnpj(value: str) -> str:
    return only_digits(value)


def normalize_plate(value: str) -> str:
    return "".join(character for character in value if character.isalnum()).upper()


def _has_repeated_digits(value: str) -> bool:
    return len(set(value)) == 1


def validate_cpf(value: str) -> str:
    cpf = normalize_cpf(value)
    if len(cpf) != CPF_LENGTH or _has_repeated_digits(cpf):
        raise ValueError("CPF inválido")

    first_sum = sum(int(cpf[index]) * (10 - index) for index in range(9))
    first_digit = (first_sum * 10) % 11
    if first_digit == 10:
        first_digit = 0

    second_sum = sum(int(cpf[index]) * (11 - index) for index in range(10))
    second_digit = (second_sum * 10) % 11
    if second_digit == 10:
        second_digit = 0

    if cpf[-2:] != f"{first_digit}{second_digit}":
        raise ValueError("CPF inválido")
    return cpf


def validate_cnpj(value: str) -> str:
    cnpj = normalize_cnpj(value)
    if len(cnpj) != CNPJ_LENGTH or _has_repeated_digits(cnpj):
        raise ValueError("CNPJ inválido")

    first_weights = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    first_sum = sum(
        int(digit) * weight for digit, weight in zip(cnpj[:12], first_weights, strict=True)
    )
    first_remainder = first_sum % 11
    first_digit = 0 if first_remainder < 2 else 11 - first_remainder

    second_weights = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    second_sum = sum(
        int(digit) * weight for digit, weight in zip(cnpj[:13], second_weights, strict=True)
    )
    second_remainder = second_sum % 11
    second_digit = 0 if second_remainder < 2 else 11 - second_remainder

    if cnpj[-2:] != f"{first_digit}{second_digit}":
        raise ValueError("CNPJ inválido")
    return cnpj


def validate_brazilian_plate(value: str) -> str:
    plate = normalize_plate(value)
    if OLD_PLATE_PATTERN.fullmatch(plate) or MERCOSUL_PLATE_PATTERN.fullmatch(plate):
        return plate
    raise ValueError("Placa inválida")
