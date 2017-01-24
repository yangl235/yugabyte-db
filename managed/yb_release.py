#!/usr/bin/env python
# Copyright (c) YugaByte, Inc.

import os
import logging
import shutil
import sys
import argparse

from subprocess import check_output, CalledProcessError
from ybops.utils import init_env, log_message, get_release_file, publish_release, \
    generate_checksum, latest_release, download_release
from ybops.common.exceptions import YBOpsRuntimeError

"""This script is basically builds and packages yugaware application.
  - Builds the React API and generates production files (js, css, etc)
  - Run sbt packaging command to package yugaware along with the react files
  If we want to publish a docker image, then we just generate and publish
  or else, we would do the following to generate a release file.
  - Rename the package file to have the commit sha in it
  - Generate checksum for the package
  - Publish the package to s3

"""

parser = argparse.ArgumentParser()
release_types = ["docker", "file"]
parser.add_argument('--type', action='store', choices=release_types,
                   default="file", help='Provide a release type')
parser.add_argument('--publish', action='store_true',
                    help='Publish release to S3.')
parser.add_argument('--destination', help='Copy release to Destination folder.')
args = parser.parse_args()

try:
    init_env(logging.INFO)
    script_dir = os.path.dirname(os.path.realpath(__file__))
    log_message(logging.INFO, "Building/Packaging UI code")
    check_output(["rm", "-rf", "node_modules"], cwd=os.path.join(script_dir, 'ui'))
    check_output(["npm", "install"], cwd=os.path.join(script_dir, 'ui'))
    check_output(["npm", "run", "build"], cwd=os.path.join(script_dir, 'ui'))

    check_output(["sbt", "clean"])

    if args.type == "docker":
        # TODO, make these params, so we can specify which version of devops
        # and yugabyte software we want to be bundled, also be able to specify
        # local builds
        log_message(logging.INFO, "Download latest devops and yugabyte packages")
        devops_release = latest_release("snapshots.yugabyte.com", "devops")
        yugabyte_release = latest_release("snapshots.yugabyte.com", "yugabyte")
        packages_folder = os.path.join(script_dir, "target", "docker", "stage", "packages")
        if not os.path.exists(packages_folder):
            os.makedirs(packages_folder)

        download_release("snapshots.yugabyte.com", "devops", devops_release, packages_folder)
        download_release("snapshots.yugabyte.com", "yugabyte", yugabyte_release, packages_folder)

        if args.publish:
            log_message(logging.INFO, "Package and publish docker image to replicated")
            check_output(["sbt", "docker:publish"])
        else:
            log_message(logging.INFO, "Package and publish docker image locally")
            check_output(["sbt", "docker:publishLocal"])

        log_message(logging.INFO, "Cleanup the packages folder")
        shutil.rmtree(packages_folder)

    else:
        log_message(logging.INFO, "Kick off SBT universal packaging")
        check_output(["sbt", "universal:packageZipTarball"])

        log_message(logging.INFO, "Get a release file name based on the current commit sha")
        release_file = get_release_file(script_dir, 'yugaware')
        packaged_file = os.path.join(script_dir, 'target', 'universal', 'yugaware-1.0-SNAPSHOT.tgz')

        log_message(logging.INFO, "Rename the release file to have current commit sha")
        shutil.copyfile(packaged_file, release_file)

        if args.publish:
            log_message(logging.INFO, "Publish the release to S3")
            generate_checksum(release_file)
            publish_release(script_dir, release_file)
        elif args.destination:
            if not os.path.exists(args.destination):
                raise YBOpsRuntimeError("Destination {} not a directory.".format(args.destination))
            shutil.copy(release_file, args.destination)

except (CalledProcessError, OSError, RuntimeError, TypeError, NameError) as e:
    log_message(logging.ERROR, e)
