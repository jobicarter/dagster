from typing import (
    Callable,
    Dict,
    Generic,
    Mapping,
    Optional,
    Sequence,
    Type,
    Union,
    cast,
)

import dagster._check as check
from dagster._core.errors import DagsterInvariantViolationError

from .valid_definitions import RepositoryLevelDefinition


class _CacheingDefinitionIndex(Generic[RepositoryLevelDefinition]):
    def __init__(
        self,
        definition_class: Type[RepositoryLevelDefinition],
        definition_class_name: str,
        definition_kind: str,
        definitions: Mapping[
            str, Union[RepositoryLevelDefinition, Callable[[], RepositoryLevelDefinition]]
        ],
        validation_fn: Callable[[RepositoryLevelDefinition], RepositoryLevelDefinition],
        lazy_definitions_fn: Optional[Callable[[], Sequence[RepositoryLevelDefinition]]] = None,
    ):
        """
        Args:
            definitions: A dictionary of definition names to definitions or functions that load
                definitions.
            lazy_definitions_fn: A function for loading a list of definitions whose names are not
                even known until loaded.

        """
        for key, definition in definitions.items():
            check.invariant(
                isinstance(definition, definition_class) or callable(definition),
                "Bad definition for {definition_kind} {key}: must be {definition_class_name} or "
                "callable, got {type_}".format(
                    definition_kind=definition_kind,
                    key=key,
                    definition_class_name=definition_class_name,
                    type_=type(definition),
                ),
            )

        self._definition_class: Type[RepositoryLevelDefinition] = definition_class
        self._definition_class_name = definition_class_name
        self._definition_kind = definition_kind
        self._validation_fn: Callable[
            [RepositoryLevelDefinition], RepositoryLevelDefinition
        ] = validation_fn

        self._definitions: Mapping[
            str, Union[RepositoryLevelDefinition, Callable[[], RepositoryLevelDefinition]]
        ] = definitions
        self._definition_cache: Dict[str, RepositoryLevelDefinition] = {}
        self._definition_names: Optional[Sequence[str]] = None

        self._lazy_definitions_fn: Callable[
            [], Sequence[RepositoryLevelDefinition]
        ] = lazy_definitions_fn or (lambda: [])
        self._lazy_definitions: Optional[Sequence[RepositoryLevelDefinition]] = None

        self._all_definitions: Optional[Sequence[RepositoryLevelDefinition]] = None

    def _get_lazy_definitions(self) -> Sequence[RepositoryLevelDefinition]:
        if self._lazy_definitions is None:
            self._lazy_definitions = self._lazy_definitions_fn()
            for definition in self._lazy_definitions:
                self._validate_and_cache_definition(definition, definition.name)

        return self._lazy_definitions

    def get_definition_names(self) -> Sequence[str]:
        if self._definition_names:
            return self._definition_names

        lazy_names = []
        for definition in self._get_lazy_definitions():
            strict_definition = self._definitions.get(definition.name)
            if strict_definition:
                check.invariant(
                    strict_definition == definition,
                    f"Duplicate definition found for {definition.name}",
                )
            else:
                lazy_names.append(definition.name)

        self._definition_names = list(self._definitions.keys()) + lazy_names
        return self._definition_names

    def has_definition(self, definition_name: str) -> bool:
        check.str_param(definition_name, "definition_name")

        return definition_name in self.get_definition_names()

    def get_all_definitions(self) -> Sequence[RepositoryLevelDefinition]:
        if self._all_definitions is not None:
            return self._all_definitions

        self._all_definitions = list(
            sorted(
                map(self.get_definition, self.get_definition_names()),
                key=lambda definition: definition.name,
            )
        )
        return self._all_definitions

    def get_definition(self, definition_name: str) -> RepositoryLevelDefinition:
        check.str_param(definition_name, "definition_name")

        if not self.has_definition(definition_name):
            raise DagsterInvariantViolationError(
                "Could not find {definition_kind} '{definition_name}'. Found: "
                "{found_names}.".format(
                    definition_kind=self._definition_kind,
                    definition_name=definition_name,
                    found_names=", ".join(
                        [
                            "'{found_name}'".format(found_name=found_name)
                            for found_name in self.get_definition_names()
                        ]
                    ),
                )
            )

        if definition_name in self._definition_cache:
            return self._definition_cache[definition_name]

        definition_source = self._definitions[definition_name]

        if isinstance(definition_source, self._definition_class):
            self._definition_cache[definition_name] = self._validation_fn(definition_source)
            return definition_source
        else:
            definition = cast(Callable, definition_source)()
            self._validate_and_cache_definition(definition, definition_name)
            return definition

    def _validate_and_cache_definition(
        self, definition: RepositoryLevelDefinition, definition_dict_key: str
    ):
        check.invariant(
            isinstance(definition, self._definition_class),
            "Bad constructor for {definition_kind} {definition_name}: must return "
            "{definition_class_name}, got value of type {type_}".format(
                definition_kind=self._definition_kind,
                definition_name=definition_dict_key,
                definition_class_name=self._definition_class_name,
                type_=type(definition),
            ),
        )
        check.invariant(
            definition.name == definition_dict_key,
            "Bad constructor for {definition_kind} '{definition_name}': name in "
            "{definition_class_name} does not match: got '{definition_def_name}'".format(
                definition_kind=self._definition_kind,
                definition_name=definition_dict_key,
                definition_class_name=self._definition_class_name,
                definition_def_name=definition.name,
            ),
        )
        self._definition_cache[definition_dict_key] = self._validation_fn(definition)
