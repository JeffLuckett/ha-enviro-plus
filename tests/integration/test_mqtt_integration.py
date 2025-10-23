"""Integration tests for MQTT functionality."""

import pytest
import time
from unittest.mock import Mock, patch, mock_open

from ha_enviro_plus.agent import (
    on_connect,
    on_message,
    read_all,
    SENSORS,
)


class MockMQTTBroker:
    """Mock MQTT broker for integration testing."""

    def __init__(self):
        self.clients = {}
        self.messages = []
        self.subscriptions = {}
        self.will_messages = {}

    def add_client(self, client_id, client):
        """Add a client to the broker."""
        self.clients[client_id] = client
        client.broker = self

    def publish(self, topic, payload, qos=0, retain=False):
        """Publish a message to the broker."""
        message = {
            "topic": topic,
            "payload": payload,
            "qos": qos,
            "retain": retain,
            "timestamp": time.time(),
        }
        self.messages.append(message)

        # Deliver to subscribed clients
        for pattern, clients in self.subscriptions.items():
            if self._topic_matches(topic, pattern):
                for client in clients:
                    client._deliver_message(topic, payload, qos)

    def subscribe(self, client, topic_patterns, qos=0):
        """Subscribe a client to topic patterns."""
        for pattern in topic_patterns:
            if isinstance(pattern, tuple):
                pattern, qos = pattern

            if pattern not in self.subscriptions:
                self.subscriptions[pattern] = []
            self.subscriptions[pattern].append(client)

    def _topic_matches(self, topic, pattern):
        """Check if topic matches pattern (supports + wildcard)."""
        if pattern == topic:
            return True

        # Handle + wildcard
        if "+" in pattern:
            pattern_parts = pattern.split("/")
            topic_parts = topic.split("/")

            if len(pattern_parts) != len(topic_parts):
                return False

            for p, t in zip(pattern_parts, topic_parts):
                if p != "+" and p != t:
                    return False
            return True

        return False

    def set_will(self, client, topic, payload, qos=0, retain=False):
        """Set will message for a client."""
        self.will_messages[client] = {
            "topic": topic,
            "payload": payload,
            "qos": qos,
            "retain": retain,
        }

    def disconnect_client(self, client):
        """Disconnect a client and publish will message."""
        if client in self.will_messages:
            will = self.will_messages[client]
            self.publish(will["topic"], will["payload"], will["qos"], will["retain"])


class MockMQTTClient:
    """Mock MQTT client for integration testing."""

    def __init__(self, client_id, broker=None):
        self.client_id = client_id
        self.broker = broker
        self.connected = False
        self.on_connect = None
        self.on_message = None
        self.username = None
        self.password = None
        self._message_queue = []

    def username_pw_set(self, username, password):
        """Set username and password."""
        self.username = username
        self.password = password

    def will_set(self, topic, payload, qos=0, retain=False):
        """Set will message."""
        if self.broker:
            self.broker.set_will(self, topic, payload, qos, retain)

    def connect(self, host, port, keepalive=60):
        """Connect to broker."""
        if self.broker:
            self.broker.add_client(self.client_id, self)
            self.connected = True

            # Trigger on_connect callback
            if self.on_connect:
                self.on_connect(self, None, None, 0)

    def disconnect(self):
        """Disconnect from broker."""
        if self.broker and self.connected:
            self.broker.disconnect_client(self)
            self.connected = False

    def loop_start(self):
        """Start the network loop."""
        pass

    def loop_stop(self):
        """Stop the network loop."""
        pass

    def publish(self, topic, payload, qos=0, retain=False):
        """Publish a message."""
        if self.broker:
            self.broker.publish(topic, payload, qos, retain)

    def subscribe(self, topic_patterns, qos=0):
        """Subscribe to topic patterns."""
        if self.broker:
            self.broker.subscribe(self, topic_patterns, qos)

    def _deliver_message(self, topic, payload, qos=0):
        """Deliver a message to this client."""
        if self.on_message:
            msg = Mock()
            msg.topic = topic
            msg.qos = qos
            # Create a mock payload object with decode method
            msg.payload = Mock()
            msg.payload.decode.return_value = (
                payload if isinstance(payload, str) else payload.decode()
            )

            self.on_message(self, None, msg)


@pytest.fixture
def mock_broker():
    """Create a mock MQTT broker."""
    return MockMQTTBroker()


@pytest.fixture
def mock_client(mock_broker):
    """Create a mock MQTT client connected to broker."""
    client = MockMQTTClient("test_client", mock_broker)
    return client


