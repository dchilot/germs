import os
import networkx
from fabric.api import local
from fabric.api import abort
from fabric.api import settings
from fabric.context_managers import prefix


def local_raise_on_error(command):
    with settings(warn_only=True):
        result = local(command)
    if (result.failed):
        raise Exception("command failed: " + command)


def get_is_valid_url_ftp(url):
    import ftplib
    server, _, remote = url.partition('/')
    ftp = ftplib.FTP(server)
    ftp.login("anonymous")
    return (len(ftp.nlst(remote)) > 0)


def get_is_valid_url(url):
    """
    Return True if and only if the provided url is valid.
    """
    if (url.startswith('ftp://')):
        _, _, url = url.partition('ftp://')
        return get_is_valid_url_ftp(url)
    else:
        import requests
        req = requests.get(url)
        return (requests.codes.ok == req.status_code)


def init_path(path_name):
    """
    `path_name`: name of the environment variable to get.
    Return the expected environment variable in a list. If the variable is
    not found the list is empty.
    Despite its name this is not specific to paths but could work for any
    environment variable.
    """
    path_array = []
    try:
        var = os.environ[path_name]
        if (var):
            path_array.append(var)
    except:
        pass
    return path_array


def build_exports(pkg_config_path, ld_library_path, library_path, path, roots):
    exports = 'export'
    exports += ' PKG_CONFIG_PATH=' + ':'.join(pkg_config_path)
    exports += ' LD_LIBRARY_PATH=' + ':'.join(ld_library_path)
    exports += ' LIBRARY_PATH=' + ':'.join(library_path)
    exports += ' PATH=' + ':'.join(path)
    exports += ' ' + ' '.join(roots)
    print 'exports =', exports
    return exports


def install(name, destination=None, step=0,
            global_flags='',
            global_maker_flags='',
            global_installer_flags='',
            global_environment='',
            global_installer_environment='',
            force=False, test=False, retries=1,
            delete_archive=False, delete_extraction=False, repositories=None,
            **override):
    """
    Command to install some software.
    """
    if (destination is None):
        destination = os.path.join(os.environ["HOME"], "env")
    if (repositories is None):
        repositories = []
    else:
        tmp_repos = []
        for repo in repositories.split(";"):
            if (os.path.isdir(repo)):
                tmp_repos.append(repo)
            else:
                print 'Discarded repository', repo
        repositories = tmp_repos
    print "install", name, "in", destination

    from schema import Schema, Use
    step = Schema(Use(int)).validate(step)
    if (not os.path.isdir(destination)):
        abort("Destination folder (%s) does not exist." % destination)
    book = RecipeBook()
    cfg_parser = RecipeParser(book)
    print 'override =', override
    root_config = cfg_parser.parse(name, recursive=True, override=override)
    graph = cfg_parser.graph
    graph.add_node(root_config)
    nodes = networkx.topological_sort(graph)
    nodes.reverse()
    pkg_config_path = init_path('PKG_CONFIG_PATH')
    ld_library_path = init_path('LD_LIBRARY_PATH')
    print "ld_library_path", ld_library_path
    library_path = init_path('LIBRARY_PATH')
    path = init_path('PATH')
    roots = []
    has_deps = (len(nodes) > 1)
    for config in nodes:
        exports = build_exports(
            pkg_config_path, ld_library_path, library_path, path, roots)
        with prefix(exports):
            try:
                is_root = (config is root_config)
                local_step = step if (is_root) else 0
                if (is_root):
                    if (has_deps):
                        print "All dependencies installed"
                        print "Back to installing %s" % config.name
                else:
                    print "Install dependency: %s" % config.name
                #local('echo "local_step=%s"' % local_step)
                # We do not want to force dependencies to be reinstalled
                # if force=True is used so we only do it when is_root is True.
                config.install(
                    destination,
                    step=local_step,
                    global_flags=global_flags,
                    global_maker_flags=global_maker_flags,
                    global_installer_flags=global_installer_flags,
                    global_environment=global_environment,
                    global_installer_environment=global_installer_environment,
                    force=(force and is_root),
                    test=test, retries=retries,
                    delete_archive=delete_archive,
                    delete_extraction=delete_extraction,
                    repositories=repositories)
            except StopIteration:
                print "No need to install %s" % (config.name)
            full_destination = config.prefix
            roots.append('ROOT_' + config.varname + '=' + full_destination)
            if (test):
                continue
            for sub_dir in os.listdir(full_destination):
                if (sub_dir in ['lib', 'lib64']):
                    lib_dir = os.path.join(full_destination, sub_dir)
                    for pkg_sub_dir in os.listdir(lib_dir):
                        if ("pkgconfig" == pkg_sub_dir):
                            pkg_dir = os.path.join(lib_dir, pkg_sub_dir)
                            pkg_config_path.insert(0, pkg_dir)
                    ld_library_path.insert(0, lib_dir)
                    library_path.insert(0, lib_dir)
                elif (sub_dir in ['bin']):
                    path.insert(
                        0,
                        os.path.join(full_destination, sub_dir))


