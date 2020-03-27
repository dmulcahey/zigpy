import itertools
from unittest import mock

import pytest

import zigpy.device
import zigpy.endpoint
import zigpy.quirks
import zigpy.types as t
import zigpy.zcl as zcl
from zigpy.quirks.registry import DeviceRegistry
from zigpy.zcl import Cluster

ALLOWED_SIGNATURE = set(
    [
        "profile_id",
        "device_type",
        "model",
        "manufacturer",
        "input_clusters",
        "output_clusters",
    ]
)
ALLOWED_REPLACEMENT = set(["endpoints"])


def test_registry():
    class TestDevice(zigpy.quirks.CustomDevice):
        signature = {}

    assert TestDevice in zigpy.quirks._DEVICE_REGISTRY
    assert zigpy.quirks._DEVICE_REGISTRY.remove(TestDevice) is None  # :-/
    assert TestDevice not in zigpy.quirks._DEVICE_REGISTRY


@pytest.fixture
def real_device():
    application = mock.sentinel.application
    ieee = mock.sentinel.ieee
    nwk = 0x2233
    real_device = zigpy.device.Device(application, ieee, nwk)

    real_device.add_endpoint(1)
    real_device[1].profile_id = 255
    real_device[1].device_type = 255
    real_device.model = "model"
    real_device.manufacturer = "manufacturer"
    real_device[1].add_input_cluster(3)
    real_device[1].add_output_cluster(6)
    return real_device


def _dev_reg(device):
    registry = DeviceRegistry()
    registry.add_to_registry(device)
    return registry


def test_get_device_new_sig(real_device):
    class TestDevice:
        signature = {}

        def __init__(*args, **kwargs):
            pass

        def get_signature(self):
            pass

    registry = _dev_reg(TestDevice)

    assert registry.get_device(real_device) is real_device

    TestDevice.signature["endpoints"] = {1: {"profile_id": 1}}
    registry = _dev_reg(TestDevice)
    assert registry.get_device(real_device) is real_device

    TestDevice.signature["endpoints"][1]["profile_id"] = 255
    TestDevice.signature["endpoints"][1]["device_type"] = 1
    registry = _dev_reg(TestDevice)
    assert registry.get_device(real_device) is real_device

    TestDevice.signature["endpoints"][1]["device_type"] = 255
    TestDevice.signature["endpoints"][1]["input_clusters"] = [1]
    registry = _dev_reg(TestDevice)
    assert registry.get_device(real_device) is real_device

    TestDevice.signature["endpoints"][1]["input_clusters"] = [3]
    TestDevice.signature["endpoints"][1]["output_clusters"] = [1]
    registry = _dev_reg(TestDevice)
    assert registry.get_device(real_device) is real_device

    TestDevice.signature["endpoints"][1]["output_clusters"] = [6]
    TestDevice.signature["model"] = "x"
    registry = _dev_reg(TestDevice)
    assert registry.get_device(real_device) is real_device

    TestDevice.signature["model"] = "model"
    TestDevice.signature["manufacturer"] = "x"
    registry = _dev_reg(TestDevice)
    assert registry.get_device(real_device) is real_device

    TestDevice.signature["manufacturer"] = "manufacturer"
    registry = _dev_reg(TestDevice)
    assert isinstance(registry.get_device(real_device), TestDevice)


