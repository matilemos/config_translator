#!/usr/bin/python3
# Migrador de nodo completo a partir de Json


import sys
import json
import codecs
import jinja2
from pprint import pprint
from os import listdir
from os import remove

f_nodoc= 'files/nodoc.json'
f_rac= 'files/rac.json'
f_sac= 'files/sac.json'
f_rbb= 'files/rbb.json'
f_sco= 'files/sco.txt'
f_vpns= 'files/vpns.txt'


sco = {}

vpns = {}

ifaces_list = {'all': [],'pending': [], 'sco': [],'irs': [], 'vrf': [],'vpls': [],'bridge': [], 'trunk':[]}
instances_list = {'vrf': [], 'vpls': [], 'bridge':[], 'noassigned':[]}

templateLoader = jinja2.FileSystemLoader( searchpath="/home/mlemos/github/config_translator/templates" )
templateEnv = jinja2.Environment( loader=templateLoader )


def main():
    
    # Lectura de archivo sco.txt

    with open(f_sco) as f:  
        for line in f.readlines():
            if line.startswith('#'):
                continue
            l = line.split("\t")
            if l[0] not in sco:
                sco[l[0]] = {'interface': l[1], 'ip': l[2], 'vlan':l[3], 'vendor':l[4]}
                ifaces_list['sco'].append(l[1])


    # Lecutra de nodo C

    nodoc = json.load(codecs.open(f_nodoc, 'r', 'utf-8-sig'))
    nodoc = nodoc['configuration'][0]

    # Lectura de configuracion VPNs

    with open(f_vpns) as f:  
        for line in f.readlines():
            if line.startswith('#'):
                continue
            l = line.split("\t")
            vpns[l[2].rstrip()] = {'id_cv': l[1], 'id_fc':l[0]}


    # Armado listado de interfaces e instancias a migrar:

    for interface in nodoc['interfaces'][0]['interface']: # Recorro las interfaz del Nodo C que corresponden a SCOs
        if(interface['name']['data']) in ifaces_list['sco']:  # Selecciono unicamente las que vamos a migrar
            if_name=interface['name']['data']
            for unit in interface['unit']:
                interface_name = if_name + "." + str(unit['name']['data'])
                ifaces_list['all'].append(interface_name)
                ifaces_list['pending'].append(interface_name)

                if ('encapsulation' in unit.keys() and 
                    unit['encapsulation'][0]['data'] == 'vlan-vpls'):  # Identifico VPLS
                   
                   ifaces_list['vpls'].append(interface_name)
                   ifaces_list['pending'].remove(interface_name)

                   for instance in nodoc['routing-instances'][0]['instance']:
                        if ('interface' in instance.keys()):
                            for iface in instance['interface']:
                                if (interface_name == iface['name']['data']):
                                    if (instance['name']['data'] not in instances_list['vpls']):
                                        instances_list['vpls'].append(instance['name']['data'])
                                        instances_list['noassigned'].append(instance['name']['data'])
                                        

                if ('encapsulation' in unit.keys() and 
                    unit['encapsulation'][0]['data'] == 'vlan-bridge'):  # Identifico bridges
                   
                    ifaces_list['bridge'].append(interface_name)
                    ifaces_list['pending'].remove(interface_name)

                    for domain in nodoc['bridge-domains'][0]['domain']:
                        if ('interface' in domain.keys()):
                            for iface in domain['interface']:
                                if (interface_name == iface['name']['data']):
                                    if (domain['name']['data'] not in instances_list['bridge']):
                                        instances_list['bridge'].append(domain['name']['data'])

                    
                if ('family' in unit.keys() and 
                    'inet' in unit['family'][0].keys() and 
                    'address' in unit['family'][0]['inet'][0].keys()):
                    
                    ifaces_list['irs'].append(interface_name)
                    ifaces_list['pending'].remove(interface_name)

                    for instance in nodoc['routing-instances'][0]['instance']:
                        if ('interface' in instance.keys()):
                            for iface in instance['interface']:
                                if (interface_name == iface['name']['data']):

                                    ifaces_list['irs'].remove(interface_name)
                                    ifaces_list['vrf'].append(interface_name)
                                    if (instance['name']['data'] not in instances_list['vrf']):
                                        instances_list['vrf'].append(instance['name']['data'])
                                        instances_list['noassigned'].append(instance['name']['data'])
                
                if ('family' in unit.keys() and 
                    'bridge' in unit['family'][0].keys() and 
                    'interface-mode' in unit['family'][0]['bridge'][0].keys() and
                    unit['family'][0]['bridge'][0]['interface-mode'][0]['data'] == 'trunk'):
                    
                    ifaces_list['trunk'].append(interface_name)
                    ifaces_list['pending'].remove(interface_name)
    

    # Identificacion de VPLS-id

    for vpls in instances_list['vpls']:
        for instance in nodoc['routing-instances'][0]['instance']:
            if (vpls == instance['name']['data']):
                id_cv = instance['protocols'][0]['vpls'][0]['vpls-id'][0]['data']
                for vpn in vpns:
                    if id_cv == vpns[vpn]['id_cv']:
                        vpns[vpn]['alias'] = vpls
                        if vpls in instances_list['noassigned']:
                            instances_list['noassigned'].remove(vpls)

    # Identificacion de VRF-id
    for vrf in instances_list['vrf']:
        for instance in nodoc['routing-instances'][0]['instance']:
            if (vrf == instance['name']['data']):
                if ('vrf-target' in instance and 'vrf-import' in instance):
                    id_cv = instance['vrf-target'][0]['community'][0]['data'].split(":")[1] + ":" + instance['vrf-target'][0]['community'][0]['data'].split(":")[2]
                    for vpn in vpns:
                        if id_cv == vpns[vpn]['id_cv']:
                            vpns[vpn]['alias'] = vrf
                            if vrf in instances_list['noassigned']:
                                instances_list['noassigned'].remove(vrf)

                if ('vrf-import' in instance):
                    vrf_imp = instance['vrf-import'][0]['data']
                    for policy in nodoc['policy-options'][0]['policy-statement']:
                        if instance['vrf-import'][0]['data'] == policy['name']['data']:
                            for term in policy['term']:
                                if ('from' in term and
                                    'community' in term['from'][0]):
                                    for community in term['from'][0]['community']:
                                        if community['data'] != 'GESTION' and community['data'] != 'Gestion-FC-Import':
                                            for item in nodoc['policy-options'][0]['community']:
                                                if community['data'] == item['name']['data']:
                                                    for member in item['members']:
                                                        id_cv = member['data'].split(":")[1] + ":" + member['data'].split(":")[2]
                                                        for vpn in vpns:
                                                            if id_cv == vpns[vpn]['id_cv']:
                                                                vpns[vpn]['alias'] = vrf
                                                                if vrf in instances_list['noassigned']:
                                                                    instances_list['noassigned'].remove(vrf)
                

    # Verififacion de asignacion de VPNS:
    if instances_list['noassigned']:
        print("\nLas siguientes instancias no tienen asignacion:\n")
        for instance in instances_list['noassigned']:
            pprint (instance)
        print("\n\nCompletar y volver a ejecutar.\n")
        return

    for file in listdir("output"): # Borro archivos en carpeta "output"
        remove("output/" + file)

    for interface in ifaces_list['irs']:
    #    pprint(interface)
        for iface in nodoc['interfaces'][0]:
            
            
            break
    template = templateEnv.get_template('irs_interface.j2')
    irs = {'sco': '123', 'vlan': '13412','ip_a': '1.1.1.1', 'ip_b': '2.2.2.2'}
    test=template.render(irs)

    with open('output/test.txt', 'a') as f:
        f.write(test)

if __name__ == '__main__':
        exit(main())
