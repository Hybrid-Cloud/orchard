#!/bin/sh
#2015.8.30 test ok
dir=`cd "$(dirname "$0")"; pwd`
RUN_SCRIPT=${dir}/enable_openstack_service_run.sh
RUN_LOG=${dir}/enable_openstack_service_run.log

az_domain=${1}
az_hostname=${az_domain%%".huawei.com"}

. /root/env.sh

which_sh=`which sh`
echo "#!"${which_sh} > ${RUN_SCRIPT}
echo ". /root/env.sh" >> ${RUN_SCRIPT}

cinder_service_list=`cinder service-list | grep ${az_hostname} | awk -F"|" '{print $2}'`

for service in `echo ${cinder_service_list}`
do
    echo cinder service-enable ${az_hostname} ${service} >> ${RUN_SCRIPT}
done

nova_service_list=`nova service-list | grep ${az_hostname} | awk -F "|" '{print $3}'`
for service in `echo ${nova_service_list}`
do
    echo nova service-enable ${az_hostname} ${service} >> ${RUN_SCRIPT}
done

sh ${RUN_SCRIPT} > ${RUN_LOG} 2>&1