def test_get_device_old_signature(real_device):
    class TestDevice:
        signature = {}

        def __init__(*args, **kwargs):
            pass

        def get_signature(self):
            pass

    registry = DeviceRegistry()
    registry.add_to_registry(TestDevice)

    assert registry.get_device(real_device) is real_device

    TestDevice.signature[1] = {"profile_id": 1}
    assert registry.get_device(real_device) is real_device

    TestDevice.signature[1]["profile_id"] = 255
    TestDevice.signature[1]["device_type"] = 1
    assert registry.get_device(real_device) is real_device

    TestDevice.signature[1]["device_type"] = 255
    TestDevice.signature[1]["input_clusters"] = [1]
    assert registry.get_device(real_device) is real_device

    TestDevice.signature[1]["input_clusters"] = [3]
    TestDevice.signature[1]["output_clusters"] = [1]
    assert registry.get_device(real_device) is real_device

    TestDevice.signature[1]["output_clusters"] = [6]
    TestDevice.signature[1]["model"] = "x"
    assert registry.get_device(real_device) is real_device

    TestDevice.signature[1]["model"] = "model"
    TestDevice.signature[1]["manufacturer"] = "x"
    assert registry.get_device(real_device) is real_device

    TestDevice.signature[1]["manufacturer"] = "manufacturer"
    assert isinstance(registry.get_device(real_device), TestDevice)


def test_model_manuf_device_sig(real_device):
    class TestDevice:
        signature = {}

        def __init__(*args, **kwargs):
            pass

        def get_signature(self):
            pass

    registry = DeviceRegistry()
    registry.add_to_registry(TestDevice)

    assert registry.get_device(real_device) is real_device

    TestDevice.signature["endpoints"] = {
        1: {
            "profile_id": 255,
            "device_type": 255,
            "input_clusters": [3],
            "output_clusters": [6],
        }
    }

    TestDevice.signature["model"] = "x"
    assert registry.get_device(real_device) is real_device

    TestDevice.signature["model"] = "model"
    TestDevice.signature["manufacturer"] = "x"
    assert registry.get_device(real_device) is real_device

    TestDevice.signature["manufacturer"] = "manufacturer"
    assert isinstance(registry.get_device(real_device), TestDevice)


def test_custom_devices():
    def _check_range(cluster):
        for range in Cluster._registry_range.keys():
            if range[0] <= cluster <= range[1]:
                return True
        return False

    # Validate that all CustomDevices look sane
    reg = zigpy.quirks._DEVICE_REGISTRY.registry
    return
    candidates = list(
        itertools.chain(*itertools.chain(*[m.values() for m in reg.values()]))
    )

    for device in candidates:
        # enforce new style of signature
        assert "endpoints" in device.signature
        numeric = [eid for eid in device.signature if isinstance(eid, int)]
        assert not numeric

        # Check that the signature data is OK
        signature = device.signature["endpoints"]
        for profile_id, profile_data in signature.items():
            assert isinstance(profile_id, int)
            assert set(profile_data.keys()) - ALLOWED_SIGNATURE == set()

        # Check that the replacement data is OK
        assert set(device.replacement.keys()) - ALLOWED_REPLACEMENT == set()
        for epid, epdata in device.replacement.get("endpoints", {}).items():
            assert (epid in signature) or (
                "profile" in epdata and "device_type" in epdata
            )
            if "profile" in epdata:
                profile = epdata["profile"]
                assert isinstance(profile, int) and 0 <= profile <= 0xFFFF
            if "device_type" in epdata:
                device_type = epdata["device_type"]
                assert isinstance(device_type, int) and 0 <= device_type <= 0xFFFF

            all_clusters = epdata.get("input_clusters", []) + epdata.get(
                "output_clusters", []
            )
            for cluster in all_clusters:
                assert (
                    (isinstance(cluster, int) and cluster in Cluster._registry)
                    or (isinstance(cluster, int) and _check_range(cluster))
                    or issubclass(cluster, Cluster)
                )


