#!/usr/bin/python3
# Migrador de nodo completo

from pprint import pprint
import json


f_nodoc= 'files/test.json'
f_rac= 'files/rac.json'
f_sac= 'files/sac.json'
f_rbb= 'files/rbb.json'
f_sco= 'files/sco.txt'

def main():
    
    nodoc_data=open(f_nodoc).read()
    nodoc = json.loads(nodoc_data)

  	#with open(f_sco) as f:  # Lectura de archivo sco.txt
    #    for line in f.readlines():
    #        if line.startswith('#'):
    #            continue
    #        l = line.split("\t")
    #        if l[0] not in sco:
    #            sco[l[0]] = {'interface': l[1], 'ip': l[2], 'vlan':l[3], 'vendor':l[4]}
    #            sco_interfaces.append(l[1])



if __name__ == '__main__':
        exit(main())
