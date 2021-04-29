#!/usr/bin/env python

from click.testing import CliRunner

from sonic_package_manager import main


def test_show_changelog(package_manager, fake_metadata_resolver):
    """ Test case for "sonic-package-manager package show changelog [NAME]" """

    runner = CliRunner()
    changelog = {
      "1.0.0": {
        "changes": ["Initial release"],
        "author": "Stepan Blyshchak",
        "email": "stepanb@nvidia.com",
        "date": "Mon, 25 May 2020 12:24:30 +0300"
      },
      "1.1.0": {
        "changes": [
          "Added functionality",
          "Bug fixes"
        ],
        "author": "Stepan Blyshchak",
        "email": "stepanb@nvidia.com",
        "date": "Fri, 23 Oct 2020 12:26:08 +0300"
      }
    }
    manifest = fake_metadata_resolver.metadata_store['Azure/docker-test']['1.6.0']['manifest']
    manifest['package']['changelog'] = changelog

    expected_output = """\
1.0.0:

    • Initial release

        Stepan Blyshchak (stepanb@nvidia.com) Mon, 25 May 2020 12:24:30 +0300

1.1.0:

    • Added functionality
    • Bug fixes

        Stepan Blyshchak (stepanb@nvidia.com) Fri, 23 Oct 2020 12:26:08 +0300

"""

    result = runner.invoke(main.show.commands['package'].commands['changelog'],
                           ['test-package'], obj=package_manager)

    assert result.exit_code == 0
    assert result.output == expected_output


def test_show_changelog_no_changelog(package_manager):
    """ Test case for "sonic-package-manager package show changelog [NAME]"
    when there is no changelog provided by package. """

    runner = CliRunner()
    result = runner.invoke(main.show.commands['package'].commands['changelog'], ['test-package'], obj=package_manager)

    assert result.exit_code == 1
    assert result.output == 'Failed to print package changelog: No changelog for package test-package\n'