def test_custom_device():
    class Device(zigpy.quirks.CustomDevice):
        signature = {}

        class MyEndpoint:
            def __init__(self, device, endpoint_id, *args, **kwargs):
                assert args == (mock.sentinel.custom_endpoint_arg, replaces)

        class MyCluster(zigpy.quirks.CustomCluster):
            cluster_id = 0x8888

        replacement = {
            "endpoints": {
                1: {
                    "profile_id": mock.sentinel.profile_id,
                    "input_clusters": [0x0000, MyCluster],
                    "output_clusters": [0x0001, MyCluster],
                },
                2: (MyEndpoint, mock.sentinel.custom_endpoint_arg),
            },
            "model": "Mock Model",
            "manufacturer": "Mock Manufacturer",
        }

    class Device2(zigpy.quirks.CustomDevice):
        signature = {}

        class MyEndpoint:
            def __init__(self, device, endpoint_id, *args, **kwargs):
                assert args == (mock.sentinel.custom_endpoint_arg, replaces)

        class MyCluster(zigpy.quirks.CustomCluster):
            cluster_id = 0x8888

        replacement = {
            "endpoints": {
                1: {
                    "profile_id": mock.sentinel.profile_id,
                    "input_clusters": [0x0000, MyCluster],
                    "output_clusters": [0x0001, MyCluster],
                },
                2: (MyEndpoint, mock.sentinel.custom_endpoint_arg),
            },
            "model": "Mock Model",
            "manufacturer": "Mock Manufacturer",
            "skip_configuration": True,
        }

    assert 0x8888 not in Cluster._registry

    replaces = mock.MagicMock()
    replaces[1].device_type = mock.sentinel.device_type
    test_device = Device(None, None, 0x4455, replaces)
    test_device2 = Device2(None, None, 0x4455, replaces)

    assert test_device2.skip_configuration is True

    assert test_device.manufacturer == "Mock Manufacturer"
    assert test_device.model == "Mock Model"
    assert test_device.skip_configuration is False

    assert test_device[1].profile_id == mock.sentinel.profile_id
    assert test_device[1].device_type == mock.sentinel.device_type

    assert 0x0000 in test_device[1].in_clusters
    assert 0x8888 in test_device[1].in_clusters
    assert isinstance(test_device[1].in_clusters[0x8888], Device.MyCluster)

    assert 0x0001 in test_device[1].out_clusters
    assert 0x8888 in test_device[1].out_clusters
    assert isinstance(test_device[1].out_clusters[0x8888], Device.MyCluster)

    assert isinstance(test_device[2], Device.MyEndpoint)

    test_device.add_endpoint(3)
    assert isinstance(test_device[3], zigpy.endpoint.Endpoint)

    assert zigpy.quirks._DEVICE_REGISTRY.remove(Device) is None  # :-/
    assert Device not in zigpy.quirks._DEVICE_REGISTRY


def test_custom_cluster_idx():
    class TestClusterIdx(zigpy.quirks.CustomCluster):
        cluster_id = 0x1234
        attributes = {
            0x0000: ("first_attribute", t.uint8_t),
            0x00FF: ("2nd_attribute", t.enum8),
        }
        server_commands = {
            0x00: ("server_cmd_0", (t.uint8_t, t.uint8_t), False),
            0x01: ("server_cmd_2", (t.uint8_t, t.uint8_t), False),
        }
        client_commands = {
            0x00: ("client_cmd_0", (t.uint8_t,), True),
            0x01: ("client_cmd_1", (t.uint8_t,), True),
        }

    def _test_cmd(cmd_set, cmd_set_idx):
        assert hasattr(TestClusterIdx, cmd_set_idx)
        idx_len = len(getattr(TestClusterIdx, cmd_set_idx))
        cmd_set_len = len(getattr(TestClusterIdx, cmd_set))
        assert idx_len == cmd_set_len
        for cmd_name, cmd_id in getattr(TestClusterIdx, cmd_set_idx).items():
            assert getattr(TestClusterIdx, cmd_set)[cmd_id][0] == cmd_name

    assert hasattr(TestClusterIdx, "attridx")
    attr_idx_len = len(TestClusterIdx.attridx)
    attrs_len = len(TestClusterIdx.attributes)
    assert attr_idx_len == attrs_len
    for attr_name, attr_id in TestClusterIdx.attridx.items():
        assert TestClusterIdx.attributes[attr_id][0] == attr_name

    _test_cmd("server_commands", "_server_command_idx")
    _test_cmd("client_commands", "_client_command_idx")


