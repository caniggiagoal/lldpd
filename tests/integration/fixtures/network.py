import pytest
import pyroute2
import struct
from .namespaces import Namespace


def int_to_mac(c):
    """Turn an int into a MAC address."""
    return ":".join(('{:02x}',)*6).format(
        *struct.unpack('BBBBBB', c.to_bytes(6, byteorder='big')))


class LinksFactory(object):
    """A factory for veth pair of interfaces and other L2 stuff.

    Each veth interfaces will get named ethX with X strictly
    increasing at each call.

    """

    def __init__(self):
        # We create all those links in a dedicated namespace to avoid
        # conflict with other namespaces.
        self.ns = Namespace('net')
        self.count = 0

    def __call__(self, *args):
        return self.veth(*args)

    def veth(self, ns1, ns2):
        """Create a veth pair between two namespaces."""
        with self.ns:
            # First, create a link
            first = 'eth{}'.format(self.count)
            second = 'eth{}'.format(self.count + 1)
            ipr = pyroute2.IPRoute()
            ipr.link_create(ifname=first,
                            peer=second,
                            kind='veth')
            idx = [ipr.link_lookup(ifname=x)[0]
                   for x in (first, second)]

            # Set an easy to remember MAC address
            ipr.link('set', index=idx[0],
                     address=int_to_mac(self.count + 1))
            ipr.link('set', index=idx[1],
                     address=int_to_mac(self.count + 2))

            # Then, move each to the target namespace
            ipr.link('set', index=idx[0], net_ns_fd=ns1.fd('net'))
            ipr.link('set', index=idx[1], net_ns_fd=ns2.fd('net'))

            # And put them up
            with ns1:
                ipr = pyroute2.IPRoute()
                ipr.link('set', index=idx[0], state='up')
            with ns2:
                ipr = pyroute2.IPRoute()
                ipr.link('set', index=idx[1], state='up')

            self.count += 2

    def bridge(self, name, *ifaces):
        """Create a bridge."""
        ipr = pyroute2.IPRoute()
        # Create the bridge
        ipr.link_create(ifname=name,
                        kind='bridge')
        idx = ipr.link_lookup(ifname=name)[0]
        # Attach interfaces
        for iface in ifaces:
            port = ipr.link_lookup(ifname=iface)[0]
            ipr.link('set', index=port, master=idx)
        # Put the bridge up
        ipr.link('set', index=idx, state='up')
        return idx

    def bond(self, name, *ifaces):
        """Create a bond."""
        ipr = pyroute2.IPRoute()
        # Create the bond
        ipr.link_create(ifname=name,
                        kind='bond')
        idx = ipr.link_lookup(ifname=name)[0]
        # Attach interfaces
        for iface in ifaces:
            slave = ipr.link_lookup(ifname=iface)[0]
            ipr.link('set', index=slave, state='down')
            ipr.link('set', index=slave, master=idx)
        # Put the bond up
        ipr.link('set', index=idx, state='up')
        return idx

    def vlan(self, name, id, iface):
        """Create a VLAN."""
        ipr = pyroute2.IPRoute()
        idx = ipr.link_lookup(ifname=iface)[0]
        ipr.link_create(ifname=name,
                        kind='vlan',
                        vlan_id=id,
                        link=idx)
        idx = ipr.link_lookup(ifname=name)[0]
        ipr.link('set', index=idx, state='up')
        return idx

    def up(self, name):
        ipr = pyroute2.IPRoute()
        idx = ipr.link_lookup(ifname=name)[0]
        ipr.link('set', index=idx, state='up')

    def down(self, name):
        ipr = pyroute2.IPRoute()
        idx = ipr.link_lookup(ifname=name)[0]
        ipr.link('set', index=idx, state='down')

    def remove(self, name):
        ipr = pyroute2.IPRoute()
        idx = ipr.link_lookup(ifname=name)[0]
        ipr.link_remove(idx)


@pytest.fixture
def links():
    return LinksFactory()
