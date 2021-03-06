#!/usr/bin/env python
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import argparse
import jinja2
import os
import shutil
import six
import sys
import yaml

__tht_root_dir = os.path.dirname(os.path.dirname(__file__))


def parse_opts(argv):
    parser = argparse.ArgumentParser(
        description='Configure host network interfaces using a JSON'
        ' config file format.')
    parser.add_argument('-p', '--base_path', metavar='BASE_PATH',
                        help="""base path of templates to process.""",
                        default='.')
    parser.add_argument('-r', '--roles-data', metavar='ROLES_DATA',
                        help="""relative path to the roles_data.yaml file.""",
                        default='roles_data.yaml')
    parser.add_argument('-n', '--network-data', metavar='NETWORK_DATA',
                        help="""relative path to the network_data.yaml file.""",
                        default='network_data.yaml')
    parser.add_argument('--safe',
                        action='store_true',
                        help="""Enable safe mode (do not overwrite files).""",
                        default=False)
    parser.add_argument('-o', '--output-dir', metavar='OUTPUT_DIR',
                        help="""Output dir for all the templates""",
                        default='')
    opts = parser.parse_args(argv[1:])

    return opts


def _j2_render_to_file(j2_template, j2_data, outfile_name=None,
                       overwrite=True):
    yaml_f = outfile_name or j2_template.replace('.j2.yaml', '.yaml')
    print('rendering j2 template to file: %s' % outfile_name)

    if not overwrite and os.path.exists(outfile_name):
        print('ERROR: path already exists for file: %s' % outfile_name)
        sys.exit(1)

    # Search for templates relative to the current template path first
    template_base = os.path.dirname(yaml_f)
    j2_loader = jinja2.loaders.FileSystemLoader([template_base, __tht_root_dir])

    try:
        # Render the j2 template
        template = jinja2.Environment(loader=j2_loader).from_string(
            j2_template)
        r_template = template.render(**j2_data)
    except jinja2.exceptions.TemplateError as ex:
        error_msg = ("Error rendering template %s : %s"
                     % (yaml_f, six.text_type(ex)))
        print(error_msg)
        raise Exception(error_msg)
    with open(outfile_name, 'w') as out_f:
        out_f.write(r_template)


def process_templates(template_path, role_data_path, output_dir,
                      network_data_path, overwrite):

    with open(role_data_path) as role_data_file:
        role_data = yaml.safe_load(role_data_file)

    with open(network_data_path) as network_data_file:
        network_data = yaml.safe_load(network_data_file)

    j2_excludes_path = os.path.join(template_path, 'j2_excludes.yaml')
    with open(j2_excludes_path) as role_data_file:
        j2_excludes = yaml.safe_load(role_data_file)

    if output_dir and not os.path.isdir(output_dir):
        if os.path.exists(output_dir):
            raise RuntimeError('Output dir %s is not a directory' % output_dir)
        os.mkdir(output_dir)

    role_names = [r.get('name') for r in role_data]
    r_map = {}
    for r in role_data:
        r_map[r.get('name')] = r
    excl_templates = ['%s/%s' % (template_path, e)
                      for e in j2_excludes.get('name')]

    if os.path.isdir(template_path):
        for subdir, dirs, files in os.walk(template_path):

            # NOTE(flaper87): Ignore hidden dirs as we don't
            # generate templates for those.
            # Note the slice assigment for `dirs` is necessary
            # because we need to modify the *elements* in the
            # dirs list rather than the reference to the list.
            # This way we'll make sure os.walk will iterate over
            # the shrunk list. os.walk doesn't have an API for
            # filtering dirs at this point.
            dirs[:] = [d for d in dirs if not d[0] == '.']
            files = [f for f in files if not f[0] == '.']

            # NOTE(flaper87): We could have used shutil.copytree
            # but it requires the dst dir to not be present. This
            # approach is safer as it doesn't require us to delete
            # the output_dir in advance and it allows for running
            # the command multiple times with the same output_dir.
            out_dir = subdir
            if output_dir:
                out_dir = os.path.join(output_dir, subdir)
                if not os.path.exists(out_dir):
                    os.mkdir(out_dir)

            for f in files:
                file_path = os.path.join(subdir, f)
                # We do two templating passes here:
                # 1. *.role.j2.yaml - we template just the role name
                #    and create multiple files (one per role)
                # 2. *.j2.yaml - we template with all roles_data,
                #    and create one file common to all roles
                if f.endswith('.role.j2.yaml'):
                    print("jinja2 rendering role template %s" % f)
                    with open(file_path) as j2_template:
                        template_data = j2_template.read()
                        print("jinja2 rendering roles %s" % ","
                              .join(role_names))
                        for role in role_names:
                            j2_data = {'role': r_map[role]}
                            out_f = "-".join(
                                [role.lower(),
                                 os.path.basename(f).replace('.role.j2.yaml',
                                                             '.yaml')])
                            out_f_path = os.path.join(out_dir, out_f)
                            if not (out_f_path in excl_templates):
                                if '{{role.name}}' in template_data:
                                    j2_data = {'role': r_map[role],
                                               'networks': network_data}
                                    _j2_render_to_file(template_data, j2_data,
                                                       out_f_path, overwrite)
                                else:
                                    # Backwards compatibility with templates
                                    # that specify {{role}} vs {{role.name}}
                                    j2_data = {'role': role,
                                               'networks': network_data}
                                    # (dprince) For the undercloud installer we
                                    # don'twant to have heat check nova/glance
                                    # API's
                                    if r_map[role].get('disable_constraints',
                                                       False):
                                        j2_data['disable_constraints'] = True
                                    _j2_render_to_file(
                                        template_data,j2_data,
                                        out_f_path, overwrite)

                            else:
                                print('skipping rendering of %s' % out_f_path)
                elif f.endswith('.j2.yaml'):
                    print("jinja2 rendering normal template %s" % f)
                    with open(file_path) as j2_template:
                        template_data = j2_template.read()
                        j2_data = {'roles': role_data,
                                   'networks': network_data}
                        out_f = os.path.basename(f).replace('.j2.yaml', '.yaml')
                        out_f_path = os.path.join(out_dir, out_f)
                        _j2_render_to_file(template_data, j2_data, out_f_path,
                                           overwrite)
                elif output_dir:
                    shutil.copy(os.path.join(subdir, f), out_dir)

    else:
        print('Unexpected argument %s' % template_path)

opts = parse_opts(sys.argv)

role_data_path = os.path.join(opts.base_path, opts.roles_data)
network_data_path = os.path.join(opts.base_path, opts.network_data)

process_templates(opts.base_path, role_data_path, opts.output_dir,
                  network_data_path, (not opts.safe))
