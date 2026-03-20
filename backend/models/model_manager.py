import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Type

from models.predictor_v1 import ContextWindowPredictor, TinySleepNetPredictor
from models.sleep_stage_v8 import SleepStageNetV8
from models.tiny_sleepnet import TinySleepNetRepro
from services.analyzer import SleepAnalyzer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelFamilyConfig:
    key: str
    label: str
    folder_name: str
    model_class: Type
    predictor_class: Type
    predictor_kwargs: Dict[str, int] = field(default_factory=dict)


@dataclass
class LoadedModel:
    model_id: str
    model_name: str
    model_family: str
    model_family_label: str
    model_path: str
    analyzer: SleepAnalyzer

    def to_dict(self):
        return {
            "id": self.model_id,
            "name": self.model_name,
            "family": self.model_family,
            "family_label": self.model_family_label,
            "path": self.model_path,
        }


DEFAULT_MODEL_FAMILIES = [
    ModelFamilyConfig(
        key="sleep_stage_v8",
        label="SleepStageV8",
        folder_name="sleep_stage_v8",
        model_class=SleepStageNetV8,
        predictor_class=ContextWindowPredictor,
        predictor_kwargs={"window_size": 15},
    ),
    ModelFamilyConfig(
        key="tiny_sleepnet",
        label="TinySleepNet",
        folder_name="tiny_sleepnet",
        model_class=TinySleepNetRepro,
        predictor_class=TinySleepNetPredictor,
        predictor_kwargs={"seq_length": 20},
    ),
]


class ModelManager:
    def __init__(self, data_dir: str, device: str = "cuda", family_configs=None):
        self.data_dir = Path(data_dir)
        self.device = device
        self.family_configs = family_configs or DEFAULT_MODEL_FAMILIES
        self.models: Dict[str, LoadedModel] = {}
        self.default_model_id: Optional[str] = None

    def load_all(self):
        self.models.clear()
        self.default_model_id = None
        self.data_dir.mkdir(parents=True, exist_ok=True)

        for family in self.family_configs:
            family_dir = self.data_dir / family.folder_name
            family_dir.mkdir(parents=True, exist_ok=True)

            for model_path in sorted(family_dir.glob("*.pth")):
                model_id = f"{family.key}/{model_path.name}"
                try:
                    predictor_kwargs = dict(family.predictor_kwargs)
                    if family.key == "sleep_stage_v8":
                        model_date_code = self._extract_model_date_code(model_path.name)
                        if model_date_code is not None and model_date_code >= 319:
                            predictor_kwargs["preprocess_mode"] = "raw_microvolt"
                        else:
                            predictor_kwargs["preprocess_mode"] = "legacy_filtered_zscore"
                        logger.info(
                            "SleepStageV8 model %s -> preprocess_mode=%s (date_code=%s)",
                            model_path.name,
                            predictor_kwargs["preprocess_mode"],
                            model_date_code,
                        )

                    predictor = family.predictor_class(
                        model_path=str(model_path),
                        model_class=family.model_class,
                        device=self.device,
                        **predictor_kwargs,
                    )
                    predictor.load_model()

                    loaded_model = LoadedModel(
                        model_id=model_id,
                        model_name=model_path.name,
                        model_family=family.key,
                        model_family_label=family.label,
                        model_path=str(model_path),
                        analyzer=SleepAnalyzer(
                            predictor=predictor,
                            model_id=model_id,
                            model_name=model_path.name,
                            model_family=family.key,
                        ),
                    )
                    self.models[model_id] = loaded_model
                    if self.default_model_id is None:
                        self.default_model_id = model_id
                except Exception as exc:
                    logger.exception("Failed to load model %s: %s", model_path, exc)

        logger.info("Loaded %s model(s) from %s", len(self.models), self.data_dir)

    @staticmethod
    def _extract_model_date_code(filename: str) -> Optional[int]:
        model_match = re.search(r"model(\d{4})\d*", filename, re.IGNORECASE)
        if model_match:
            return int(model_match.group(1))

        fold_match = re.search(r"fold_\d+_(\d{4})_\d+", filename, re.IGNORECASE)
        if fold_match:
            return int(fold_match.group(1))

        generic_match = re.search(r"(^|[_-])(\d{4})(?:[_-]|\.|$)", filename)
        if generic_match:
            return int(generic_match.group(2))

        return None

    def has_models(self):
        return bool(self.models)

    def list_models(self) -> List[Dict[str, str]]:
        return [self.models[model_id].to_dict() for model_id in sorted(self.models)]

    def get_model(self, model_id: Optional[str] = None) -> LoadedModel:
        if not self.models:
            raise ValueError("No models are loaded")

        selected_id = model_id or self.default_model_id
        if selected_id in self.models:
            return self.models[selected_id]

        matched = [model for model in self.models.values() if model.model_name == selected_id]
        if len(matched) == 1:
            return matched[0]

        raise KeyError(f"Model not found: {model_id}")
