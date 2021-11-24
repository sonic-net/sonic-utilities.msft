#!/usr/bin/env python

from dataclasses import dataclass, field

import json
import tarfile
from typing import Dict, Optional

from sonic_package_manager import utils
from sonic_package_manager.errors import MetadataError
from sonic_package_manager.manifest import Manifest
from sonic_package_manager.version import Version


def translate_plain_to_tree(plain: Dict[str, str], sep='.') -> Dict:
    """ Convert plain key/value dictionary into
    a tree by spliting the key with '.'

    Args:
        plain: Dictionary to convert into tree-like structure.
            Keys in this dictionary have to be in a format:
            "[key0].+", e.g: "com.azure.sonic" that
            will be converted into tree like struct:

                {
                    "com": {
                        "azure": {
                            "sonic": {}
                        }
                    }
                }
        sep: Seperator string

    Returns:
        Tree like structure

    """

    res = {}
    for key, value in plain.items():
        if sep not in key:
            res[key] = value
            continue
        namespace, key = key.split(sep, 1)
        res.setdefault(namespace, {})
        utils.deep_update(res[namespace], translate_plain_to_tree({key: value}))
    return res


@dataclass
class Metadata:
    """ Package metadata object that can be retrieved from
    OCI image manifest. """

    manifest: Manifest
    components: Dict[str, Version] = field(default_factory=dict)
    yang_module_str: Optional[str] = None


class MetadataResolver:
    """ Resolve metadata for package from different sources. """

    def __init__(self, docker, registry_resolver):
        self.docker = docker
        self.registry_resolver = registry_resolver

    def from_local(self, image: str) -> Metadata:
        """ Reads manifest from locally installed docker image.

        Args:
            image: Docker image ID
        Returns:
            Metadata
        Raises:
            MetadataError
        """

        labels = self.docker.labels(image)
        if labels is None:
            raise MetadataError('No manifest found in image labels')

        return self.from_labels(labels)

    def from_registry(self,
                      repository: str,
                      reference: str) -> Metadata:
        """ Reads manifest from remote registry.

        Args:
            repository: Repository to pull image from
            reference: Reference, either tag or digest
        Returns:
            Metadata
        Raises:
            MetadataError
        """

        registry = self.registry_resolver.get_registry_for(repository)

        manifest = registry.manifest(repository, reference)
        digest = manifest['config']['digest']

        blob = registry.blobs(repository, digest)
        labels = blob['config']['Labels']
        if labels is None:
            raise MetadataError('No manifest found in image labels')

        return self.from_labels(labels)

    def from_tarball(self, image_path: str) -> Metadata:
        """ Reads manifest image tarball.
        Args:
            image_path: Path to image tarball.
        Returns:
            Manifest
        Raises:
            MetadataError
        """

        with tarfile.open(image_path) as image:
            manifest = json.loads(image.extractfile('manifest.json').read())

            blob = manifest[0]['Config']
            image_config = json.loads(image.extractfile(blob).read())
            labels = image_config['config']['Labels']
            if labels is None:
                raise MetadataError('No manifest found in image labels')

            return self.from_labels(labels)

    @classmethod
    def from_labels(cls, labels: Dict[str, str]) -> Metadata:
        """ Get manifest from image labels.

        Args:
            labels: key, value string pairs
        Returns:
            Metadata
        Raises:
            MetadataError
        """

        metadata_dict = translate_plain_to_tree(labels)
        try:
            sonic_metadata = metadata_dict['com']['azure']['sonic']
        except KeyError:
            raise MetadataError('No metadata found in image labels')

        try:
            manifest_string = sonic_metadata['manifest']
        except KeyError:
            raise MetadataError('No manifest found in image labels')

        try:
            manifest_dict = json.loads(manifest_string)
        except (ValueError, TypeError) as err:
            raise MetadataError(f'Failed to parse manifest JSON: {err}')

        components = {}
        if 'versions' in sonic_metadata:
            for component, version in sonic_metadata['versions'].items():
                try:
                    components[component] = Version.parse(version)
                except ValueError as err:
                    raise MetadataError(f'Failed to parse component version: {err}')

        yang_module_str = sonic_metadata.get('yang-module')

        return Metadata(Manifest.marshal(manifest_dict), components, yang_module_str)