async def test_read_attributes_uncached():
    class TestCluster(zigpy.quirks.CustomCluster):
        cluster_id = 0x1234
        _CONSTANT_ATTRIBUTES = {0x0001: 5}
        attributes = {
            0x0000: ("first_attribute", t.uint8_t),
            0x0001: ("2nd_attribute", t.uint8_t),
            0x0002: ("3rd_attribute", t.uint8_t),
            0x0003: ("4th_attribute", t.enum8),
        }
        server_commands = {
            0x00: ("server_cmd_0", (t.uint8_t, t.uint8_t), False),
            0x01: ("server_cmd_2", (t.uint8_t, t.uint8_t), False),
        }
        client_commands = {
            0x00: ("client_cmd_0", (t.uint8_t,), True),
            0x01: ("client_cmd_1", (t.uint8_t,), True),
        }

    class TestCluster2(zigpy.quirks.CustomCluster):
        cluster_id = 0x1235
        attributes = {0x0000: ("first_attribute", t.uint8_t)}
        server_commands = {}
        client_commands = {}

    epmock = mock.MagicMock()
    epmock._device.application.get_sequence.return_value = 123
    epmock.device.application.get_sequence.return_value = 123
    cluster = TestCluster(epmock, True)
    cluster2 = TestCluster2(epmock, True)

    async def mockrequest(
        foundation, command, schema, args, manufacturer=None, **kwargs
    ):
        assert foundation is True
        assert command == 0
        rar0 = _mk_rar(0, 99)
        rar99 = _mk_rar(2, None, 1)
        rar199 = _mk_rar(3, 199)
        return [[rar0, rar99, rar199]]

    cluster.request = mockrequest
    cluster2.request = mockrequest
    # test no constants
    success, failure = await cluster.read_attributes([0, 2, 3])
    assert success[0] == 99
    assert failure[2] == 1
    assert success[3] == 199

    # test mixed response with constant
    success, failure = await cluster.read_attributes([0, 1, 2, 3])
    assert success[0] == 99
    assert success[1] == 5
    assert failure[2] == 1
    assert success[3] == 199

    # test just constant attr
    success, failure = await cluster.read_attributes([1])
    assert success[1] == 5

    # test just constant attr
    success, failure = await cluster2.read_attributes([0, 2, 3])
    assert success[0] == 99
    assert failure[2] == 1
    assert success[3] == 199


async def test_read_attributes_default_response():
    class TestCluster(zigpy.quirks.CustomCluster):
        cluster_id = 0x1234
        _CONSTANT_ATTRIBUTES = {0x0001: 5}
        attributes = {
            0x0000: ("first_attribute", t.uint8_t),
            0x0001: ("2nd_attribute", t.uint8_t),
            0x0002: ("3rd_attribute", t.uint8_t),
            0x0003: ("4th_attribute", t.enum8),
        }
        server_commands = {
            0x00: ("server_cmd_0", (t.uint8_t, t.uint8_t), False),
            0x01: ("server_cmd_2", (t.uint8_t, t.uint8_t), False),
        }
        client_commands = {
            0x00: ("client_cmd_0", (t.uint8_t,), True),
            0x01: ("client_cmd_1", (t.uint8_t,), True),
        }

    epmock = mock.MagicMock()
    epmock._device.application.get_sequence.return_value = 123
    epmock.device.application.get_sequence.return_value = 123
    cluster = TestCluster(epmock, True)

    async def mockrequest(
        foundation, command, schema, args, manufacturer=None, **kwargs
    ):
        assert foundation is True
        assert command == 0
        return [0xC1]

    cluster.request = mockrequest
    # test constants with errors
    success, failure = await cluster.read_attributes([0, 1, 2, 3], allow_cache=False)
    assert success == {1: 5}
    assert failure == {0: 0xC1, 2: 0xC1, 3: 0xC1}


def _mk_rar(attrid, value, status=0):
    r = zcl.foundation.ReadAttributeRecord()
    r.attrid = attrid
    r.status = status
    r.value = zcl.foundation.TypeValue()
    r.value.value = value
    return r
