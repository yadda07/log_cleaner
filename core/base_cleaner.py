from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class CleanResult:
    """Rapport structuré d'une opération de nettoyage."""

    success: bool
    removed: int = 0
    errors: int = 0
    paths_failed: Tuple[str, ...] = ()
    paths_succeeded: Tuple[str, ...] = ()
    elapsed_ms: float = 0.0
    message: str = ""


class Cleaner(ABC):
    """Contrat pour les opérations de nettoyage du plugin."""

    @property
    @abstractmethod
    def label(self):
        """Nom court affiché dans le feedback utilisateur."""
        pass

    @property
    @abstractmethod
    def tooltip(self):
        """Texte de l'infobulle du bouton."""
        pass

    @property
    @abstractmethod
    def icon_type(self):
        """Identifiant d'icône pour le bouton UI (ex: 'trash', 'broom')."""
        pass

    @property
    def thread_safe(self):
        """Indique si le nettoyage peut être exécuté hors du thread GUI."""
        return True

    @abstractmethod
    def clean(self):
        """Exécute le nettoyage.

        Returns:
            CleanResult: rapport structuré de l'opération.
        """
        pass
