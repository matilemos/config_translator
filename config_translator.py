#!/usr/bin/python3
# Migrador de nodo completo a partir de Json

import sys
import json
import codecs
import jinja2
from pprint import pprint
from os import listdir
from os import remove

from netaddr import IPAddress
from netaddr import IPNetwork

templateEnv = jinja2.Environment( loader=jinja2.FileSystemLoader( searchpath="templates" ) )

tipo = 'plazachica/'

f_nodoc= 'files/nodoc.json'
f_rac= 'files/rac.json'
f_sac= 'files/sac.json'
f_rbb= 'files/rbb.json'
f_sco= 'files/sco.txt'
f_vpns= 'files/vpns.txt'

sco = []
vpns = {}

ifaces_list = {'all': [],'pending': [], 'sco': [],'irs': [], 'vrf': [],'vpls': [],'bridge': [], 'trunk':[]}
instances_list = {'vrf': [], 'vpls': [], 'bridge':[], 'noassigned':[], 'created':[]}

rac_config = {'interfaces':[], 'routing-instances':[], 'routes':[]}

loopback = '1.1.1.1'


def create_sco(switch):
    data=switch
    data['sco']=data['vlan']
    config = templateEnv.get_template(tipo+'rac/sco.j2').render(data)
    with open('output/rac.txt', 'a') as f:
        f.write(config)
    return

def create_irs_iface(interface):
    data=interface
    config = templateEnv.get_template(tipo+'rac/irs_interface.j2').render(data)
    with open('output/rac.txt', 'a') as f:
        f.write(config)
    delete_nodoc_service(data)
    return

def create_vpls_base(instance):
    for ri in rac_config['routing-instances']:
        if instance == ri['ri_name_cv']:
            data = {}
            data['vpn'] = ri['ri_name_fc']
            data['vpn_id'] = ri['id_fc'].split(":")[1]
            data['loopback'] = loopback
            config = templateEnv.get_template(tipo+'/rac/l2vpn_base.j2').render(data)
            with open('output/rac.txt', 'a') as f:
                f.write(config)
            return

def create_vpls_iface(interface):
    if interface['ri_name_fc'] not in instances_list['created']:
        create_vpls_base(interface['ri_name_cv'])
    data = interface
    data['vpn'] = data['ri_name_fc']
    config = templateEnv.get_template(tipo+'/rac/l2vpn_interface.j2').render(data)
    with open('output/rac.txt', 'a') as f:
        f.write(config)
    delete_nodoc_service(data)
    return

def create_vrf_base(instance):
    for ri in rac_config['routing-instances']:
        if instance == ri['ri_name_cv']:
            data = {}
            data['vpn'] = ri['ri_name_fc']
            data['vpn_id'] = ri['id_fc'].split(":")[1]
            data['loopback'] = loopback
            config = templateEnv.get_template(tipo+'/rac/l3vpn_base.j2').render(data)
            with open('output/rac.txt', 'a') as f:
                f.write(config)
            return

def create_vrf_iface(interface):
    if interface['ri_name_fc'] not in instances_list['created']:
        create_vrf_base(interface['ri_name_cv'])
    
    data = interface
    data['vpn'] = data['ri_name_fc']
    for ri in rac_config['routing-instances']:
        if interface['ri_name_cv'] == ri['ri_name_cv']:
            for bgp_group in ri['bgp_groups']:
                wan=IPNetwork(interface['ip'])
                if bgp_group['neighbor'] in IPNetwork(wan.cidr):
                    if 'bgp_gorups' not in data.keys():
                        data['bgp_groups'] = []
                    data['bgp_groups'].append(bgp_group)
    config = templateEnv.get_template(tipo+'/rac/l3vpn_interface.j2').render(data)
    
    with open('output/rac.txt', 'a') as f:
        f.write(config)
    delete_nodoc_service(data)
    return

def delete_nodoc_service(data):
    config = templateEnv.get_template('nodoc/delete_service.j2').render(data)
    with open('output/nodoc.txt', 'a') as f:
        f.write(config)
    return

