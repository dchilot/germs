import os
import networkx
from fabric.api import local
from fabric.api import abort
from fabric.context_managers import prefix


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


def install(name, destination=None):
    """
    Command to install some software.
    """
    if (destination is None):
        destination = os.path.join(os.environ["HOME"], "env")
    print "install", name, "in", destination

    if (not os.path.isdir(destination)):
        abort("Destination folder (%s) does not exist." % destination)
    book = RecipeBook()
    cfg_parser = RecipeParser(book)
    root_config = cfg_parser.parse(name, recursive=True)
    graph = cfg_parser.graph
    graph.add_node(root_config)
    nodes = networkx.topological_sort(graph)
    nodes.reverse()
    ld_library_path = []
    try:
        var = os.environ['LD_LIBRARY_PATH']
        if (var):
            ld_library_path.append(var)
    except:
        pass
    path = []
    try:
        var = os.environ['PATH']
        if (var):
            path.append(var)
    except:
        pass
    roots = []
    for config in nodes:
        exports = 'export'
        exports += ' LD_LIBRARY_PATH=' + ':'.join(ld_library_path)
        exports += ' PATH=' + ':'.join(path)
        exports += ' ' + ' '.join(roots)
        print 'exports =', exports
        with prefix(exports):
            local('echo ROOT_LIBGMP=$ROOT_LIBGMP')
            full_destination = config.install(destination)
            roots.append('ROOT_' + config.name.upper() + '=' + full_destination)
            for sub_dir in os.listdir(full_destination):
                if (sub_dir in ['lib', 'lib64']):
                    ld_library_path.insert(
                        0,
                        os.path.join(full_destination, sub_dir))
                elif (sub_dir in ['bin']):
                    path.insert(
                        0,
                        os.path.join(full_destination, sub_dir))
    #print graph.nodes()
    #print graph.edges()
    #networkx.drawing.nx_pydot.write_dot(graph, 'graph.dot')
    #import pydot
    #pydot.write_dot(graph, 'graph.dot')


class RecipeBook(object):
    def __init__(self):
        self._root = os.path.dirname(os.path.abspath(__file__))

    def open(self, recipe):
        recipe = os.path.join(self._root, "recipies", recipe + ".cfg")
        if (not os.path.exists(recipe)):
            print "recipe =", recipe
            abort("No recipe found to install '%s'." % recipe)
        return recipe


class Config(object):
    def __init__(self, name, recipe, values, parser=None):
        self._name = name
        self._recipe = recipe
        self._values = values
        self._dependencies = set()
        if (parser is not None):
            deps = self._values['dependencies']
            if (deps):
                for dependency in deps.split(' '):
                    self._dependencies.add(parser.parse(dependency))

    def __str__(self):
        return self._name

    @property
    def name(self):
        return self._name

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
    def flags(self):
        return self._values['flags']

    @property
    def dependencies(self):
        return self._dependencies

    def install(self, destination, working_dir=None, archive_dir=None):
        archive = self.address.split('/')[-1]
        directory, _, _ = archive.partition('.tar')
        dir_prefix = os.path.join(destination, self._name)
        if (os.path.isdir(dir_prefix)):
            local('echo Assume %s is installed.' % self._name)
            return dir_prefix
        if (working_dir is None):
            import tempfile
            working_dir = tempfile.gettempdir()
        if (archive_dir is None):
            import tempfile
            archive_dir = tempfile.gettempdir()
        os.chdir(archive_dir)
        local("wget -nc %s" % self.address)
        import tarfile
        tar = tarfile.open(archive)
        build_directory = os.path.join(working_dir, directory)
        if (not os.path.isdir(build_directory)):
            tar.extractall(working_dir)
        os.chdir(build_directory)
        try:
            import shutil
            shutil.rmtree('build')
        except:
            pass
        os.mkdir('build')
        os.chdir('build')
        if ('configure' == self.method):
            flags = self.flags + ' --prefix=' + dir_prefix
            local('pwd')
            local('../configure ' + flags)
            local('make')
            local('make install')
        else:
            print "Do not know how to install with method '%s'." % self.method
        return dir_prefix


class RecipeParser(object):
    def __init__(self, recipe_book):
        self._cache = {}
        self._book = recipe_book

    def parse(self, name, recursive=False):
        """
        >>> parser = RecipeParser()
        >>> config = parser.parse("recipies/gcc-4.8-light.cfg")
        """
        recipe = self._book.open(name)
        if (name in self._cache):
            return self._cache[name]
        import ConfigParser
        cfg = ConfigParser.RawConfigParser()
        cfg.read(recipe)
        from schema import Schema, And, Use, Optional
        schema = Schema({
            'address': And(str, len, Use(get_is_valid_url)),
            'method': Use(lambda s: s in ['configure']),
            'flags': str,
            'dependencies': str
            })
        config = {
                'address': None,
                'method': 'configure',
                'flags': '',
                'dependencies': ''
                }
        for key in config:
            try:
                config[key] = cfg.get('install', key)
            except ConfigParser.NoOptionError:
                # keep the default value
                pass
            except ConfigParser.NoSectionError as exception:
                abort("Recipe '%s' is corrupted.\n%s" % (recipe, exception))
        schema.validate(config)
        if (recursive):
            config = Config(name, recipe, config, self)
        else:
            config = Config(name, recipe, config, self)
        self._cache[name] = config
        return config

    @property
    def graph(self):
        graph = networkx.DiGraph()
        for recipe in self._cache.values():
            map(lambda x: graph.add_edge(recipe, x), recipe.dependencies)
        return graph
