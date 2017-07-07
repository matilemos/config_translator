#!/usr/bin/python3
# Migrador de nodo completo


import sys
import json
import codecs
from jinja2 import Template
from pprint import pprint

f_nodoc= 'files/nodoc.json'
f_rac= 'files/rac.json'
f_sac= 'files/sac.json'
f_rbb= 'files/rbb.json'
f_sco= 'files/sco.txt'


sco = {}
sco_interfaces = []
interfaces_list = []
pending_list = []

irs_list = []
vpls_list = []
bridge_list = []
vrf_list = []

def main():
    
    with open(f_sco) as f:  # Lectura de archivo sco.txt
        for line in f.readlines():
            if line.startswith('#'):
                continue
            l = line.split("\t")
            if l[0] not in sco:
                sco[l[0]] = {'interface': l[1], 'ip': l[2], 'vlan':l[3], 'vendor':l[4]}
                sco_interfaces.append(l[1])

    nodoc = json.load(codecs.open(f_nodoc, 'r', 'utf-8-sig'))
    nodoc = nodoc['configuration'][0]


    # Armo listado de interfaces a migrar:

    for interface in nodoc['interfaces'][0]['interface']: # Recorro las interfaz del Nodo C que corresponden a SCOs
        if(interface['name']['data']) in sco_interfaces:  # Selecciono unicamente las que vamos a migrar
            if_name=interface['name']['data']
            for unit in interface['unit']:
                interface_name = if_name + "." + str(unit['name']['data'])
                interfaces_list.append(interface_name)
                pending_list.append(interface_name)

                if ('encapsulation' in unit.keys() and unit['encapsulation'][0]['data'] == 'vlan-vpls'):  # Identifico VPLS
                   vpls_list.append(interface_name)

                if ('encapsulation' in unit.keys() and unit['encapsulation'][0]['data'] == 'vlan-bridge'):  # Identifico bridges
                   bridge_list.append(interface_name)

                if ('family' in unit.keys() and 'inet' in unit['family'][0].keys() and 'address' in unit['family'][0]['inet'][0].keys()):
                    # Decido si es IRS o VRF

                    irs_list.append(interface_name)

                    for instance in nodoc['routing-instances'][0]['instance']:
                        if ('interface' in instance.keys()):
                            for iface in instance['interface']:
                                if (interface_name == iface):
                                    irs_list.remove(interface_name)
                                    vrf_list.append(interface_name)


        pprint(irs_list)
        pprint(vrf_list)



        #        
        #        if roa_interfaces[interface][unit]['family'] == 'inet':
        #            irs_list.append(interface_name)
        #            pending_list.remove(interface_name)
        #            for instance in roa_instances:
        #                if interface_name in roa_instances[instance]['interfaces']:
        #                    irs_list.remove(interface_name)
        #                    vrf_list.append(interface_name)
        #                    if instance not in (review_instances):
        #                        review_instances.append(instance)
        #        

                #if unit['encapsulation'] == 'vlan-vpls':
                #    for instance in roa_instances:
                #        if interface_name in roa_instances[instance]['interfaces']:
                #            vpls_list.append(interface_name)
                #            pending_list.remove(interface_name)
                #            if instance not in (review_instances):
                #                review_instances.append(instance)
        #
        #        # Identifico BRDIGEs
        #        if roa_interfaces[interface][unit]['family'] == 'bridge':
        #            bridge_list.append(interface_name)
        #            pending_list.remove(interface_name)
        #        
        #        # Identifico PWs
        #        if roa_interfaces[interface][unit]['encapsulation'] == 'vlan-ccc':
        #            pw_list.append(interface_name)
        #            pending_list.remove(interface_name)



if __name__ == '__main__':
        exit(main())
