"""Provider interfaces. Every Azure dependency sits behind one of these Protocols; the local
implementation is the default and is selected by environment variables (see `.env.example`)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

import pandas as pd


@runtime_checkable
class LLMProvider(Protocol):
    name: str

    def write(self, task: str, facts: dict, draft: str) -> str:
        """Return prose for `task`. Must only use numbers present in `facts`; `draft` is the template text."""
        ...


@dataclass
class PolicyChunk:
    section: str  # e.g. "4.1"
    title: str
    text: str
    score: float = 0.0


@runtime_checkable
class SearchProvider(Protocol):
    def search(self, query: str, k: int = 4) -> list[PolicyChunk]: ...

    def get(self, section: str) -> PolicyChunk | None: ...


@dataclass
class ParsedDocument:
    doc_type: str
    fields: dict
    confidence: float


@runtime_checkable
class DocParser(Protocol):
    def parse(self, content: bytes, filename: str) -> ParsedDocument: ...


@dataclass
class ConsentArtefact:
    consent_id: str
    factory_id: str
    purpose: str
    fi_types: list[str]
    data_from: date
    data_to: date
    expires_on: date
    frequency: str
    status: str


@runtime_checkable
class ConsentProvider(Protocol):
    def request(self, application_id: int, factory_id: str, as_of: date, actor: str) -> ConsentArtefact: ...

    def revoke(self, application_id: int, actor: str) -> ConsentArtefact: ...

    def active(self, application_id: int, as_of: date) -> ConsentArtefact | None: ...


@runtime_checkable
class LakeStore(Protocol):
    def profile(self, factory_id: str) -> dict: ...

    def profiles(self) -> pd.DataFrame: ...

    def history(self, factory_id: str, upto_month: int) -> pd.DataFrame: ...

    def features(self, factory_id: str, month: int) -> pd.Series: ...

    def scores(self, upto_month: int) -> pd.DataFrame: ...

    def ews_hits(self, factory_id: str, months: list[int]) -> pd.DataFrame: ...
