#!/usr/bin/env python

""" Version and helpers routines. """

import semver

Version = semver.Version
VersionRange = semver.VersionRange


def version_to_tag(ver: Version) -> str:
    """ Converts the version to Docker compliant tag string. """

    return str(ver).replace('+', '_')


def tag_to_version(tag: str) -> Version:
    """ Converts the version to Docker compliant tag string. """

    try:
        return Version.parse(tag.replace('_', '+'))
    except ValueError as err:
        raise ValueError(f'Failed to convert {tag} to version string: {err}')
