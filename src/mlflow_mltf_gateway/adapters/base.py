"""
BackendAdapter and implementations for REST and Local adapters.
"""

from abc import abstractmethod


class BackendAdapter:
    """
    Base class for connections between the client and backend.
    """

    # Note that the tarball can be deleted by the caller so we need to save it somewhere before returning
    @abstractmethod
    def enqueue_run(
        self,
        run_id,
        project_tarball,
        entry_point,
        params,
        backend_config,
        tracking_uri,
        experiment_id,
    ):
        raise NotImplementedError()

    CONFIG_NAMES = {"tracking_uri": "URI of tracking server"}

    def get_config(self) -> dict:
        """
        We'd like to be able to just have the user set a URI for the gateway
        and then have any other necessary config be provided from there instead
        of having the user set (and sync) those values. This endpoint will
        dump back a dict with things like the tracking server URI
        :return: Dict with configuration. Should have keys listed in
        """
        raise NotImplementedError()

    @abstractmethod
    def list(self, list_all):
        """
        List jobs this backend knows about
        :param list_all: if true, list completed/deleted jobs, otherwise just active
        :return: list of GatewaySubmittedRun
        """
        raise NotImplementedError()

    @abstractmethod
    def wait(self, run_id):
        raise NotImplementedError()

    @abstractmethod
    def get_status(self, run_id):
        raise NotImplementedError()

    @abstractmethod
    def get_tracking_server(self):
        raise NotImplementedError()

    @abstractmethod
    def show_details(self, run_id, show_logs):
        raise NotImplementedError()

    @abstractmethod
    def delete(self, run_id):
        raise NotImplementedError()