def main():

    with open(f_sco) as f:  
        for line in f.readlines():
            if line.startswith('#'):
                continue
            l = line.split("\t")
            data = {'name': l[0], 'interface': l[1], 'ip': l[2], 'vlan':l[3], 'vendor':l[4].strip("\n")}
            sco.append(data)
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
    
    for interface in nodoc['interfaces'][0]['interface']: # Obtencion de interfaces e instancias a migrar
        if(interface['name']['data']) in ifaces_list['sco']:  # Selecciono unicamente las que vamos a migrar
            if_name=interface['name']['data']
            
            if 'aggregated-ether-options' in interface.keys() and 'lacp' in interface['aggregated-ether-options'][0]:
                if 'active' in interface['aggregated-ether-options'][0]['lacp'][0].keys():
                    lacp = 'active'
                if 'passive' in interface['aggregated-ether-options'][0]['lacp'][0].keys():
                    lacp = 'passive'

                if lacp:
                    for switch in sco:
                        if if_name == switch['interface']:
                            switch['lacp']=lacp

            for unit in interface['unit']:
                interface_name = if_name + "." + str(unit['name']['data'])
                ifaces_list['all'].append(interface_name)
                ifaces_list['pending'].append(interface_name)

                for switch in sco:  #Cargo SCO
                    if switch['interface'] == if_name:
                        data = {'sco':switch['vlan']}

                data['nodoc_interface'] = interface_name

                if ('description' in unit.keys()): #Cargo descripcion
                    data['description']=unit['description'][0]['data']
                else:
                    data['description']= "Sin descripcion"
                                    
                if ('encapsulation' in unit.keys() and 
                    unit['encapsulation'][0]['data'] == 'vlan-vpls'):  # Identifico servicio VPLS
                   
                    ifaces_list['vpls'].append(interface_name)
                    ifaces_list['pending'].remove(interface_name)

                    data['service']='vpls'

                    if ('vlan-id' in unit.keys()):  # Identifico vlan
                        data['vlan']=unit['vlan-id'][0]['data']
                    
                    for instance in nodoc['routing-instances'][0]['instance']:
                        if ('interface' in instance.keys()):
                            for iface in instance['interface']:
                                if (interface_name == iface['name']['data']):
                                    if (instance['name']['data'] not in instances_list['vpls']):
                                        instances_list['vpls'].append(instance['name']['data'])
                                        instances_list['noassigned'].append(instance['name']['data'])
                                        data['ri_name_cv']=instance['name']['data']

                if ('encapsulation' in unit.keys() and 
                    unit['encapsulation'][0]['data'] == 'vlan-bridge'):  # Identifico bridges
                   
                    ifaces_list['bridge'].append(interface_name)
                    ifaces_list['pending'].remove(interface_name)
                    data['service']='bridge'

                    for domain in nodoc['bridge-domains'][0]['domain']:
                        if ('interface' in domain.keys()):
                            for iface in domain['interface']:
                                if (interface_name == iface['name']['data']):
                                    if (domain['name']['data'] not in instances_list['bridge']):
                                        instances_list['bridge'].append(domain['name']['data'])
                                        data['ri_name_cv']=domain['name']['data']
                    
                if ('family' in unit.keys() and 
                    'inet' in unit['family'][0].keys() and 
                    'address' in unit['family'][0]['inet'][0].keys()):  # Identifico IRS
                    
                    ifaces_list['irs'].append(interface_name)
                    ifaces_list['pending'].remove(interface_name)
                    data['service']='irs'
                    data['ip']=unit['family'][0]['inet'][0]['address'][0]['name']['data']

                    if ('vlan-id' in unit.keys()):  # Identifico vlan
                        data['vlan']=unit['vlan-id'][0]['data']
                
                    for instance in nodoc['routing-instances'][0]['instance']:
                        if ('interface' in instance.keys()):
                            for iface in instance['interface']:
                                if (interface_name == iface['name']['data']):
                                    ifaces_list['irs'].remove(interface_name)
                                    ifaces_list['vrf'].append(interface_name)
                                    data['service']='vrf'
                                    data['ri_name_cv']=instance['name']['data']
                                    if (instance['name']['data'] not in instances_list['vrf']):
                                        instances_list['vrf'].append(instance['name']['data'])
                                        instances_list['noassigned'].append(instance['name']['data'])

                
                if ('family' in unit.keys() and 
                    'bridge' in unit['family'][0].keys() and 
                    'interface-mode' in unit['family'][0]['bridge'][0].keys() and
                    unit['family'][0]['bridge'][0]['interface-mode'][0]['data'] == 'trunk'):
                    
                    ifaces_list['trunk'].append(interface_name)
                    ifaces_list['pending'].remove(interface_name)
                    data['service']='trunk'
    
                rac_config['interfaces'].append(data)

    for instance in nodoc['routing-instances'][0]['instance']:  # Obtencion de RT a partir de nodo C, grupos BGP
        if (instance['name']['data'] in instances_list['vpls']):
            data = {'ri_name_cv': instance['name']['data']}
            
            if ('description' in instance.keys()):
                data['description'] = instance['description'][0]['data']

            if ('interface' in instance.keys()):
                data['interfaces']=[]
                for interface in instance['interface']:
                    data['interfaces'].append(interface['name']['data'])

            if ('protocols' in instance.keys() and
                'vpls' in instance['protocols'][0].keys() and
                'vpls-id' in instance['protocols'][0]['vpls'][0].keys()):
                data['id_cv'] = instance['protocols'][0]['vpls'][0]['vpls-id'][0]['data']
                for vpn in vpns:
                    if (data['id_cv'] == vpns[vpn]['id_cv']):
                        data['id_fc'] = vpns[vpn]['id_fc']
                        data['ri_name_fc'] = vpn
                        if data['ri_name_cv'] in instances_list['noassigned']:
                            instances_list['noassigned'].remove(data['ri_name_cv'])
            rac_config['routing-instances'].append(data)                                

        if (instance['name']['data'] in instances_list['vrf']):
            data = {'ri_name_cv': instance['name']['data']}
            
            if ('description' in instance.keys()):
                data['description'] = instance['description'][0]['data']
            
            if ('interface' in instance.keys()):
                data['interfaces']=[]
                for interface in instance['interface']:
                    data['interfaces'].append(interface['name']['data'])            

            if ('vrf-target' in instance and 'vrf-import' not in instance):
                data['id_cv'] = instance['vrf-target'][0]['community'][0]['data'].split(":")[1] + ":" + instance['vrf-target'][0]['community'][0]['data'].split(":")[2]
                for vpn in vpns:
                    if data['id_cv'] == vpns[vpn]['id_cv']:
                        data['ri_name_fc'] = vpn
                        if data['name'] in instances_list['noassigned']:
                             instances_list['noassigned'].remove(data['name'])

            if ('vrf-import' in instance):
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
                                                    data['id_cv'] = member['data'].split(":")[1] + ":" + member['data'].split(":")[2]
                                                    for vpn in vpns:
                                                        if data['id_cv'] == vpns[vpn]['id_cv']:
                                                            data['id_fc'] = vpns[vpn]['id_fc']
                                                            data['ri_name_fc'] = vpn
                                                            if data['ri_name_cv'] in instances_list['noassigned']:
                                                                instances_list['noassigned'].remove(data['ri_name_cv'])

            if ('protocols' in instance.keys()):
                for protocol in instance['protocols'][0]:
                    if 'bgp' in instance['protocols'][0].keys():
                        if 'group' in instance['protocols'][0]['bgp'][0].keys():
                            data['bgp_groups']=[]
                            for group in instance['protocols'][0]['bgp'][0]['group']:
                                data_g={}
                                if 'description' in group.keys():
                                    data_g['description'] = group['description'][0]['data']
                                if 'name' in group.keys():
                                    data_g['name'] = group['name']['data']
                                if 'local_address' in group.keys():
                                    data_g['local_address'] = group['local-address'][0]['data']
                                if 'neighbor' in group.keys():
                                    data_g['neighbor'] = group['neighbor'][0]['name']['data']
                                    data_g['peer_as'] = group['neighbor'][0]['peer-as'][0]['data']
                                data['bgp_groups'].append(data_g)
            
            rac_config['routing-instances'].append(data)
            
    for route in nodoc['routing-options'][0]['static'][0]['route']:  # Obtencion de rutas estaticas Internet
        if ('tag' in route.keys() and
            route['tag'][0]['metric-value'][0]['data'] == '100'):
            data={'prefix':route['name']['data']}
            if 'next-hop' in route.keys():
                data['next_hop']=route['next-hop'][0]['data']
                # Verificar si es IRS:
                for interface in rac_config['interfaces']:
                    if interface['service'] == 'irs':
                        wan=IPNetwork(interface['ip'])
                        if data['next_hop'] in IPNetwork(wan.cidr):
                            interface['routes']=[]
                            interface['routes'].append(data)

    if instances_list['noassigned']:  # Verificacion de asignaciones
        print("\nLas siguientes instancias no tienen asignacion:\n")
        for instance in instances_list['noassigned']:
            pprint (instance)
        print("\n\nCompletar y volver a ejecutar.\n")
        return 

    for interface in rac_config['interfaces']:
        if ('ri_name_cv' in interface.keys() and 'ri_name_fc' not in interface.keys()):
            for instance in rac_config['routing-instances']:
                if instance['ri_name_cv'] == interface['ri_name_cv']:
                    interface['ri_name_fc'] = instance['ri_name_fc']

    for file in listdir("output"):  # Borro archivos en carpeta "output"
        remove("output/" + file)


    for switch in sco:
        create_sco(switch)

    for interface in rac_config['interfaces']:
        if ('ri_name_cv' not in interface.keys() and interface['service'] == 'irs'):
            create_irs_iface(interface)

    for interface in rac_config['interfaces']:
        if ('ri_name_cv' in interface.keys() and interface['service'] == 'vrf'):
            create_vrf_iface(interface)

    for interface in rac_config['interfaces']:
        if ('ri_name_cv' in interface.keys() and interface['service'] == 'vpls'):
            create_vpls_iface(interface)


if __name__ == '__main__':
        exit(main())

