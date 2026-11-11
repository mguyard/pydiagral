"""Verify Topaze reads preserve identities and never manufacture safe states."""

from copy import deepcopy

import pytest

from pydiagral.exceptions import ModelValidationError
from pydiagral.topaze_models import build_configuration, normalize_status


@pytest.fixture
def source_data():
    """Use synthetic identifiers and a non-default exit delay."""
    return (
        {
            "centralLearningZone": {
                "centralInformation": {"radioId": "RADIO123", "customLabel": "Central"},
                "groupNames": {"1": "Doors", "2": "Inside"},
                "sensors": [
                    {
                        "index": 3,
                        "customLabel": "Window",
                        "radioId": "000042",
                        "refCode": "9057",
                        "affectedToZone": 1,
                        "type": 2,
                        "subType": 4,
                        "radioAlert": True,
                    }
                ],
                "commands": [{"index": 1, "customLabel": "Keypad"}],
                "alarms": [{"index": 1, "customLabel": "Siren"}],
                "transmitters": [{"index": 2, "customLabel": "Transmitter"}],
                "transceivers": [{"index": 1, "customLabel": "Relay"}],
            },
            "centralSettingsZone": {
                "nbGroups": 2,
                "inputDelays": {"1": 10, "2": 20},
                "outputDelays": {"1": 45, "2": 120},
                "groupesMarchePresence": {"1": True, "2": False},
                "groupesMarchePartielle1": {"1": False, "2": True},
                "groupesMarchePartielle2": {"1": True, "2": True},
            },
            "factoryZone": {"versions": {"central": "6.3.2", "centralRadio": "1.2.3"}},
            "boxVideoZone": {
                "cameras": [
                    {"index": 1, "name": "Camera", "password": "never-copy-this"}
                ]
            },
        },
        {"centralId": "001234", "transmitterId": "000999", "name": "Test home"},
        {"versions": {"box": "5.0.0", "boxRadio": "2.0.0"}},
    )


class TestConfigurationMapping:
    """Keep the central identity, device names and configured timing intact."""

    def test_preserves_identity_groups_timing_and_inventory(self, source_data):
        """The transmitter must never replace the existing central identifier."""
        config = build_configuration(*source_data)

        assert config.alarm.central.serial == "001234"
        assert config.alarm.box.serial == "000999"
        assert config.alarm.name == "Test home"
        assert config.alarm.central.firmwares.central == "6.3.2"
        assert config.alarm.central.firmwares.centralradio == "1.2.3"
        assert config.alarm.box.firmwares.boxradio == "2.0.0"
        assert [
            (group.index, group.name, group.output_delay) for group in config.groups
        ] == [
            (1, "Doors", 45),
            (2, "Inside", 120),
        ]
        assert config.groups[0].input_delay == 10
        assert config.presence_group == [1]
        assert config.partial_group1 == [2]
        assert config.partial_group2 == [1, 2]
        assert config.sensors[0].index == 3
        assert config.sensors[0].label == "Window"
        assert config.sensors[0].serial == "000042"
        assert config.sensors[0].group == 1
        assert config.sensors[0].subtype == 4
        assert config.commands[0].label == "Keypad"
        assert config.sirens[0].label == "Siren"
        assert config.transmitters[0].label == "Transmitter"
        assert config.transceivers[0].label == "Relay"
        assert config.cameras[0].label == "Camera"

    def test_does_not_copy_secrets_or_invent_anomaly_state(self, source_data):
        """Only proven configuration fields enter Home Assistant models."""
        config = build_configuration(*source_data)

        assert "never-copy-this" not in repr(config)
        assert config.sensors[0].anomalies is None
        assert config.central_information.anomalies is None
        assert config.reading_date is None

    def test_does_not_mutate_input(self, source_data):
        """The caller can retain its raw inventory without conversion side effects."""
        original = deepcopy(source_data)
        build_configuration(*source_data)
        assert source_data == original

    @pytest.mark.parametrize("central_id", [None, 1234, ""])
    def test_rejects_invalid_central_identity(self, source_data, central_id):
        """A changed identity would silently create replacement HA entities."""
        source_data[1]["centralId"] = central_id
        with pytest.raises(ModelValidationError):
            build_configuration(*source_data)

    @pytest.mark.parametrize("count", [0, -1, True, "2", None])
    def test_rejects_invalid_group_count(self, source_data, count):
        """A missing topology cannot safely describe group states."""
        source_data[0]["centralSettingsZone"]["nbGroups"] = count
        with pytest.raises(ModelValidationError):
            build_configuration(*source_data)

    def test_rejects_missing_configured_group(self, source_data):
        """Do not fill absent groups with fabricated labels or timing."""
        del source_data[0]["centralLearningZone"]["groupNames"]["2"]
        with pytest.raises(ModelValidationError):
            build_configuration(*source_data)

    def test_missing_delay_stays_unknown(self, source_data):
        """An absent setting does not imply immediate arming."""
        del source_data[0]["centralSettingsZone"]["outputDelays"]["2"]
        config = build_configuration(*source_data)
        assert config.groups[1].output_delay is None

    @pytest.mark.parametrize("delay", [-1, True, "90"])
    def test_rejects_malformed_delay(self, source_data, delay):
        """Timing must retain its explicit numeric meaning."""
        source_data[0]["centralSettingsZone"]["outputDelays"]["2"] = delay
        with pytest.raises(ModelValidationError):
            build_configuration(*source_data)

    def test_rejects_duplicate_device_indexes(self, source_data):
        """Duplicate indexes would attach anomaly details to the wrong device."""
        sensor = source_data[0]["centralLearningZone"]["sensors"][0]
        source_data[0]["centralLearningZone"]["sensors"].append(dict(sensor))
        with pytest.raises(ModelValidationError):
            build_configuration(*source_data)


