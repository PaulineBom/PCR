#!/bin/bash 
#PBS -N test-np
#PBS -q np
#PBS -l EC_nodes=1
#PBS -l EC_total_tasks=72
#PBS -l EC_hyperthreads=2
#PBS -l EC_billing_account=c3s432l3

#PBS -M hsutanudjajacchms99@yahoo.com

aprun -N $EC_tasks_per_node -n $EC_total_tasks -j $EC_hyperthreads ./test_aprun.sh