class RecipeBook(object):
    """
    Tells where to find recipies on the disk.
    """

    def __init__(self):
        self._root = os.path.dirname(os.path.abspath(__file__))

    def locate(self, recipe):
        """
        Abort if the file #recipe + ".cfg" is not found in the recipies
        directory.
        Return the full path to the recipe otherwise.
        """
        recipe = os.path.join(self._root, "recipies", recipe + ".cfg")
        if (not os.path.exists(recipe)):
            print "recipe =", recipe
            abort("No recipe found to install '%s'." % recipe)
        return recipe


def spaced(string):
    """
    Return the provided string prepended with a space if not empty.
    """
    return ' ' + string if (string) else ""


class Config(object):
    """
    Mapping of a recipe with extra logic to install it.
    This is tightly couples with RecipeParser (which is not good).
    """

    def __init__(self, name, recipe, values, parser=None):
        """
        `name`: name of the recipe.
        `recipe`: path to the file containing the recipe.
        `values`: values extracted from the file.
        `parser`: if provided, the dependencies will be parsed with it.
        """
        self._name = name
        self._recipe = recipe
        self._values = values
        self._dependencies = set()
        self._prefix = None
        self._global_flags = ''
        self._global_maker_flags = ''
        self._global_installer_flags = ''
        self._global_environment = ''
        self._global_installer_environment = ''
        if (parser is not None):
            deps = self._values['dependencies']
            if (deps):
                for dependency in deps.split(' '):
                    self._dependencies.add(parser.parse(dependency))
        try:
            self._values['address'], _, _ = \
                self._values['address'].partition('?')
        except KeyError:
            pass

    def _replace_in_values(self, mapping):
        '''
        Expand values from #_values using the python #format method.
        `mapping`: dictionary that contains the mapping for the #format
          method to perform its substitutions.
        '''
        import six
        for key, value in self._values.items():
            if (isinstance(value, six.string_types)):
                new_value = value.format(**mapping)
                if (new_value != value):
                    self._values[key] = new_value

    def __str__(self):
        return self._name

    @property
    def name(self):
        return self._name

    @property
    def prefix(self):
        return self._prefix

    @property
    def varname(self):
        return self._name.replace('.', '_').replace('-', '_').upper()

    @property
    def recipe(self):
        return self._recipe

    @property
    def address(self):
        return self._values['address']

    @property
    def method(self):
        return self._values['method']

    @property
    def maker(self):
        return self._values['maker']

    @property
    def flags(self):
        return self._values['flags'] + spaced(self._global_flags)

    @property
    def maker_flags(self):
        return self._values['maker_flags'] + spaced(self._global_maker_flags)

    @property
    def installer_flags(self):
        return self._values['installer_flags'] +\
            spaced(self._global_installer_flags)

    @property
    def environment(self):
        return self._values['environment'] + spaced(self._global_environment)

    @property
    def installer_environment(self):
        return self._values['installer_environment'] + \
            spaced(self._global_installer_environment)

    @property
    def force(self):
        return self._values['force']

    @property
    def build_out_of_sources(self):
        return self._values['build_out_of_sources']

    @property
    def dependencies(self):
        return self._dependencies

    @property
    def directory(self):
        return self._values['directory']

    def _install_0(self, step, force, test):
        """
        Step 0: Check if the recipe has been installed.
        """
        if (0 >= step):
            print 0
            if (os.path.isdir(self._prefix)):
                if (force):
                    if (not test):
                        import shutil
                        shutil.rmtree(self._prefix)
                else:
                    print "'%s' already exists." % (self._prefix)
                    raise StopIteration

    def _install_1(self, step, archive, downloader, working_dir, archive_dir,
                   extraction_directory):
        """
        `archive`: name of the archive to be downloaded (only valid for wget).
        `dowloader`: program used to download the software.
        Step 1: For wget compatible addresses, download and extract the tar
          file if needed.
          For hg or git, perform a clone.
        """
        if (1 >= step):
            print 1
            os.chdir(archive_dir)
            if ('wget' == downloader):
                tries = 0
                done = False
                while ((not done) and (tries < 3)):
                    tries += 1
                    local_raise_on_error("wget -nc --no-check-certificate %s" %
                                         self.address)
                    import tarfile
                    #try:
                    tar = tarfile.open(archive)
                    if (not os.path.isdir(extraction_directory)):
                        tar.extractall(working_dir)
                    done = True
                    #except Exception as e:
                        #print e
                        #os.remove(archive)
            elif ('hg' == downloader):
                clone_needed = True
                if (os.path.exists(extraction_directory)):
                    os.chdir(extraction_directory)
                    try:
                        local_raise_on_error('hg pull && hg update')
                        clone_needed = False
                    except:
                        os.remove(extraction_directory)
                if (clone_needed):
                    local_raise_on_error('hg clone %s %s' %
                                         (self.address, extraction_directory))
            elif ('git' == downloader):
                clone_needed = True
                if (os.path.exists(extraction_directory)):
                    os.chdir(extraction_directory)
                    try:
                        local_raise_on_error('git pull')
                        clone_needed = False
                    except:
                        os.remove(extraction_directory)
                if (clone_needed):
                    local_raise_on_error('git clone %s %s' %
                                         (self.address, extraction_directory))

    def _install_2(self, step, extraction_directory):
        """
        Move to build directory.
        Step 2: clean build directory if needed.
        """
        os.chdir(extraction_directory)
        if (self.build_out_of_sources):
            if (2 >= step):
                print 2
                try:
                    #import shutil
                    #shutil.rmtree('build')
                    local_raise_on_error('rm -rf build')
                except:
                    pass
                try:
                    #os.mkdir('build')
                    local_raise_on_error('mkdir build')
                except OSError:
                    pass
            os.chdir('build')

    def _install_3(self, step, extraction_directory, forced_method=None):
        """
        Step 3: generate makefile (or equivalent)
        """
        if (3 >= step):
            if (forced_method):
                print 3, "(forced)"
                used_method = forced_method
            else:
                print 3
                used_method = self.method
            if (used_method == 'cmake'):
                flags = self.flags
                if (self.build_out_of_sources):
                    flags += ' .. '
                flags += ' -DCMAKE_INSTALL_PREFIX:PATH=' + self._prefix
                method = used_method
            else:
                flags = self.flags
                if (used_method != 'autogen'):
                    flags += ' --prefix=' + self._prefix
                method = os.path.join(extraction_directory, used_method)
                if (not os.path.exists(method)):
                    if (os.path.exists(method + '.sh')):
                        method += '.sh'
            if (self.environment):
                local_raise_on_error(
                    self.environment + spaced(method) + spaced(flags))
            else:
                local_raise_on_error(method + spaced(flags))
            if (('autogen' == used_method) and (not forced_method)):
                self._install_3(step, extraction_directory, 'configure')

    def _install_4(self, step):
        """
        Step 4: compile
        """
        if (4 >= step):
            print 4
            if ('build' == self.maker):
                maker = 'sh' + spaced(self.maker) + ".sh"
                maker += ' --prefix=' + self._prefix
            else:
                maker = self.maker
            local_raise_on_error(maker + spaced(self.maker_flags))

    def _install_3_4_5(self, step, extraction_directory):
        """
        You must be in the build directory when calling this method.
        Step 3: generate makefile (or equivalent)
        Step 4: compile
        Step 5: install (may compile too)
        """
        if (5 >= step):
            if (self.method in
                    ['autogen',
                     'configure',
                     'bootstrap',
                     'make',
                     'build',
                     'cmake']):
                local_raise_on_error('pwd')
                if (self.method not in ['make', 'build']):
                    self._install_3(step, extraction_directory)
                if (self.maker in ['make', 'build']):
                    self._install_4(step)
                    print 5
                    print 'self.method =', self.method
                    if ('build' == self.method):
                        installer = 'sh ' + self.method + ".sh"
                        if (not os.path.exists(self._prefix)):
                            os.mkdir(self._prefix)
                    elif ('configure' == self.method):
                        installer = self.maker
                    elif (self.method in ['cmake', 'autogen']):
                        installer = 'make'
                    else:
                        installer = self.method
                    installer += ' install'
                    if (self.installer_environment):
                        local_raise_on_error(
                            self.installer_environment +
                            spaced(installer) + spaced(self.installer_flags))
                    else:
                        local_raise_on_error(
                            installer + spaced(self.installer_flags))
                elif ('b2' == self.maker):
                    print 5
                    local_raise_on_error(
                        './b2 install' +
                        spaced(self.installer_flags))
            else:
                raise ValueError(
                    "Do not know how to install with method '%s'." %
                    self.method)

    def _install_6(self, step):
        """
        Step 6: add dependencies.
        """
        if (self.dependencies):
            deps_dir = os.path.join(self._prefix, "deps")
            #try:
                #os.mkdir(deps_dir)
            #except OSError:
                #pass
            local_raise_on_error('mkdir -p ' + deps_dir)
            for dep in self.dependencies:
                local_raise_on_error("touch " +
                                     os.path.join(deps_dir, dep.name))

    def install(self, destination, step=0, working_dir=None, archive_dir=None,
                global_flags='',
                global_maker_flags='',
                global_installer_flags='',
                global_environment='',
                global_installer_environment='',
                force=False, test=False, retries=1,
                delete_archive=False, delete_extraction=False,
                repositories=None):
        """
        `destination`: root folder which will contain a directory named
            after the configuration (name is used) where the software will
            be installed.
        `working_dir`: directory where the sources are extracted.
        `archive_dir`: directory where the archive is downloaded.
        """
        self._destination = destination
        self._global_flags = global_flags
        self._global_maker_flags = global_maker_flags
        self._global_installer_flags = global_installer_flags
        self._global_environment = global_environment
        self._global_installer_environment = global_installer_environment
        self._repositories = repositories
        print 'Start installation at step %i' % step
        archive = self.address.split('/')[-1]
        is_tar = False
        for ext in ('.tar', '.tgz'):
            directory, tar, _ = archive.partition(ext)
            if (tar):
                is_tar = True
                break
        if (directory.endswith('-src')):
            directory = directory[:-4]
        if (not is_tar):
            address = self.address.rstrip('/')
            if (address.endswith('hg')):
                downloader = 'hg'
            elif (address.endswith('git')):
                downloader = 'git'
            else:
                raise Exception("Do not know how to dowload from '%s'" %
                                self.address)
            directory = self._name
        else:
            downloader = 'wget'
        if (self.directory):
            # override from configuration
            directory = self.directory
        prefixes = [os.path.join(repo, self._name)
                    for repo in repositories]
        for prefix in prefixes:
            if (os.path.exists(prefix)):
                print 'Prefix:', prefix
                self._prefix = prefix
                break
        if (self._prefix is None):
            self._prefix = os.path.join(destination, self._name)
        self._install_0(step, force, test)
        if (test):
            return
        if (working_dir is None):
            import tempfile
            working_dir = tempfile.gettempdir()
        if (archive_dir is None):
            import tempfile
            archive_dir = tempfile.gettempdir()
        extraction_directory = os.path.join(working_dir, directory)
        self._replace_in_values({ 'prefix': self._prefix })
        tries = 0
        done = 0
        while ((not done) and (tries < retries)):
            try:
                self._install_1(step, archive, downloader, working_dir,
                                archive_dir, extraction_directory)
                self._install_2(step, extraction_directory)
                self._install_3_4_5(step, extraction_directory)
                self._install_6(step)
                done = True
            except Exception as e:
                tries += 1
                print e
                full_archive_path = os.path.join(archive_dir, archive)
                if (os.path.exists(full_archive_path)):
                    if (delete_archive):
                        os.remove(full_archive_path)
                if (os.path.exists(extraction_directory)):
                    if (delete_extraction):
                        import shutil
                        shutil.rmtree(extraction_directory)
        if (not done):
            raise Exception("Abort on failure")


