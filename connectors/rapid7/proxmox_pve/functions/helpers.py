
"""
Any code that is shared between the functions in this connector
should be placed here, so that it can be reused by all functions.
"""
from logging import Logger
from typing import Generator
from r7_surcom_api import HttpSession
from furl import furl

from .sc_types import ProxmoxPVENode, ProxmoxPVEStorage, ProxmoxPVEUser, ProxmoxPVEGroup, ProxmoxPVEVM

from .sc_settings import Settings

USER_PATH = "/api2/json/access/users"
GROUP_PATH = "/api2/json/access/groups"
CLUSTER_PATH = "/api2/json/cluster/resources"
VM_PATH = "/api2/json/nodes/pve/qemu"
NODE_PATH = "/api2/json/nodes"


class ProxmoxPVEClient():

    def __init__(
        self,
        user_log: Logger,
        settings: Settings
    ):
        self.logger = user_log
        self.settings = settings

        self.base_url = settings.get("url")
        self.session = HttpSession()
        self.session.verify = settings.get("verify_tls")
        user = settings.get("user")
        realm = settings.get("realm")
        token_id = settings.get("token_id")
        token_secret = settings.get("token_secret")
        self.session.headers.update({
            "Authorization": f"PVEAPIToken={user}@{realm}!{token_id}={token_secret}",
            "Content-Type": "application/json"
        })

    def make_get_request(self, endpoint: str, q_params: dict = None) -> list:
        """Make a GET request to the Proxmox PVE API.
        Args:
            endpoint (str): The API endpoint to make the request to.
            q_params (dict, optional): A dictionary of query parameters to include in the request.
        Returns:
            list: The JSON response from the API.
        """
        url = furl(url=self.base_url).add(path=endpoint).add(query_params=q_params or {}).url
        response = self.session.get(str(url))
        response.raise_for_status()
        return response.json()

    def get_user(self, q_params: dict = None) -> Generator[ProxmoxPVEUser, None, None]:
        """Get user from the Proxmox PVE API.
        Args:
            q_params (dict): Query parameters for the request.
        Returns:
            list: A list of detailed user from proxmox PVE.
        """
        resp = self.make_get_request(endpoint=USER_PATH, q_params=q_params)
        user_resp = resp.get("data", [])
        for item in user_resp:
            user = {}
            user_id = item.get("userid")
            details = self.make_get_request(endpoint=f"{USER_PATH}/{user_id}", q_params={})
            user_data = details.get("data", {})
            user.update(item)
            user.update(user_data)
            # Remove 'expire' key if the value is 0.
            if user.get("expire", None) == 0:
                user.pop("expire", None)
            yield user

    def get_group(self, q_params: dict = None) -> Generator[ProxmoxPVEGroup, None, None]:
        """Get group from the Proxmox PVE API.
        Args:
            q_params (dict): Query parameters for the request.
        Returns:
            list: A list of group from proxmox PVE.
        """
        resp = self.make_get_request(endpoint=GROUP_PATH, q_params=q_params)
        group_resp = resp.get("data", [])
        for item in group_resp:
            group_detail = {}
            # Removing the redundant users key to avoid confusion.
            item.pop("users", None)
            group_name = item.get("groupid")
            details = self.make_get_request(endpoint=f"{GROUP_PATH}/{group_name}", q_params={})
            group_data = details.get("data", {})
            group_detail.update(item)
            group_detail.update(group_data)
            yield group_detail

    def get_vm(self, q_params: dict = None) -> Generator[ProxmoxPVEVM, None, None]:
        """Get VM from the Proxmox PVE API.
        Args:
            q_params (dict): Query parameters for the request.
        Returns:
            list: A list of cluster VM and details from proxmox PVE.
        """
        q_params.update({"type": "vm"})
        vm_resp = self.make_get_request(endpoint=CLUSTER_PATH, q_params=q_params)
        vm_data = vm_resp.get("data", [])
        for vm in vm_data:
            vm_detail = {}
            vm_id = vm.get("vmid")
            resp = self.make_get_request(endpoint=VM_PATH + f'/{vm_id}/config', q_params={})
            config_data = resp.get("data", {})
            # To get MAC addresses from the network interfaces
            net0_value = config_data.get("net0")
            mac_address = None
            if isinstance(net0_value, str) and "virtio=" in net0_value:
                mac_address = net0_value.split("virtio=")[1].split(",")[0]
            config_data.update({"mac_address": mac_address})
            vm_detail.update(config_data)
            vm_detail.update(vm)
            yield vm_detail

    def get_storage(self, q_params: dict = None) -> Generator[ProxmoxPVEStorage, None, None]:
        """Get storage from the Proxmox PVE API.
        Args:
            q_params (dict): Query parameters for the request.
        Returns:
            list: A list of storage from proxmox PVE.
        """
        q_params.update({"type": "storage"})
        storage_resp = self.make_get_request(endpoint=CLUSTER_PATH, q_params=q_params)
        storage_data = storage_resp.get("data", [])
        for item in storage_data:
            updated_storage_details = {}
            updated_storage_details.update(item)
            node_id = item.get("node")
            storage_details = self.make_get_request(endpoint=NODE_PATH + f'/{node_id}/storage', q_params={})
            detailed_data = storage_details.get("data", [])
            for storage in detailed_data:
                updated_storage_details.update(storage)
            yield updated_storage_details

    def get_nodes(self, q_params: dict = None) -> Generator[ProxmoxPVENode, None, None]:
        """Get nodes from the Proxmox PVE API.
        Args:
            q_params (dict): Query parameters for the request.
        Returns:
            list: A list of nodes from proxmox PVE.
        """
        q_params.update({"type": "node"})
        resp = self.make_get_request(endpoint=CLUSTER_PATH, q_params=q_params)
        node_data = resp.get("data", [])
        for node in node_data:
            node_details = {}
            node_details.update(node)
            # id is basically the name of the node
            node_id = node.get("node")
            summary_details = self.make_get_request(endpoint=NODE_PATH + f'/{node_id}/status', q_params={})
            summary_details_data = summary_details.get("data", {})
            node_details.update(summary_details_data)
            network_details = self.make_get_request(endpoint=NODE_PATH + f'/{node_id}/network', q_params={})
            network_details_data = network_details.get("data", {})
            node_details.update({"network": network_details_data})
            yield node_details