class TestStatusMapping:
    """Only validated live status can make the alarm available."""

    @pytest.mark.parametrize(
        ("state", "groups", "expected"),
        [
            ("off", [], "off"),
            ("on", [1, 2], "group"),
            ("group", [2], "group"),
            ("tempogroup", [], "tempo_group"),
            ("presence", [1], "presence"),
        ],
    )
    def test_maps_known_states_and_preserves_groups(
        self, source_data, state, groups, expected
    ):
        """The legacy all-armed value is translated without expanding its groups."""
        config = build_configuration(*source_data)
        result = normalize_status(
            {"systemState": state, "groups": groups, "commandStatus": "CMD_OK"}, config
        )
        assert result.status == expected
        assert result.activated_groups == groups
        assert result.activated_groups is not groups

    @pytest.mark.parametrize(
        "payload",
        [
            {},
            {"systemState": "unknown", "groups": []},
            {"systemState": "on", "groups": []},
            {"systemState": "group", "groups": []},
            {"systemState": "off", "groups": [1]},
            {"systemState": "group", "groups": [3]},
            {"systemState": "group", "groups": [True]},
            {"systemState": "group", "groups": ["1"]},
            {"systemState": "group", "groups": [1, 1]},
            {"systemState": "off", "groups": None},
            {"systemState": "off", "groups": [], "commandStatus": "CMD_FAILED"},
        ],
    )
    def test_rejects_unusable_status(self, source_data, payload):
        """Never report disarmed or armed from malformed or failed responses."""
        config = build_configuration(*source_data)
        with pytest.raises(ModelValidationError):
            normalize_status(payload, config)


@pytest.mark.parametrize(
    "selection", [{"group": True}, {"1": "true"}, {"3": True}, {"1": True, "01": True}]
)
def test_invalid_group_selection_is_rejected(source_data, selection):
    """Presence configuration cannot select unknown, duplicate or malformed groups."""
    source_data[0]["centralSettingsZone"]["groupesMarchePresence"] = selection
    with pytest.raises(ModelValidationError):
        build_configuration(*source_data)


def test_device_collection_must_be_a_list(source_data):
    """A dictionary cannot be mistaken for a list of declared equipment."""
    source_data[0]["centralLearningZone"]["sensors"] = {}
    with pytest.raises(ModelValidationError, match="device list"):
        build_configuration(*source_data)
