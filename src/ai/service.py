import logging
from typing import Dict, Any

from pydantic import ValidationError

from ai.schemas import AnamnesisInput
from ai.pipeline import CannabIAPipeline


logger = logging.getLogger("cannabia.ai")


class CannabIAService:
    """
    Camada de serviço da IA.
    Responsável por:
    - Validar entrada
    - Executar pipeline
    - Tratar erros
    - Retornar resposta estruturada
    """

    def __init__(self):
        self.pipeline = CannabIAPipeline()

    def process_patient_case(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recebe dict bruto (ex: vindo da API),
        valida com Pydantic,
        executa pipeline,
        retorna resultado estruturado.
        """

        try:
            anamnesis = AnamnesisInput(**data)
        except ValidationError as e:
            logger.error("Erro de validação de entrada: %s", e)
            raise ValueError(f"Dados inválidos: {e}")

        try:
            result = self.pipeline.run(anamnesis)
            return result
        except Exception as e:
            logger.exception("Erro durante execução do pipeline")
            raise RuntimeError(f"Erro interno no processamento clínico: {e}")