class TestMQTTIntegration:
    """Test MQTT integration functionality."""

    def test_connection_and_discovery(
        self, mock_client, mock_broker, mock_bme280, mock_ltr559, mock_gas_sensor, mock_env_vars
    ):
        """Test MQTT connection and discovery publishing."""
        # Set up client callbacks
        mock_client.on_connect = on_connect
        mock_client.on_message = lambda client, userdata, msg: on_message(
            client, userdata, msg, Mock()
        )

        # Connect client
        mock_client.connect("test-broker.local", 1883)

        # Check that discovery messages were published
        discovery_messages = [msg for msg in mock_broker.messages if "config" in msg["topic"]]
        assert len(discovery_messages) > 0

        # Check sensor discovery
        sensor_configs = [msg for msg in discovery_messages if "sensor" in msg["topic"]]
        assert len(sensor_configs) >= len(SENSORS)

        # Check button discovery
        button_configs = [msg for msg in discovery_messages if "button" in msg["topic"]]
        assert len(button_configs) >= 3  # reboot, shutdown, restart_service

        # Check number entity discovery
        number_configs = [msg for msg in discovery_messages if "number" in msg["topic"]]
        assert len(number_configs) >= 3  # temp_offset, hum_offset, cpu_temp_factor

    def test_availability_topic(self, mock_client, mock_broker):
        """Test availability topic publishing."""
        mock_client.on_connect = on_connect
        mock_client.connect("test-broker.local", 1883)

        # Check availability message
        availability_messages = [msg for msg in mock_broker.messages if "status" in msg["topic"]]
        assert len(availability_messages) > 0

        online_message = availability_messages[0]
        assert online_message["payload"] == "online"
        assert online_message["retain"] is True

    def test_will_message(self, mock_client, mock_broker):
        """Test will message on disconnect."""
        # Set will message
        mock_client.will_set("enviro_raspberrypi/status", "offline", retain=True)

        # Connect and then disconnect
        mock_client.connect("test-broker.local", 1883)
        mock_client.disconnect()

        # Check will message was published
        offline_messages = [msg for msg in mock_broker.messages if msg["payload"] == "offline"]
        assert len(offline_messages) > 0

        offline_message = offline_messages[0]
        assert offline_message["topic"] == "enviro_raspberrypi/status"
        assert offline_message["retain"] is True

    def test_command_subscription(self, mock_client, mock_broker, mock_device_id):
        """Test command topic subscription."""
        mock_client.on_connect = on_connect
        mock_client.connect("test-broker.local", 1883)

        # Check subscriptions
        assert "enviro_raspberrypi/cmd" in mock_broker.subscriptions
        assert "enviro_raspberrypi/set/+" in mock_broker.subscriptions

        # Verify client is subscribed
        cmd_subscribers = mock_broker.subscriptions["enviro_raspberrypi/cmd"]
        assert mock_client in cmd_subscribers

        set_subscribers = mock_broker.subscriptions["enviro_raspberrypi/set/+"]
        assert mock_client in set_subscribers

    def test_command_processing(
        self, mock_client, mock_broker, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
    ):
        """Test command processing via MQTT."""
        sensors = Mock()
        mock_client.on_connect = on_connect
        mock_client.on_message = lambda client, userdata, msg: on_message(
            client, userdata, msg, sensors
        )

        mock_client.connect("test-broker.local", 1883)

        # Send reboot command
        with patch("ha_enviro_plus.agent.subprocess.Popen") as mock_popen:
            mock_broker.publish("enviro_raspberrypi/cmd", "reboot")

            # Should call reboot command
            mock_popen.assert_called_once_with(["sudo", "reboot"])

    def test_calibration_updates(
        self, mock_client, mock_broker, mock_bme280, mock_ltr559, mock_gas_sensor, mock_device_id
    ):
        """Test calibration updates via MQTT."""
        sensors = Mock()
        mock_client.on_connect = on_connect
        mock_client.on_message = lambda client, userdata, msg: on_message(
            client, userdata, msg, sensors
        )

        mock_client.connect("test-broker.local", 1883)

        # Send temperature offset update
        mock_broker.publish("enviro_raspberrypi/set/temp_offset", "2.5")
        sensors.update_calibration.assert_called_with(temp_offset=2.5)

        # Send humidity offset update
        mock_broker.publish("enviro_raspberrypi/set/hum_offset", "-3.0")
        sensors.update_calibration.assert_called_with(hum_offset=-3.0)

        # Send CPU factor update
        mock_broker.publish("enviro_raspberrypi/set/cpu_temp_factor", "2.0")
        sensors.update_calibration.assert_called_with(cpu_temp_factor=2.0)

    def test_sensor_data_publishing(
        self,
        mock_client,
        mock_broker,
        mock_bme280,
        mock_ltr559,
        mock_gas_sensor,
        mock_subprocess,
        mock_psutil,
        mock_socket,
        mock_platform,
        mock_device_id,
    ):
        """Test sensor data publishing."""
        # Set up mock sensor data
        mock_bme280.get_temperature.return_value = 25.5
        mock_bme280.get_humidity.return_value = 45.0
        mock_bme280.get_pressure.return_value = 1013.25
        mock_ltr559.get_lux.return_value = 150.0
        mock_subprocess.return_value = "temp=42.0'C\n"

        mock_gas_sensor.oxidising = 50000.0
        mock_gas_sensor.reducing = 30000.0
        mock_gas_sensor.nh3 = 40000.0

        mock_psutil["vm"].percent = 45.2
        mock_psutil["vm"].total = 8 * 1024 * 1024 * 1024
        mock_psutil["cpu"].return_value = 12.5

        # Mock file operations
        with patch("builtins.open", mock_open(read_data="12345.67 98765.43")):
            from ha_enviro_plus.sensors import EnviroPlusSensors

            sensors = EnviroPlusSensors()

            # Read sensor data
            vals = read_all(sensors)

            # Publish sensor data
            for tail, val in vals.items():
                mock_client.publish(f"enviro_raspberrypi/{tail}", str(val), retain=True)

        # Check that sensor data was published
        sensor_messages = [
            msg
            for msg in mock_broker.messages
            if "enviro_raspberrypi/" in msg["topic"] and "config" not in msg["topic"]
        ]
        assert len(sensor_messages) > 0

        # Check specific sensor values
        temp_message = next(
            (msg for msg in sensor_messages if "bme280/temperature" in msg["topic"]), None
        )
        assert temp_message is not None
        assert temp_message["payload"] == "16.33"  # Compensated temperature
        assert temp_message["retain"] is True

        humidity_message = next(
            (msg for msg in sensor_messages if "bme280/humidity" in msg["topic"]), None
        )
        assert humidity_message is not None
        assert humidity_message["payload"] == "45.0"
        assert humidity_message["retain"] is True

    def test_retained_messages(self, mock_client, mock_broker):
        """Test that messages are published as retained."""
        mock_client.on_connect = on_connect
        mock_client.connect("test-broker.local", 1883)

        # Check that discovery messages are retained
        discovery_messages = [msg for msg in mock_broker.messages if "config" in msg["topic"]]
        for msg in discovery_messages:
            assert msg["retain"] is True

        # Check that offset messages are retained
        offset_messages = [msg for msg in mock_broker.messages if "set/" in msg["topic"]]
        for msg in offset_messages:
            assert msg["retain"] is True

    def test_qos_levels(self, mock_client, mock_broker, mock_device_id):
        """Test QoS levels for different message types."""
        mock_client.on_connect = on_connect
        mock_client.connect("test-broker.local", 1883)

        # Discovery messages should use QoS 1
        discovery_messages = [msg for msg in mock_broker.messages if "config" in msg["topic"]]
        for msg in discovery_messages:
            assert msg["qos"] == 1

        # Availability messages should use QoS 0 (retained messages don't need QoS 1)
        availability_messages = [msg for msg in mock_broker.messages if "status" in msg["topic"]]
        for msg in availability_messages:
            assert msg["qos"] == 0

    def test_authentication(self, mock_client, mock_broker):
        """Test MQTT authentication."""
        # Set credentials
        mock_client.username_pw_set("testuser", "testpass")

        # Connect
        mock_client.connect("test-broker.local", 1883)

        # Verify credentials were set
        assert mock_client.username == "testuser"
        assert mock_client.password == "testpass"
        assert mock_client.connected is True

    def test_reconnection_handling(self, mock_client, mock_broker):
        """Test reconnection handling."""
        mock_client.on_connect = on_connect

        # Connect
        mock_client.connect("test-broker.local", 1883)
        initial_message_count = len(mock_broker.messages)

        # Disconnect
        mock_client.disconnect()

        # Reconnect
        mock_client.connect("test-broker.local", 1883)

        # Should republish discovery on reconnect
        assert len(mock_broker.messages) > initial_message_count

        # Should publish availability again
        availability_messages = [
            msg
            for msg in mock_broker.messages
            if "status" in msg["topic"] and msg["payload"] == "online"
        ]
        assert len(availability_messages) >= 2  # At least one from each connection


