from __future__ import annotations

from typing import Any, Dict, Iterable, Optional


FIELD_LABELS = {
    "patient_name": "Nome do paciente",
    "age": "Idade",
    "main_complaint": "Queixa principal",
    "symptoms": "Sintomas",
    "weight_kg": "Peso (kg)",
    "height_cm": "Altura (cm)",
    "prior_cannabis_use": "Uso prévio de cannabis",
    "conditions": "Condições clínicas",
    "current_medications": "Medicações atuais",
    "allergies": "Alergias",
    "medical_history": "Histórico médico",
    "risk_level": "Nível de risco",
}

REQUIRED_FIELDS = (
    "patient_name",
    "age",
    "main_complaint",
    "symptoms",
    "weight_kg",
    "height_cm",
    "prior_cannabis_use",
)

OPTIONAL_FIELDS = (
    "conditions",
    "current_medications",
    "allergies",
    "medical_history",
    "risk_level",
)


class PrescriptionContractError(ValueError):
    def __init__(self, message: str, details: dict):
        super().__init__(message)
        self.details = details


def _get_nested(payload: Any, path: str) -> Any:
    current = payload
    for chunk in path.split("."):
        if not isinstance(current, dict) or chunk not in current:
            return None
        current = current[chunk]
    return current


def _normalize_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", ".")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_list(value: Any) -> Optional[list[str]]:
    if value is None:
        return None
    if isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
        return items or None
    if isinstance(value, str):
        items = [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]
        return items or None
    return None


def _normalize_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "sim", "s", "yes", "y"}:
            return True
        if normalized in {"false", "0", "nao", "não", "n", "no"}:
            return False
    return None


def _first_present(candidates: Iterable[tuple[str, Any]], normalizer) -> tuple[Any, Optional[str]]:
    for source, raw_value in candidates:
        normalized = normalizer(raw_value)
        if normalized is not None:
            return normalized, source
    return None, None


