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
from netaddr import *

templateEnv = jinja2.Environment( loader=jinja2.FileSystemLoader( searchpath="templates" ) )

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

rac_config = {'interfaces':[], 'routing-instances':[], 'routes':[]}


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

                for element in sco:  #Cargo SCO
                    if sco[element]['interface'] == if_name:
                        data = {'sco':sco[element]['vlan']}

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
                                        data['instance']=instance['name']['data']

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
                                        data['instance']=domain['name']['data']
                    
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
                                    if (instance['name']['data'] not in instances_list['vrf']):
                                        instances_list['vrf'].append(instance['name']['data'])
                                        instances_list['noassigned'].append(instance['name']['data'])
                                        data['service']='vrf'
                                        data['instance']=instance['name']['data']
                
                if ('family' in unit.keys() and 
                    'bridge' in unit['family'][0].keys() and 
                    'interface-mode' in unit['family'][0]['bridge'][0].keys() and
                    unit['family'][0]['bridge'][0]['interface-mode'][0]['data'] == 'trunk'):
                    
                    ifaces_list['trunk'].append(interface_name)
                    ifaces_list['pending'].remove(interface_name)
                    data['service']='trunk'
    
                rac_config['interfaces'].append(data)

    for instance in nodoc['routing-instances'][0]['instance']:
        if (instance['name']['data'] in instances_list['vpls']):
            data = {'name': instance['name']['data']}
            
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
                        vpns[vpn]['alias'] = data['name']
                        data['id_fc'] = vpns[vpn]['id_fc']
                        if data['name'] in instances_list['noassigned']:
                            instances_list['noassigned'].remove(data['name'])
                                        

        if (instance['name']['data'] in instances_list['vrf']):
            data = {'name': instance['name']['data']}
            
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
                        vpns[vpn]['alias'] = data['name']
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
                                                            vpns[vpn]['alias'] = data['name']
                                                            data['id_fc'] = vpns[vpn]['id_fc']
                                                            if data['name'] in instances_list['noassigned']:
                                                                instances_list['noassigned'].remove(data['name'])

            rac_config['routing-instances'].append(data)
 
    for route in nodoc['routing-options'][0]['static'][0]['route']:
        if ('tag' in route.keys() and
            route['tag'][0]['metric-value'][0]['data'] == '100'):
            data={'prefix':route['name']['data']}
            if 'next-hop' in route.keys():
                data['next_hop']=route['next-hop'][0]['data']
                
                    # Verificar si es IRS:
                for interface in rac_config['interfaces']:
                    if interface['service'] == 'irs':
                        wan=IPNetwork(interface['ip'])
                        #pprint(wan.cidr)
                        if data['next_hop'] in IPNetwork(wan.cidr):
                            rac_config['routes'].append(data)

    if instances_list['noassigned']:
        print("\nLas siguientes instancias no tienen asignacion:\n")
        for instance in instances_list['noassigned']:
            pprint (instance)
        print("\n\nCompletar y volver a ejecutar.\n")
        return  # Verififacion de asignacion de VPNS:

    pprint(rac_config)

    for file in listdir("output"):  # Borro archivos en carpeta "output"
        remove("output/" + file)


if __name__ == '__main__':
        exit(main())
