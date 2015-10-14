# -*- Mode:Python; indent-tabs-mode:nil; tab-width:4 -*-
#
# Copyright © 2015 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import snapcraft
import os


class RosCorePlugin(snapcraft.BasePlugin):

    _PLUGIN_STAGE_PACKAGES = [
    ]

    _PLUGIN_STAGE_SOURCES = (
        'deb http://packages.ros.org/ros/ubuntu/ vivid main\n'
        'deb http://archive.ubuntu.com/ubuntu/ vivid main universe\n'
        'deb http://archive.ubuntu.com/ubuntu/ vivid-updates main universe\n'
        'deb http://archive.ubuntu.com/ubuntu/ vivid-security main universe\n')

    @classmethod
    def schema(cls):
        return {
            '$schema': 'http://json-schema.org/draft-04/schema#',
            'type': 'object',
            'properties': {
                'rosversion': {
                    'type': 'string',
                },
            }
        }

    def __init__(self, name, options):
        self.rosversion = options.rosversion or 'jade'
        self._PLUGIN_STAGE_PACKAGES.append(
            'ros-' + self.rosversion + '-ros-core'
        )
        super().__init__(name, options)

    def build(self):
        dirname = os.path.join(self.installdir, 'bin')
        os.makedirs(dirname, exist_ok=True)

        filename = os.path.join(dirname, self.name + '-rosmaster-service')
        with open(filename, 'w') as f:
            rosdir = os.path.join(
                '$SNAP_APP_PATH',
                'opt',
                'ros',
                self.rosversion
            )

            f.write('\n'.join([
                '#!/bin/sh',
                '_CATKIN_SETUP_DIR={}'.format(rosdir),
                'source {}'.format(rosdir + '/setup.sh'),
                'exec {}'.format(rosdir + '/bin/rosmaster')
            ]))
        return True

    def snap_fileset(self):
        return [
            os.path.join('bin', self.name + '-rosmaster-service')
        ]

    def snap(self, config={}):
        if 'services' not in config.data:
            config.data['services'] = {}

        rosserv = {
            'start': os.path.join('bin', self.name + '-rosemaster-service'),
            'description': 'ROS Master service',
            'ports': {
                'internal': {
                    'rosmaster': {
                        'port': '11311/tcp',
                        'negotiable': False
                    }
                }
            }
        }

        config.data['services'][self.name + '-rosmaster'] = rosserv
        return True