def _field_definition(field: str, report: dict, overrides: dict) -> tuple[Any, Optional[str]]:
    anamnesis = report.get("anamnesis_data") if isinstance(report, dict) else {}
    clinical_analysis = report.get("clinical_analysis") if isinstance(report, dict) else {}

    definitions: dict[str, tuple[Iterable[tuple[str, Any]], Any]] = {
        "patient_name": (
            (
                ("payload.patient_name", overrides.get("patient_name")),
                ("report.patient_name", report.get("patient_name")),
                ("report.anamnesis_data.patient_name", _get_nested(anamnesis, "patient_name")),
            ),
            _normalize_string,
        ),
        "age": (
            (
                ("payload.age", overrides.get("age")),
                ("report.anamnesis_data.age", _get_nested(anamnesis, "age")),
            ),
            _normalize_int,
        ),
        "main_complaint": (
            (
                ("payload.main_complaint", overrides.get("main_complaint")),
                ("report.anamnesis_data.main_complaint", _get_nested(anamnesis, "main_complaint")),
                ("report.anamnesis_data.chief_complaint", _get_nested(anamnesis, "chief_complaint")),
            ),
            _normalize_string,
        ),
        "symptoms": (
            (
                ("payload.symptoms", overrides.get("symptoms")),
                ("report.anamnesis_data.symptoms", _get_nested(anamnesis, "symptoms")),
            ),
            _normalize_list,
        ),
        "weight_kg": (
            (
                ("payload.weight_kg", overrides.get("weight_kg")),
                ("report.anamnesis_data.vital_signs.weight_kg", _get_nested(anamnesis, "vital_signs.weight_kg")),
                ("report.anamnesis_data.sinais_vitais.weight_kg", _get_nested(anamnesis, "sinais_vitais.weight_kg")),
                ("report.anamnesis_data.vitals.weight_kg", _get_nested(anamnesis, "vitals.weight_kg")),
                ("report.anamnesis_data.weight_kg", _get_nested(anamnesis, "weight_kg")),
            ),
            _normalize_float,
        ),
        "height_cm": (
            (
                ("payload.height_cm", overrides.get("height_cm")),
                ("report.anamnesis_data.vital_signs.height_cm", _get_nested(anamnesis, "vital_signs.height_cm")),
                ("report.anamnesis_data.sinais_vitais.height_cm", _get_nested(anamnesis, "sinais_vitais.height_cm")),
                ("report.anamnesis_data.vitals.height_cm", _get_nested(anamnesis, "vitals.height_cm")),
                ("report.anamnesis_data.height_cm", _get_nested(anamnesis, "height_cm")),
            ),
            _normalize_float,
        ),
        "prior_cannabis_use": (
            (
                ("payload.prior_cannabis_use", overrides.get("prior_cannabis_use")),
                ("report.anamnesis_data.prior_cannabis_use", _get_nested(anamnesis, "prior_cannabis_use")),
                ("report.anamnesis_data.uso_previo_cannabis", _get_nested(anamnesis, "uso_previo_cannabis")),
                ("report.anamnesis_data.cannabis_history.prior_use", _get_nested(anamnesis, "cannabis_history.prior_use")),
                ("report.anamnesis_data.cannabis_use.prior_use", _get_nested(anamnesis, "cannabis_use.prior_use")),
            ),
            _normalize_bool,
        ),
        "conditions": (
            (
                ("payload.conditions", overrides.get("conditions")),
                ("report.clinical_analysis.probable_conditions", _get_nested(clinical_analysis, "probable_conditions")),
            ),
            _normalize_list,
        ),
        "current_medications": (
            (
                ("payload.current_medications", overrides.get("current_medications")),
                ("report.anamnesis_data.current_medications", _get_nested(anamnesis, "current_medications")),
            ),
            _normalize_list,
        ),
        "allergies": (
            (
                ("payload.allergies", overrides.get("allergies")),
                ("report.anamnesis_data.allergies", _get_nested(anamnesis, "allergies")),
            ),
            _normalize_list,
        ),
        "medical_history": (
            (
                ("payload.medical_history", overrides.get("medical_history")),
                ("report.anamnesis_data.medical_history", _get_nested(anamnesis, "medical_history")),
                ("report.anamnesis_data.historico_medico", _get_nested(anamnesis, "historico_medico")),
            ),
            _normalize_string,
        ),
        "risk_level": (
            (
                ("payload.risk_level", overrides.get("risk_level")),
                ("report.clinical_analysis.risk_level", _get_nested(clinical_analysis, "risk_level")),
                ("default.risk_level", "moderado"),
            ),
            _normalize_string,
        ),
    }

    candidates, normalizer = definitions[field]
    return _first_present(candidates, normalizer)


def build_prescription_contract(report: Optional[Dict[str, Any]] = None, overrides: Optional[Dict[str, Any]] = None) -> dict:
    report = report or {}
    overrides = overrides or {}

    resolved_values: dict[str, Any] = {}
    source_map: dict[str, str] = {}

    for field in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS):
        value, source = _field_definition(field, report, overrides)
        if value is None:
            continue
        resolved_values[field] = value
        if source:
            source_map[field] = source

    missing_required_fields = [
        {"field": field, "label": FIELD_LABELS[field]}
        for field in REQUIRED_FIELDS
        if field not in resolved_values
    ]
    missing_optional_fields = [
        {"field": field, "label": FIELD_LABELS[field]}
        for field in OPTIONAL_FIELDS
        if field not in resolved_values
    ]

    ready = not missing_required_fields
    if ready:
        message = "Contrato clínico mínimo pronto para cálculo seguro de dosagem."
    else:
        missing_labels = ", ".join(item["label"] for item in missing_required_fields)
        message = f"Prescrição segura ainda exige: {missing_labels}."

    return {
        "ready": ready,
        "readiness": "ready" if ready else "missing_required",
        "message": message,
        "required_fields": [{"field": field, "label": FIELD_LABELS[field]} for field in REQUIRED_FIELDS],
        "missing_required_fields": missing_required_fields,
        "missing_optional_fields": missing_optional_fields,
        "resolved_values": resolved_values,
        "source_map": source_map,
        "report_id": report.get("id"),
        "patient_id": report.get("patient_id"),
    }


def build_dosage_input_or_raise(report: Optional[Dict[str, Any]] = None, overrides: Optional[Dict[str, Any]] = None) -> dict:
    contract = build_prescription_contract(report=report, overrides=overrides)
    if not contract["ready"]:
        raise PrescriptionContractError(contract["message"], contract)
    return contract["resolved_values"]
