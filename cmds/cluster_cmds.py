import os, sys, shutil

L = os.path.realpath(__file__).split(os.path.sep)[:-2]
root = os.path.sep.join(L)
sys.path.append(os.path.join(root, 'ccm_lib'))
from command import Cmd
from node import Node
import common

def cluster_cmds():
    return [
        "create",
        "add",
        "list",
        "switch",
        "status",
        "remove",
        "clear",
        "liveset",
        "start",
        "stop",
        "flush",
        "compact",
        "stress"
    ]

class ClusterCreateCmd(Cmd):
    def description(self):
        return "Create a new cluster"

    def get_parser(self):
        usage = "usage: ccm create [options] cluster_name"
        parser = self._get_default_parser(usage, self.description())
        parser.add_option('--no-switch', action="store_true", dest="no_switch",
            help="Don't switch to the newly created cluster", default=False)
        parser.add_option('-p', '--partitioner', type="string", dest="partitioner",
            help="Set the cluster partitioner class")
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, cluster_name=True)

    def run(self):
        try:
            cluster = common.create_cluster(self.path, self.name)
        except OSError:
            print 'Cannot create cluster, directory %s already exists.' % os.path.join(self.path, self.name)
            exit(1)

        if self.options.partitioner:
            cluster.partitioner = self.options.partitioner

        cluster.save()

        if not self.options.no_switch:
            common.switch_cluster(self.path, self.name)
            print 'Current cluster is now: %s' % self.name

class ClusterAddCmd(Cmd):
    def description(self):
        return "Add a new node to the current cluster"

    def get_parser(self):
        usage = "usage: ccm add [options] node_name"
        parser = self._get_default_parser(usage, self.description(), cassandra_dir=True)
        parser.add_option('-b', '--auto-boostrap', action="store_true", dest="boostrap",
            help="Set auto bootstrap for the node", default=False)
        parser.add_option('-s', '--seeds', action="store_true", dest="is_seed",
            help="Configure this node as a seed", default=False)
        parser.add_option('-i', '--itf', type="string", dest="itfs",
            help="Set host and port for both thrift and storage (format: host[:port])")
        parser.add_option('-t', '--thrift-itf', type="string", dest="thrift_itf",
            help="Set the thrift host and port for the node (format: host[:port])")
        parser.add_option('-l', '--storage-itf', type="string", dest="storage_itf",
            help="Set the storage (cassandra internal) host and port for the node (format: host[:port])")
        parser.add_option('-j', '--jmx-port', type="string", dest="jmx_port",
            help="JMX port for the node", default="7199")
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, node_name=True)
        self.cluster = common.load_current_cluster(self.path)

        if self.name in self.cluster.nodes:
            print 'Cannot create existing node %s' % self.name
            exit(1)

        if options.itfs is None and (options.thrift_itf is None or options.storage_itf is None):
            print 'Missing thrift and/or storage interfaces or jmx port'
            parser.print_help()
            exit(1)

        if options.thrift_itf is None:
            options.thrift_itf = options.itfs
        if options.storage_itf is None:
            options.storage_itf = options.itfs

        self.thrift = common.parse_interface(options.thrift_itf, 9160)
        self.storage = common.parse_interface(options.storage_itf, 7000)
        self.jmx_port = options.jmx_port

    def run(self):
        node = Node(self.name, self.cluster, self.options.boostrap, self.thrift, self.storage, self.jmx_port)
        self.cluster.add(node, self.options.is_seed)
        node.save()
        self.cluster.save()

        node.update_configuration(self.options.cassandra_dir)

class ClusterListCmd(Cmd):
    def description(self):
        return "List existing clusters"

    def get_parser(self):
        usage = "usage: ccm list [options]"
        return self._get_default_parser(usage, self.description())

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args)

    def run(self):
        try:
            current = common.current_cluster_name(self.path)
        except Exception as e:
            current = ''

        for dir in os.listdir(self.path):
            if os.path.exists(os.path.join(self.path, dir, 'cluster.conf')):
                print " %s%s" % ('*' if current == dir else ' ', dir)

class ClusterSwitchCmd(Cmd):
    def description(self):
        return "Switch of current (active) cluster"

    def get_parser(self):
        usage = "usage: ccm switch [options] cluster_name"
        return self._get_default_parser(usage, self.description())

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, cluster_name=True)
        if not os.path.exists(os.path.join(self.path, self.name, 'cluster.conf')):
            print "%s does not appear to be a valid cluster (use ccm cluster list to view valid cluster)" % self.name
            exit(1)

    def run(self):
        common.switch_cluster(self.path, self.name)

class ClusterStatusCmd(Cmd):
    def description(self):
        return "Display status on the current cluster"

    def get_parser(self):
        usage = "usage: ccm status [options]"
        parser =  self._get_default_parser(usage, self.description())
        parser.add_option('-v', '--verbose', action="store_true", dest="verbose",
                help="Print full information on all nodes", default=False)
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, load_cluster=True)

    def run(self):
        self.cluster.show(self.options.verbose)

class ClusterRemoveCmd(Cmd):
    def description(self):
        return "Remove the current cluster (delete all data)"

    def get_parser(self):
        usage = "usage: ccm remove [options]"
        parser =  self._get_default_parser(usage, self.description())
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, load_cluster=True)

    def run(self):
        self.cluster.stop()
        shutil.rmtree(self.cluster.get_path())
        os.remove(os.path.join(self.path, 'CURRENT'))

class ClusterClearCmd(Cmd):
    def description(self):
        return "Clear the current cluster data (and stop all nodes)"

    def get_parser(self):
        usage = "usage: ccm clear [options]"
        parser =  self._get_default_parser(usage, self.description())
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, load_cluster=True)

    def run(self):
        self.cluster.stop()
        for node in self.cluster.nodes.values():
            node.clear()

class ClusterLivesetCmd(Cmd):
    def description(self):
        return "Pring a comma-separated list of addresses of running nodes (handful in scripts)"

    def get_parser(self):
        usage = "usage: ccm liveset [options]"
        parser =  self._get_default_parser(usage, self.description())
        return parser

    def validate(self, parser, options, args):
        Cmd.validate(self, parser, options, args, load_cluster=True)

    def run(self):
        l = [ node.network_interfaces['storage'][0] for node in self.cluster.nodes.values() if node.is_live() ]
        print ",".join(l)