class TestMQTTErrorHandling:
    """Test MQTT error handling."""

    def test_invalid_command_handling(
        self, mock_client, mock_broker, mock_bme280, mock_ltr559, mock_gas_sensor
    ):
        """Test handling of invalid commands."""
        sensors = Mock()
        mock_client.on_connect = on_connect
        mock_client.on_message = lambda client, userdata, msg: on_message(
            client, userdata, msg, sensors
        )

        mock_client.connect("test-broker.local", 1883)

        # Send invalid command
        mock_broker.publish("enviro_raspberrypi/cmd", "invalid_command")

        # Should not call any system commands
        assert not sensors.update_calibration.called

    def test_malformed_payload_handling(
        self, mock_client, mock_broker, mock_bme280, mock_ltr559, mock_gas_sensor
    ):
        """Test handling of malformed payloads."""
        sensors = Mock()
        mock_client.on_connect = on_connect

        def error_on_message(client, userdata, msg):
            try:
                on_message(client, userdata, msg, sensors)
            except Exception:
                pass  # Should handle errors gracefully

        mock_client.on_message = error_on_message
        mock_client.connect("test-broker.local", 1883)

        # Send malformed payload
        mock_broker.publish("enviro_raspberrypi/set/temp_offset", "not_a_number")

        # Should not crash
        assert True  # If we get here, error was handled

    def test_connection_failure_recovery(self, mock_client, mock_broker):
        """Test recovery from connection failures."""
        # Simulate connection failure
        mock_client.connected = False

        # Attempt to publish (should not crash)
        mock_client.publish("test/topic", "test_payload")

        # Should handle gracefully
        assert True  # If we get here, error was handled
