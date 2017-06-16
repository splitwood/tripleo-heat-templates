# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Gather and distinguish PCI devices from inventory."""

import collections
import json
import os

from oslo_config import cfg

from ironic_inspector.common.i18n import _
from ironic_inspector.plugins import base
from ironic_inspector import utils

STORE_LOCAL_OPTS = [
    cfg.StrOpt('store_local_path',
               default='/var/lib/ironic/inspector-store-local',
               help=_('File path to store inspection data locally')),
]


def list_opts():
    return [
        ('store_local', STORE_LOCAL_OPTS)
    ]

CONF = cfg.CONF
CONF.register_opts(STORE_LOCAL_OPTS, group='store_local')

LOG = utils.getProcessingLogger(__name__)


class StoreLocalHook(base.ProcessingHook):
    """Processing hook for storing inspection data locally"""

    def before_update(self, introspection_data, node_info, **kwargs):
        uuid = node_info.uuid
        path = os.path.join(CONF.store_local.store_local_path, uuid)
        if not os.path.isdir(CONF.store_local.store_local_path):
            os.makedirs(CONF.store_local.store_local_path)
        with open(path, 'w') as f:
            f.write(json.dumps(introspection_data))
        node_info.patch([{'op': 'add', 'path': '/extra/inspector_data_path',
                          'value': path}])