class RecipeParser(object):
    """
    Parses the recipies and stores the objects wrapping them (this is used
    when building a dependency graph).
    """

    from schema import Schema, And, Use
    _schema = Schema({
        'address': And(str, len, get_is_valid_url),
        'method': And(str, lambda s: s in ['autogen',
                                           'configure',
                                           'bootstrap',
                                           'make',
                                           'build',
                                           'cmake']),
        'maker': And(str, lambda s: s in ['make', 'b2', 'build']),
        'build_out_of_sources': Use(lambda x: str(x).lower() in
                                    ['1', 'true', 'on', 'yes']),
        'flags': str,
        'maker_flags': str,
        'installer_flags': str,
        'dependencies': str,
        'environment': str,
        'installer_environment': str,
        'directory': str,
    })

    def __init__(self, recipe_book):
        """
        `recipe_book`: object used to find a recipe on the disk based
        on its name.
        """
        self._cache = {}
        self._book = recipe_book

    def parse(self, name, recursive=False, override=None):
        """
        Parses and validates a recipe.
        `name`: the name of the recipe (not the file).
        `recursive`: if set to True, also parse the dependencies.
        `override`: dictionary that can contain an override value for each
        config key. '+...' means something is added, '-...' means something
        is removed, otherwise the value is just replaced. If there is more
        than one value, the values have to be separated by commas (',').
        >>> parser = RecipeParser()
        >>> config = parser.parse("gcc-4.8-light")
        >>> print config
        gcc-4.8-light
        """
        recipe = self._book.locate(name)
        if (name in self._cache):
            return self._cache[name]
        import ConfigParser
        cfg = ConfigParser.RawConfigParser()
        cfg.read(recipe)
        config = {
            'address': None,
            'method': 'configure',
            'maker': 'make',
            'build_out_of_sources': True,
            'flags': '',
            'maker_flags': '',
            'installer_flags': '',
            'dependencies': '',
            'environment': '',
            'installer_environment': '',
            'directory': '',
        }
        for key in config:
            try:
                value = cfg.get('install', key)
            except ConfigParser.NoOptionError:
                # keep the default value
                value = config[key]
            except ConfigParser.NoSectionError as exception:
                abort("Recipe '%s' is corrupted.\n%s" % (recipe, exception))
            if ((override) and (key in override)):
                for override_value in override[key].split(','):
                    if (override_value.startswith('-')):
                        value = value.replace(override_value, '')
                    elif (override_value.startswith('+')):
                        value += override_value
                    else:
                        value = override_value
            config[key] = value
        print 'Recipe parsed.'
        print 'config (before)'
        print config
        config = RecipeParser._schema.validate(config)
        #print 'config (after)'
        #print config
        #abort('test')
        print 'Recipe validated.'
        if (recursive):
            config = Config(name, recipe, config, self)
        else:
            config = Config(name, recipe, config, self)
        self._cache[name] = config
        return config

    @property
    def graph(self):
        """
        Return a graph representation of the dependencies.
        """
        graph = networkx.DiGraph()
        for recipe in self._cache.values():
            map(lambda x: graph.add_edge(recipe, x), recipe.dependencies)
        return graph
