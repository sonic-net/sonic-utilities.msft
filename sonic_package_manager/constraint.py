#!/usr/bin/env python

""" Package version constraints module. """

import re
from abc import ABC
from dataclasses import dataclass, field
from typing import Dict, Union

import semver


class VersionConstraint(semver.VersionConstraint, ABC):
    """ Extends VersionConstraint from semver package. """

    @staticmethod
    def parse(constraint_expression: str) -> 'VersionConstraint':
        """ Parse version constraint.

        Args:
            constraint_expression: Expression syntax: "[[op][version]]+".
        Returns:
            The resulting VersionConstraint object.
        """

        return semver.parse_constraint(constraint_expression)


@dataclass
class ComponentConstraints:
    """ ComponentConstraints is a set of components version constraints. """

    components: Dict[str, VersionConstraint] = field(default_factory=dict)

    @staticmethod
    def parse(constraints: Dict) -> 'ComponentConstraints':
        """ Parse constraint from dictionary.

        Args:
            constraints: dictionary with component name
            as key and constraint expression as value

        Returns:
            ComponentConstraints object.

        """

        components = {component: VersionConstraint.parse(version)
                     for component, version in constraints.items()}
        return ComponentConstraints(components)

    def deparse(self) -> Dict[str, str]:
        """ Returns the manifest representation of components constraints.

        Returns:
            Dictionary of string keys and string values.

        """

        return {
            component: str(version) for component, version in self.components.items()
        }


@dataclass
class PackageConstraint:
    """ PackageConstraint is a package version constraint. """

    name: str
    constraint: VersionConstraint
    _components: ComponentConstraints = ComponentConstraints({})

    def __str__(self): return f'{self.name}{self.constraint}'

    @property
    def components(self): return self._components.components

    @staticmethod
    def from_string(constraint_expression: str) -> 'PackageConstraint':
        """ Parse package constraint string which contains a package
        name separated by a space with zero, one or more version constraint
        expressions. A variety of version matching operators are supported
        including >, <, ==, !=, ^, *. See Examples.

        Args:
            constraint_expression: Expression syntax "[package name] [[op][version]]+".

        Returns:
            PackageConstraint object.

        Examples:
            >>> PackageConstraint.parse('syncd^1.0.0').constraint
            <VersionRange (>=1.0.0,<2.0.0)>
            >>> PackageConstraint.parse('swss>1.3.2 <4.2.1').constraint
            <VersionRange (>1.3.2,<4.2.1)>
            >>> PackageConstraint.parse('swss').constraint
            <VersionRange (*)>
        """

        REQUIREMENT_SPECIFIER_RE = \
            r'(?P<name>[A-Za-z0-9_-]+)(?P<constraint>.*)'

        match = re.match(REQUIREMENT_SPECIFIER_RE, constraint_expression)
        if match is None:
            raise ValueError(f'Invalid constraint {constraint_expression}')
        groupdict = match.groupdict()
        name = groupdict.get('name')
        constraint = groupdict.get('constraint') or '*'
        return PackageConstraint(name, VersionConstraint.parse(constraint))

    @staticmethod
    def from_dict(constraint_dict: Dict) -> 'PackageConstraint':
        """ Parse package constraint information from dictionary. E.g:

        {
            "name": "swss",
            "version": "^1.0.0",
            "componenets": {
                "libswsscommon": "^1.0.0"
            }
        }

        Args:
            constraint_dict: Dictionary of constraint infromation.

        Returns:
            PackageConstraint object.
        """

        name = constraint_dict['name']
        version = VersionConstraint.parse(constraint_dict.get('version') or '*')
        components = ComponentConstraints.parse(constraint_dict.get('components', {}))
        return PackageConstraint(name, version, components)

    @staticmethod
    def parse(constraint: Union[str, Dict]) -> 'PackageConstraint':
        """ Parse constraint from string expression or dictionary.

        Args:
            constraint: string or dictionary. Check from_str() and from_dict() methods.

        Returns:
            PackageConstraint object.

        """

        if type(constraint) is str:
            return PackageConstraint.from_string(constraint)
        elif type(constraint) is dict:
            return PackageConstraint.from_dict(constraint)
        else:
            raise ValueError('Input argument should be either str or dict')

    def deparse(self) -> Dict:
        """ Returns the manifest representation of package constraint.

        Returns:
            Dictionary in manifest representation.

        """

        return {
            'name': self.name,
            'version': str(self.constraint),
            'components': self._components.deparse(),
        }
