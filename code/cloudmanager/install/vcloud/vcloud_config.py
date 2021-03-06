

import os
import pdb
from heat.openstack.common import log as logging
from heat.engine.resources.cloudmanager.vpn_configer import VpnConfiger
from heat.engine.resources.cloudmanager.vpn import VPN
import heat.engine.resources.cloudmanager.constant as constant
#from vcloudcloudpersist import VcloudCloudDataHandler
from vcloud_cloud_info_persist import *
import threading
import time
import heat.engine.resources.cloudmanager.proxy_manager
from heat.engine.resources.cloudmanager.cascading_configer import CascadingConfiger
from vcloud_cascaded_configer import CascadedConfiger

from heat.engine.resources.cloudmanager.commonutils import *
import heat.engine.resources.cloudmanager.exception as exception


LOG = logging.getLogger(__name__)

class VcloudConfig:
    def __init__(self):
        self.cloud_info = None
        self.proxy_info = None
        self.cloud_params = None
        self.cloud_info_handler = None

    def initialize(self, cloud_params, cloud_info):
        self.cloud_params = cloud_params

        self.cloud_info = cloud_info
        self.proxy_info = self.cloud_info["proxy_info"]
        cloud_id = self.cloud_info["cloud_id"]
        self.cloud_info_handler = \
            VcloudCloudInfoPersist(constant.VcloudConstant.CLOUD_INFO_FILE, cloud_id)


    def _modify_cascaded_external_api(self):
        #ssh to vpn, then ssh to cascaded through vpn tunnel_bearing_ip
        modify_cascaded_api_domain_cmd = 'cd %(dir)s; ' \
                    'source /root/adminrc; ' \
                    'python %(script)s '\
                    '%(cascading_domain)s %(cascading_api_ip)s '\
                    '%(cascaded_domain)s %(cascaded_ip)s '\
                    '%(gateway)s'\
                    % {"dir": constant.Cascaded.REMOTE_HWS_SCRIPTS_DIR,
                       "script":constant.Cascaded.MODIFY_CASCADED_SCRIPT_PY,
                       "cascading_domain": self.cloud_info['cascading_info']['domain'],
                       "cascading_api_ip": self.cloud_info["cascading_info"]["external_api_ip"],
                       "cascaded_domain": self.cloud_info["cascaded_info"]['domain'],
                       "cascaded_ip": self.cloud_info["cascaded_info"]["external_api_ip"],
                       "gateway": self.cloud_info['cascaded_subnets_info']['external_api_gateway_ip']}
        #pdb.set_trace()
        for i in range(100):
            try:
                execute_cmd_without_stdout(
                    host= self.cloud_info["cascaded_vpn_info"]["public_ip"],
                    user=constant.VpnConstant.VPN_ROOT,
                    password=constant.VpnConstant.VPN_ROOT_PWD,
                    cmd='cd %(dir)s; python %(script)s '
                        '%(cascaded_tunnel_ip)s %(user)s %(passwd)s \'%(cmd)s\''
                    % {"dir": constant.VpnConstant.REMOTE_ROUTE_SCRIPTS_DIR,
                       "script": constant.VpnConstant.MODIFY_CASCADED_API_SCRIPT,
                       "cascaded_tunnel_ip": self.cloud_info["cascaded_info"]["tunnel_bearing_ip"],
                       "user": constant.VcloudConstant.ROOT,
                       "passwd": constant.VcloudConstant.ROOT_PWD,
                       "cmd": modify_cascaded_api_domain_cmd})
                return True
            except Exception:
                #wait cascaded vm to reboot ok
                time.sleep(10)
                continue
        LOG.error("modify cascaded=%s external_api ip and domain error"
                  % self.cloud_info["cascaded_info"]["tunnel_bearing_ip"])

    def config_vpn_only(self):
        LOG.info("config vcloud vpn only")
        cloud_vpn_cf = VpnConfiger(
                    host_ip=self.cloud_info["cascaded_vpn_info"]["public_ip"],
                    user=constant.VpnConstant.VCLOUD_VPN_ROOT,
                    password=constant.VpnConstant.VCLOUD_VPN_ROOT_PWD)

        cloud_vpn_cf.register_add_conns(
                    tunnel_name=self.cloud_info["vpn_conn_name"]["api_conn_name"],
                    left_public_ip=self.cloud_info["cascaded_vpn_info"]["public_ip"],
                    left_subnet=self.cloud_info["cascaded_subnets_info"]["external_api"],
                    right_public_ip=self.cloud_info["cascading_vpn_info"]["public_ip"],
                    right_subnet=self.cloud_info["cascading_subnets_info"]["external_api"])

        cloud_vpn_cf.register_add_conns(
                    tunnel_name=self.cloud_info["vpn_conn_name"]["tunnel_conn_name"],
                    left_public_ip=self.cloud_info["cascaded_vpn_info"]["public_ip"],
                    left_subnet=self.cloud_info["cascaded_subnets_info"]["tunnel_bearing"],
                    right_public_ip=self.cloud_info["cascading_vpn_info"]["public_ip"],
                    right_subnet=self.cloud_info["cascading_subnets_info"]["tunnel_bearing"])
        cloud_vpn_cf.do_config()

    def config_vpn(self):
        if self.cloud_params['project_info']['LocalMode'] == True :
            LOG.info("config cascading vpn")
            local_vpn_cf = VpnConfiger(
                    host_ip=self.cloud_info["cascading_vpn_info"]["public_ip"],
                    user=constant.VpnConstant.VPN_ROOT,
                    password=constant.VpnConstant.VPN_ROOT_PWD)

            local_vpn_cf.register_add_conns(
                    tunnel_name=self.cloud_info["vpn_conn_name"]["tunnel_conn_name"],
                    left_public_ip=self.cloud_info["cascading_vpn_info"]["public_ip"],
                    left_subnet=self.cloud_info["cascading_subnets_info"]["tunnel_bearing"],
                    right_public_ip=self.cloud_info["cascaded_vpn_info"]["public_ip"],
                    right_subnet=self.cloud_info["cascaded_subnets_info"]["tunnel_bearing"])
            local_vpn_cf.do_config()

            LOG.info("config vcloud vpn thread")
            cloud_vpn_cf = VpnConfiger(
                    host_ip=self.cloud_info["cascaded_vpn_info"]["public_ip"],
                    user=constant.VpnConstant.VCLOUD_VPN_ROOT,
                    password=constant.VpnConstant.VCLOUD_VPN_ROOT_PWD)

            cloud_vpn_cf.register_add_conns(
                    tunnel_name=self.cloud_info["vpn_conn_name"]["tunnel_conn_name"],
                    left_public_ip=self.cloud_info["cascaded_vpn_info"]["public_ip"],
                    left_subnet=self.cloud_info["cascaded_subnets_info"]["tunnel_bearing"],
                    right_public_ip=self.cloud_info["cascading_vpn_info"]["public_ip"],
                    right_subnet=self.cloud_info["cascading_subnets_info"]["tunnel_bearing"])
            cloud_vpn_cf.do_config()
        else :
            LOG.info("config cascading vpn")
            local_vpn_cf = VpnConfiger(
                    host_ip=self.cloud_info["cascading_vpn_info"]["public_ip"],
                    user=constant.VpnConstant.VPN_ROOT,
                    password=constant.VpnConstant.VPN_ROOT_PWD)

            local_vpn_cf.register_add_conns(
                    tunnel_name=self.cloud_info["vpn_conn_name"]["api_conn_name"],
                    left_public_ip=self.cloud_info["cascading_vpn_info"]["public_ip"],
                    left_subnet=self.cloud_info["cascading_subnets_info"]["external_api"],
                    right_public_ip=self.cloud_info["cascaded_vpn_info"]["public_ip"],
                    right_subnet=self.cloud_info["cascaded_subnets_info"]["external_api"])

            local_vpn_cf.register_add_conns(
                    tunnel_name=self.cloud_info["vpn_conn_name"]["tunnel_conn_name"],
                    left_public_ip=self.cloud_info["cascading_vpn_info"]["public_ip"],
                    left_subnet=self.cloud_info["cascading_subnets_info"]["tunnel_bearing"],
                    right_public_ip=self.cloud_info["cascaded_vpn_info"]["public_ip"],
                    right_subnet=self.cloud_info["cascaded_subnets_info"]["tunnel_bearing"])
            local_vpn_cf.do_config()

    def config_route(self):
        if self.cloud_params['project_info']['LocalMode'] == True :
            LOG.info("add route to cascading ...")
            self._add_vpn_route(
                    host_ip=self.cloud_info["cascading_info"]["external_api_ip"],
                    user=constant.Cascading.ROOT,
                    passwd=constant.Cascading.ROOT_PWD,
                    access_cloud_tunnel_subnet=self.cloud_info["cascaded_subnets_info"]["tunnel_bearing"],
                    tunnel_gw=self.cloud_info["cascading_vpn_info"]["tunnel_bearing_ip"])

            check_host_status(
                        host=self.cloud_info["cascaded_info"]["public_ip"],
                        user=constant.VcloudConstant.ROOT,
                        password=constant.VcloudConstant.ROOT_PWD,
                        retry_time=100, interval=3)    #wait cascaded vm started

            LOG.info("add route to vcloud on cascaded ...")
            self._add_vpn_route(
                    host_ip=self.cloud_info["cascaded_info"]["public_ip"],
                    user=constant.VcloudConstant.ROOT,
                    passwd=constant.VcloudConstant.ROOT_PWD,
                    access_cloud_tunnel_subnet=self.cloud_info["cascading_subnets_info"]["tunnel_bearing"],
                    tunnel_gw=self.cloud_info["cascaded_vpn_info"]["tunnel_bearing_ip"])

        else :
             LOG.info("add route to cascading ...")
             self._add_vpn_route_with_api(
                    host_ip=self.cloud_info["cascading_info"]["external_api_ip"],
                    user=constant.Cascading.ROOT,
                    passwd=constant.Cascading.ROOT_PWD,
                    access_cloud_api_subnet=self.cloud_info["cascaded_subnets_info"]["external_api"],
                    api_gw=self.cloud_info["cascading_vpn_info"]["external_api_ip"],
                    access_cloud_tunnel_subnet=self.cloud_info["cascaded_subnets_info"]["tunnel_bearing"],
                    tunnel_gw=self.cloud_info["cascading_vpn_info"]["tunnel_bearing_ip"])

             LOG.info("add route to vcloud on cascaded ...")
             while True:
                 check_host_status(
                        host=self.cloud_info["cascaded_info"]["tunnel_bearing_ip"],
                        user=constant.VcloudConstant.ROOT,
                        password=constant.VcloudConstant.ROOT_PWD,
                        retry_time=100, interval=3)    #waite cascaded vm started

                 self._add_vpn_route_with_api(
                        host_ip=self.cloud_info["cascaded_info"]["tunnel_bearing_ip"],
                        user=constant.VcloudConstant.ROOT,
                        passwd=constant.VcloudConstant.ROOT_PWD,
                        access_cloud_api_subnet=self.cloud_info["cascading_subnets_info"]["external_api"],
                        api_gw=self.cloud_info["cascaded_info"]["external_api_ip"],
                        access_cloud_tunnel_subnet=self.cloud_info["cascading_subnets_info"]["tunnel_bearing"],
                        tunnel_gw=self.cloud_info["cascaded_info"]["tunnel_bearing_ip"])
                 try :
                     flag = check_host_status(
                            host=self.cloud_info["cascaded_info"]["external_api_ip"],
                            user=constant.VcloudConstant.ROOT,
                            password=constant.VcloudConstant.ROOT_PWD,
                            retry_time=1, interval=1)    #test api net
                 except Exception:
                     continue    #add vpn route again

                 if flag :
                     break


    def _enable_network_cross(self):
        cloud_id = self.cloud_info["cloud_id"]

        vpn_cfg = VpnConfiger(
                host_ip=self.cloud_info["cascaded_vpn_info"]["public_ip"],
                user=constant.VpnConstant.VPN_ROOT,
                password=constant.VpnConstant.VPN_ROOT_PWD)

        for other_cloud_id in self.cloud_info_handler.list_all_cloud_id():
            if other_cloud_id == cloud_id:
                continue

            other_cloud = \
                self.cloud_info_handler.get_cloud_info_with_id(other_cloud_id)
            if not other_cloud["access"]:
                continue

            other_vpn_cfg = VpnConfiger(host_ip=other_cloud["cascaded_vpn_info"]["public_ip"],
                            user=constant.VpnConstant.VPN_ROOT,
                            password=constant.VpnConstant.VPN_ROOT_PWD)

            LOG.info("add conn on tunnel vpns...")
            tunnel_conn_name = "%s-tunnel-%s" % (cloud_id, other_cloud_id)
            vpn_cfg.register_add_conns(
                tunnel_name=tunnel_conn_name,
                left_public_ip=self.cloud_info[" "]["public_ip"],
                left_subnet=self.cloud_info["cascaded_subnets_info"]["tunnel_bearing"],
                right_public_ip=other_cloud["cascaded_vpn_info"]["public_ip"],
                right_subnet=other_cloud["cascaded_subnets_info"]["tunnel_bearing"])

            other_vpn_cfg.register_add_conns(
                tunnel_name=tunnel_conn_name,
                left_public_ip=other_cloud["cascaded_vpn_info"]["public_ip"],
                left_subnet=other_cloud["cascaded_subnets_info"]["tunnel_bearing"],
                right_public_ip=self.cloud_info['cascaded_vpn_info']['public_ip'],
                right_subnet=self.cloud_info['cascaded_subnets_info']['tunnel_bearing'])
            vpn_cfg.do_config()
            other_vpn_cfg.do_config()

            LOG.info("add route on cascadeds...")
            execute_cmd_without_stdout(
                host=self.cloud_info["cascaded_info"]["public_ip"],
                user=constant.HwsConstant.ROOT,
                password=constant.HwsConstant.ROOT_PWD,
                cmd='cd %(dir)s; sh %(script)s %(subnet)s %(gw)s'
                    % {"dir": constant.Cascaded.REMOTE_HWS_SCRIPTS_DIR,
                       "script": constant.Cascaded.ADD_API_ROUTE_SCRIPT,
                       "subnet": other_cloud["cascaded_subnets_info"]["tunnel_bearing"],
                       "gw": self.cloud_info["cascaded_vpn_info"]['tunnel_bearing_ip']})

            execute_cmd_without_stdout(
                host=other_cloud["cascaded_info"]["public_ip"],
                user=constant.HwsConstant.ROOT,
                password=constant.HwsConstant.ROOT_PWD,
                cmd='cd %(dir)s; sh %(script)s %(subnet)s %(gw)s'
                    % {"dir": constant.Cascaded.REMOTE_HWS_SCRIPTS_DIR,
                       "script": constant.Cascaded.ADD_API_ROUTE_SCRIPT,
                       "subnet": self.cloud_info["cascaded_subnets_info"]["tunnel_bearing"],
                       "gw": other_cloud["cascaded_vpn_info"]['tunnel_bearing_ip']})

            # add cloud-sg
            LOG.info("add security group...")
            #TODO
        return True





    @staticmethod
    def _add_vpn_route_with_api(host_ip, user, passwd,
                       access_cloud_api_subnet, api_gw,
                       access_cloud_tunnel_subnet, tunnel_gw):
        try:
            execute_cmd_without_stdout(
                host=host_ip,
                user=user,
                password=passwd,
                cmd='cd %(dir)s; sh %(script)s '
                    '%(access_cloud_api_subnet)s %(api_gw)s %(access_cloud_tunnel_subnet)s %(tunnel_gw)s'
                    % {"dir": constant.VpnConstant.REMOTE_ROUTE_SCRIPTS_DIR,
                       "script": constant.VpnConstant.ADD_VPN_ROUTE_SCRIPT,
                       "access_cloud_api_subnet":access_cloud_api_subnet,
                       "api_gw":api_gw,
                       "access_cloud_tunnel_subnet": access_cloud_tunnel_subnet,
                       "tunnel_gw": tunnel_gw})
        except exception.SSHCommandFailure:
            LOG.error("add vpn route error, host: %s" % host_ip)
            return False
        return True

    @staticmethod
    def _add_vpn_route(host_ip, user, passwd,
                       access_cloud_tunnel_subnet, tunnel_gw):
        try:
            execute_cmd_without_stdout(
                host=host_ip,
                user=user,
                password=passwd,
                cmd='cd %(dir)s; sh %(script)s '
                    '%(access_cloud_tunnel_subnet)s %(tunnel_gw)s'
                    % {"dir": constant.VpnConstant.REMOTE_ROUTE_SCRIPTS_DIR,
                       "script": constant.VpnConstant.ADD_VPN_ROUTE_SCRIPT,
                       "access_cloud_tunnel_subnet": access_cloud_tunnel_subnet,
                       "tunnel_gw": tunnel_gw})
        except exception.SSHCommandFailure:
            LOG.error("add vpn route error, host: %s" % host_ip)
            return False
        return True

    def config_cascading(self):
        #TODO(lrx):remove v2v_gw
        LOG.info("config cascading")
        if self.cloud_params['project_info']['LocalMode'] == True :
            cascaded_api_ip = self.cloud_info["cascaded_info"]['public_ip']
        else :
            cascaded_api_ip = self.cloud_info["cascaded_info"]['external_api_ip']

        cascading_cf = CascadingConfiger(
                cascading_ip=self.cloud_info["cascading_info"]["external_api_ip"],
                user=constant.Cascading.ROOT,
                password=constant.Cascading.ROOT_PWD,
                cascaded_domain=self.cloud_info["cascaded_info"]["domain"],
                cascaded_api_ip=cascaded_api_ip,
                v2v_gw='1.1.1.1')
        cascading_cf.do_config()

    def config_cascaded(self):
        LOG.info("config cascaded")
        self._modify_cascaded_external_api()    #modify cascaded external api first

        cascaded_public_ip = self.cloud_info["cascaded_info"]["public_ip"]

        cascaded_cf = CascadedConfiger(
                public_ip_api=cascaded_public_ip,
                api_ip=self.cloud_info["cascaded_info"]["external_api_ip"],
                domain=self.cloud_info["cascaded_info"]["domain"],
                user=constant.VcloudConstant.ROOT,
                password=constant.VcloudConstant.ROOT_PWD,
                cascading_domain=self.cloud_info["cascading_info"]["domain"],
                cascading_api_ip=self.cloud_info["cascading_info"]["external_api_ip"])

        cascaded_cf.do_config()

    def config_proxy(self):
        # config proxy on cascading host
        #pdb.set_trace()
        LOG.info("config proxy ...")
        if self.proxy_info is None:
            raise InstallCascadedFailed("no proxy , install cascaded failed")


        LOG.info("add dhcp to proxy ...")

        proxy_id = self.proxy_info["id"]
        proxy_num = self.proxy_info["proxy_num"]
        LOG.debug("proxy_id = %s, proxy_num = %s"
                     % (proxy_id, proxy_num))

        self._config_proxy(self.cloud_info["cascading_info"]["external_api_ip"], self.proxy_info)

    @staticmethod
    def _config_proxy(cascading_ip, proxy_info):
        LOG.info("command role host add...")
        for i in range(3):
            try:
                execute_cmd_without_stdout(
                    host=cascading_ip,
                    user=constant.Cascading.ROOT,
                    password=constant.Cascading.ROOT_PWD,
                    cmd="cps role-host-add --host %(proxy_host_name)s dhcp;"
                        "cps commit"
                        % {"proxy_host_name": proxy_info["id"]})
            except exception.SSHCommandFailure:
                LOG.error("config proxy error, try again...")
        return True


    def config_patch(self):
        #TODO(lrx):modify to vcloud patch
        LOG.info("config patches config ...")
        #pdb.set_trace()
        if self.cloud_params['project_info']['LocalMode'] == True :
            cascaded_public_ip = self.cloud_info["cascaded_info"]["public_ip"]
        else :
            cascaded_public_ip = self.cloud_info["cascaded_info"]['external_api_ip']

        self._config_patch_tools(
                host_ip=self.cloud_info["cascading_info"]["external_api_ip"],
                user=constant.Cascading.ROOT,
                passwd=constant.Cascading.ROOT_PWD,
                cascaded_domain=self.cloud_info["cascaded_info"]["domain"],
                proxy_info=self.proxy_info,
                )

        self._config_vcloud(
                host_ip=cascaded_public_ip,
                user=constant.VcloudConstant.ROOT,
                passwd=constant.VcloudConstant.ROOT_PWD)


        self._deploy_patches(host_ip=self.cloud_info["cascading_info"]["external_api_ip"],
                             user=constant.Cascading.ROOT,
                             passwd=constant.Cascading.ROOT_PWD)

    def _config_patch_tools(self, host_ip, user, passwd,
                            cascaded_domain, proxy_info):
        for i in range(10):
            try:
                execute_cmd_without_stdout(
                    host=host_ip, user=user, password=passwd,
                    cmd='cd %(dis)s; sh %(script)s '
                        '%(proxy_num)s %(proxy_host_name)s %(cascaded_domain)s '
                        '%(cascading_domain)s'
                        % {"dis": constant.PatchesConstant.REMOTE_SCRIPTS_DIR,
                           "script":
                               constant.PatchesConstant.CONFIG_PATCHES_SCRIPT,
                           "proxy_num": self.cloud_info["proxy_info"]["proxy_num"],
                           "proxy_host_name": self.cloud_info["proxy_info"]["id"],
                           "cascaded_domain": self.cloud_info["cascaded_info"]["domain"],
                           "cascading_domain": self.cloud_info["cascading_info"]["domain"]})
                return True
            except Exception as e:
                LOG.error("config patch tool error, error: %s"
                             % e.message)
                continue
        return True

    def _config_vcloud(self,host_ip, user, passwd):
        for i in range(5):
            try:
                execute_cmd_without_stdout(
                    host=host_ip, user=user, password=passwd,
                    cmd='cd %(dis)s; sh %(script)s '
                        '%(vcloud_host_ip)s %(vcloud_org)s %(vcloud_vdc)s '
                        '%(vcloud_user)s %(vcloud_password)s '
                        '%(vcloud_tunnel_cidr)s %(vcloud_route_gw)s '
                        % {"dis": constant.Cascaded.REMOTE_VCLOUD_SCRIPTS_DIR,
                           "script":
                               constant.Cascaded.CONFIG_VCLOUD_SCRIPT,
                           "vcloud_host_ip": self.cloud_params["project_info"]["VcloudUrl"] ,
                           "vcloud_org": self.cloud_params["project_info"]["VcloudOrg"] ,
                           "vcloud_vdc": self.cloud_params["project_info"]["VcloudVdc"] ,
                           "vcloud_user": self.cloud_params["project_info"]["UserName"] ,
                           "vcloud_password": self.cloud_params["project_info"]["PassWd"] ,
                           "vcloud_tunnel_cidr": self.cloud_info["cascaded_subnets_info"]["tunnel_bearing"],
                           "vcloud_route_gw" : self.cloud_info["cascaded_vpn_info"]["tunnel_bearing_ip"]})

                self._restart_nova_and_cinder_computer(host_ip, user, passwd)

                return True
            except Exception as e:
                LOG.error("config vcloud error, error: %s" % e.message)
                continue
        return True

    @staticmethod
    def _restart_nova_and_cinder_computer(host_ip, user, passwd):
        execute_cmd_without_stdout(
            host=host_ip, user=user, password=passwd,
            cmd='source /root/adminrc;'
                'cps host-template-instance-operate --action stop --service nova nova-compute')
        time.sleep(1)
        execute_cmd_without_stdout(
            host=host_ip, user=user, password=passwd,
            cmd='source /root/adminrc;'
                'cps host-template-instance-operate --action start --service nova nova-compute')
        execute_cmd_without_stdout(
            host=host_ip, user=user, password=passwd,
            cmd='source /root/adminrc;'
                'cps host-template-instance-operate --action stop --service cinder cinder-volume')
        time.sleep(1)
        execute_cmd_without_stdout(
            host=host_ip, user=user, password=passwd,
            cmd='source /root/adminrc;'
                'cps host-template-instance-operate --action start --service cinder cinder-volume')


    @staticmethod
    def _deploy_patches(host_ip, user, passwd):
        execute_cmd_without_stdout(
            host=host_ip, user=user, password=passwd,
            cmd='cd %s; python config.py cascading'
                % constant.PatchesConstant.PATCH_LUNCH_DIR)


        return True


    def config_storge(self):
        LOG.info("config storage...")
        self._config_storage(
                host=self.cloud_info["cascaded_info"]["tunnel_bearing_ip"],
                user=constant.VcloudConstant.ROOT,
                password=constant.VcloudConstant.ROOT_PWD,
                cascading_domain=self.cloud_info["cascading_info"]["domain"] ,
                cascaded_domain=self.cloud_info["cascaded_info"]["domain"] ,
                )

    def _config_storage(self, host, user, password, cascading_domain,
                        cascaded_domain):
        # 1. create env file and config cinder on cascaded host
        for i in range(7):
            try:
                execute_cmd_without_stdout(
                    host=host, user=user, password=password,
                    cmd='cd %(dir)s;'
                        'sh %(create_env_script)s %(cascading_domain)s '
                        '%(cascaded_domain)s;'
                        % {"dir": constant.Cascaded.REMOTE_VCLOUD_SCRIPTS_DIR,
                           "create_env_script": constant.Cascaded.CREATE_ENV,
                           "cascading_domain": self.cloud_info["cascading_info"]["domain"],
                           "cascaded_domain": self.cloud_info["cascaded_info"]["domain"],
                           })
                break
            except Exception as e1:
                LOG.error("modify env file and config cinder "
                             "on cascaded host error: %s"
                             % e1.message)
                time.sleep(1)
                continue

        return True


    #TODO(lrx):config the network between cloud and cloud
    def config_extnet(self):
        self._config_extnet()

    def _config_extnet(self):
        self._enable_network_cross()

    @staticmethod
    def _update_l3_agent_conf(host_ip, user, passwd,
                              vcloud_region, access_key, secret_key,
                              subnet_cidr, interface_ip, interface_id,
                              used_ips):
        for i in range(3):
            try:
                execute_cmd_without_stdout(
                        host=host_ip, user=user, password=passwd,
                        cmd="cd %(dir)s; "
                            "sh %(script)s "
                            "%(vcloud_region)s %(access_key)s %(secret_key)s "
                            "%(subnet_cidr)s %(interface_ip)s "
                            "%(interface_id)s %(used_ips)s"
                            % {"dir": constant.Cascaded.REMOTE_SCRIPTS_DIR,
                               "script": constant.Cascaded.UPDATE_L3_AGENT_SCRIPT,
                               "vcloud_region": vcloud_region,
                               "access_key": access_key,
                               "secret_key": secret_key,
                               "subnet_cidr": subnet_cidr,
                               "interface_ip": interface_ip,
                               "interface_id": interface_id,
                               "used_ips": ",".join(used_ips)})
                break
            except Exception as e:
                LOG.error("update l3 agent error, error: %s" % e.message)
                time.sleep(1)
                continue

    @staticmethod
    def _update_l3_proxy_code(proxy_ip, user, passwd, proxy_num):
        restart_proxy_cmd = "cps host-template-instance-operate " \
                            "--action stop " \
                            "--service neutron neutron-l3-%s; " \
                            "sleep 2s; " \
                            "cps host-template-instance-operate " \
                            "--action start " \
                            "--service neutron neutron-l3-%s" \
                            % (proxy_num, proxy_num)
        for i in range(3):
            try:
                scp_file_to_host(host=proxy_ip, user=user, password=passwd,
                                 file_name=constant.Proxy.L3_PROXY_CODE,
                                 local_dir=constant.Proxy.LOCAL_NEUTRON_PROXY_DIR,
                                 remote_dir=constant.Proxy.REMOTE_NEUTRON_PROXY_DIR)

                execute_cmd_without_stdout(
                        host=proxy_ip, user=user, password=passwd,
                        cmd=restart_proxy_cmd)
                LOG.info("update l3 proxy code success.")
                return True
            except Exception as e:
                LOG.error("update l3 proxy code error, "
                             "proxy_ip: %s, proxy_num: %s. error: %s"
                             % (proxy_ip, proxy_num, e.message))
        LOG.error("update l3 proxy code failed, please check it."
                     "proxy_ip: %s, proxy_num: %s." % (proxy_ip, proxy_num))
        return False

    @staticmethod
    def _update_external_api_vlan(host_ip, user, passwd, vlan):
        for i in range(3):
            try:
                execute_cmd_without_stdout(
                        host=host_ip, user=user, password=passwd,
                        cmd='cd %(dir)s;'
                            'sh %(update_network_vlan_script)s '
                            '%(network_name)s %(vlan)s'
                            % {"dir": constant.Cascaded.REMOTE_SCRIPTS_DIR,
                               "update_network_vlan_script":
                                   constant.Cascaded.UPDATE_NETWORK_VLAN_SCRIPT,
                               "network_name": "external_api",
                               "vlan": vlan})
                break
            except Exception as e:
                LOG.error("update network vlan error, vlan: %s, error: %s "
                             % (vlan, e.message))
                time.sleep(1)
                continue

    def _create_ext_net(host_ip, user, passwd, alias, vlan):
        ext_net_name = "ext-%s-net" % alias
        create_net_cmd = ". /root/adminrc;" \
                         "neutron net-delete %(ext_net_name)s; " \
                         "neutron net-create %(ext_net_name)s " \
                         "--router:external " \
                         "--provider:physical_network physnet2 " \
                         "--provider:network_type vlan " \
                         "--provider:segmentation_id %(vlan)s" \
                         % {"ext_net_name": ext_net_name,
                            "vlan": vlan}
        for i in range(3):
            try:
                execute_cmd_without_stdout(host=host_ip, user=user,
                                           password=passwd, cmd=create_net_cmd)
                break
            except Exception as e:
                LOG.error("create ext network error, vlan: %s, error: %s "
                             % (vlan, e.message))
                time.sleep(1)
                continue

    @staticmethod
    def _create_ext_subnet(host_ip, user, passwd, alias, eips):
        if not eips:
            return False

        ext_cidr = "%s.0.0.0/8" % eips[0].split(".")[0]
        ext_net_name = "ext-%s-net" % alias
        ext_subnet_name = "ext-%s-subnet" % alias

        create_subnet_cmd = ". /root/adminrc; " \
                            "neutron subnet-create %(ext_net_name)s " \
                            "%(net_cidr)s --name %(ext_subnet_name)s" \
                            % {"ext_net_name": ext_net_name,
                               "net_cidr": ext_cidr,
                               "ext_subnet_name": ext_subnet_name}

        for eip in eips:
            create_subnet_cmd += ' --allocation-pool start=%s,end=%s' \
                                 % (eip, eip)

        create_subnet_cmd += ' --disable-dhcp --no-gateway'

        for i in range(3):
            try:
                execute_cmd_without_stdout(host=host_ip, user=user,
                                           password=passwd,
                                           cmd=create_subnet_cmd)
                break
            except Exception as e:
                LOG.error("create ext subnet error, alias: %s, "
                             "ext_cidr: %s, used_ips: %s. error: %s"
                             % (alias, ext_cidr, eips, e.message))
                time.sleep(1)
                continue

    @staticmethod
    def _update_proxy_params(host_ip, user, passwd, proxy_num, ext_net_name):
        for i in range(3):
            try:
                execute_cmd_without_stdout(
                        host=host_ip, user=user, password=passwd,
                        cmd="cd %(dir)s; "
                            "sh %(script)s %(proxy_num)s %(ext_net_num)s"
                            % {"dir": constant.Cascading.REMOTE_SCRIPTS_DIR,
                               "script": constant.Cascading.UPDATE_PROXY_PARAMS,
                               "proxy_num": proxy_num,
                               "ext_net_num": ext_net_name})
                break
            except Exception as e:
                LOG.error("update proxy params error, proxy_num: %s, "
                             "ext_net_name: %s"
                             % (proxy_num, ext_net_name))
                time.sleep(1)
                continue



    def remove_existed_cloud(self):
        #config cascading unregister
        #TODO(lrx):modify remove aggregate
        # try:
        #     execute_cmd_without_stdout(
        #         host=self.installer.cascading_api_ip,
        #         user=constant.Cascading.ROOT,
        #         password=constant.Cascading.ROOT_PWD,
        #         cmd='cd %(dir)s; sh %(script)s %(cascaded_domain)s'
        #             % {"dir": constant.RemoveConstant.REMOTE_SCRIPTS_DIR,
        #                "script":
        #                    constant.RemoveConstant.REMOVE_AGGREGATE_SCRIPT,
        #                "cascaded_domain": self.cloudinfo.cascaded_domain})
        # except Exception as e:
        #     LOG.error("remove aggregate error, error: %s" % e.message)

        try:
            execute_cmd_without_stdout(
                host=self.cloud_info["cascading_info"]["external_api_ip"],
                user=constant.Cascading.ROOT,
                password=constant.Cascading.ROOT_PWD,
                cmd='cd %(dir)s; sh %(script)s %(cascaded_domain)s'
                    % {"dir": constant.RemoveConstant.REMOTE_SCRIPTS_DIR,
                       "script":
                           constant.RemoveConstant.REMOVE_CINDER_SERVICE_SCRIPT,
                       "cascaded_domain": self.cloud_info["cascaded_info"]["domain"]})
        except Exception as e:
            LOG.error("remove cinder service error, error: %s" % e.message)

        try:
            execute_cmd_without_stdout(
                host=self.cloud_info["cascading_info"]["external_api_ip"],
                user=constant.Cascading.ROOT,
                password=constant.Cascading.ROOT_PWD,
                cmd='cd %(dir)s; sh %(script)s %(cascaded_domain)s'
                    % {"dir": constant.RemoveConstant.REMOTE_SCRIPTS_DIR,
                       "script":
                           constant.RemoveConstant.REMOVE_NEUTRON_AGENT_SCRIPT,
                       "cascaded_domain": self.cloud_info["cascaded_info"]["domain"]})

            execute_cmd_without_stdout(
                host=self.cloud_info["cascading_info"]["external_api_ip"],
                user=constant.Cascading.ROOT,
                password=constant.Cascading.ROOT_PWD,
                cmd='cd %(dir)s; sh %(script)s %(proxy_host)s'
                    % {"dir": constant.RemoveConstant.REMOTE_SCRIPTS_DIR,
                       "script":
                           constant.RemoveConstant.REMOVE_NEUTRON_AGENT_SCRIPT,
                       "proxy_host": self.cloud_info["proxy_info"]["id"]})

        except Exception as e:
            LOG.error("remove neutron agent error, error: %s" % e.message)

        try:
            execute_cmd_without_stdout(
                host=self.cloud_info["cascading_info"]["external_api_ip"],
                user=constant.Cascading.ROOT,
                password=constant.Cascading.ROOT_PWD,
                cmd='cd %(dir)s; sh %(script)s %(cascaded_domain)s'
                    % {"dir": constant.RemoveConstant.REMOTE_SCRIPTS_DIR,
                       "script": constant.RemoveConstant.REMOVE_KEYSTONE_SCRIPT,
                       "cascaded_domain": self.cloud_info["cascaded_info"]["domain"]})
        except SSHCommandFailure:
            LOG.error("remove keystone endpoint error.")

        try:
            execute_cmd_without_stdout(
                host=self.cloud_info["cascading_info"]["external_api_ip"],
                user=constant.Cascading.ROOT,
                password=constant.Cascading.ROOT_PWD,
                cmd='cd %(dir)s; '
                    'sh %(script)s %(proxy_host_name)s %(proxy_num)s'
                    % {"dir": constant.RemoveConstant.REMOTE_SCRIPTS_DIR,
                       "script": constant.RemoveConstant.REMOVE_PROXY_SCRIPT,
                       "proxy_host_name": self.cloud_info["proxy_info"]["id"],
                       "proxy_num": self.cloud_info["proxy_info"]["proxy_num"]})
        except SSHCommandFailure:
            LOG.error("remove proxy error.")

        if self.cloud_params['project_info']['LocalMode'] == True :
            cascaded_api_ip = self.cloud_info["cascaded_info"]["public_ip"]
        else :
            cascaded_api_ip = self.cloud_info["cascaded_info"]['external_api_ip']

        address = "/%(cascaded_domain)s/%(cascaded_ip)s" \
                  % {"cascaded_domain": self.cloud_info["cascaded_info"]["domain"],
                     "cascaded_ip": cascaded_api_ip}

        try:
            execute_cmd_without_stdout(
                host=self.cloud_info["cascading_info"]["external_api_ip"],
                user=constant.Cascading.ROOT,
                password=constant.Cascading.ROOT_PWD,
                cmd='cd %(dir)s; sh %(script)s remove %(address)s'
                    % {"dir": constant.Cascading.REMOTE_SCRIPTS_DIR,
                       "script":
                           constant.PublicConstant.MODIFY_DNS_SERVER_ADDRESS,
                       "address": address})
        except SSHCommandFailure:
            LOG.error("remove dns address error.")

        # config local_vpn
        vpn_conn_name = self.cloud_info["vpn_conn_name"]
        try:
            local_vpn = VPN(self.cloud_info["cascading_vpn_info"]["public_ip"],
                            constant.VpnConstant.VPN_ROOT,
                            constant.VpnConstant.VPN_ROOT_PWD)

            local_vpn.remove_tunnel(vpn_conn_name["tunnel_conn_name"])
        except SSHCommandFailure:
            LOG.error("remove conn error.")

