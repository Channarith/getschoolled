"""3D multimodal object recognition: detect, identify, ask, and train."""

from .ask import answer_about, intent_of
from .gallery import ObjectGallery
from .pipeline import observe
from .sensors import DisconnectedSensors, SensorBundle
from .train import train_samples, train_samples_blocking
from .types import Answer, Frame, Observation, TrainSample

__all__ = [
    "Answer",
    "DisconnectedSensors",
    "Frame",
    "ObjectGallery",
    "Observation",
    "SensorBundle",
    "TrainSample",
    "answer_about",
    "intent_of",
    "observe",
    "train_samples",
    "train_samples_blocking",
]
