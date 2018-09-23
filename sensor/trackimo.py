"""
@ Author      : Troy Kelly
@ Date        : 23 Sept 2018
@ Description : Trackimo Sensor - Queries the Trackimo API and retrieves
                data at a specified interval for retransmission via MQTT

@ Notes:        This file needs to be within your custom_components folder.
                eg "/config/custom_components/sensor"
"""

REQUIREMENTS = ['trackimo==0.0.10']
DEPENDENCIES = ['mqtt']

from datetime import timedelta
import logging
import subprocess
import json
import urllib
import requests
import asyncio
import time
import re

import voluptuous as vol
import homeassistant.components.mqtt as mqtt

from homeassistant.components.mqtt import (
    CONF_STATE_TOPIC, CONF_COMMAND_TOPIC, CONF_QOS, CONF_RETAIN)
from homeassistant.helpers import template
from homeassistant.exceptions import TemplateError
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (
    CONF_NAME, CONF_VALUE_TEMPLATE, CONF_UNIT_OF_MEASUREMENT,
    STATE_UNKNOWN)
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = 'Trackimo Sensor'
CONST_MQTT_TOPIC = "mqtt_topic"
CONST_STATE_ERROR = "error"
CONST_STATE_RUNNING = "running"
CONST_STATE_SLEEPING = "sleep"
CONST_USERNAME = "username"
CONST_PASSWORD = "password"

SCAN_INTERVAL = timedelta(seconds=60)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONST_USERNAME): cv.string,
    vol.Required(CONST_PASSWORD): cv.string,
    vol.Required(CONST_MQTT_TOPIC): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_UNIT_OF_MEASUREMENT): cv.string,
    vol.Optional(CONF_VALUE_TEMPLATE): cv.template,
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Trackimo Sensor."""
    name = config.get(CONF_NAME)
    username = config.get(CONST_USERNAME)
    password = config.get(CONST_PASSWORD)
    mqtt_topic = config.get(CONST_MQTT_TOPIC)

    unit = config.get(CONF_UNIT_OF_MEASUREMENT)
    value_template = config.get(CONF_VALUE_TEMPLATE)
    if value_template is not None:
        value_template.hass = hass

    _LOGGER.warning("Creating trackimo data and device")

    data = TrackimoSensorData(username, password, mqtt_topic, hass)

    add_devices([TrackimoSensor(hass, data, name, unit, value_template)])


class OwntracksMQTT():
    def __init__(self):
        self.t = 'p'
        self.tst = time.time()
        self.acc = None
        self._type = 'location'
        self.alt = 0
        self._cp = False
        self.lon = None
        self.lat = None
        self.batt = 0
        self.conn = 'o'
        self.vel = 0

    def json(self):
        return json.dumps(self.__dict__)


class TrackimoSensor(Entity):
    """Representation of a sensor."""

    def __init__(self, hass, data, name, unit_of_measurement, value_template):
        """Initialize the sensor."""
        self._hass = hass
        self.data = data
        self._name = name
        self._state = STATE_UNKNOWN
        self._unit_of_measurement = unit_of_measurement
        self._value_template = value_template
        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def state(self):
        """Return the state of the device."""
        return self._state

    def update(self):
        """Get the latest data and updates the state."""
        _LOGGER.warning("Updating trackimo sensor")
        self.data.update()
        value = self.data.value

        if value is None:
            value = STATE_UNKNOWN
        elif self._value_template is not None:
            self._state = self._value_template.render_with_possible_json_value(
                value, STATE_UNKNOWN)
        else:
            self._state = value


class TrackimoSensorData(object):
    """The class for handling the data retrieval."""

    def __init__(self, username, password, mqtt_topic, hass):
        """Initialize the data object."""
        from trackimo_lib import Trackimo
        self.hass = hass
        self.value = None
        self.mqtt_topic = mqtt_topic
        self.mqtt_retain = True
        self.mqtt_qos = 0

        self._config = {
            'trackimo': {
                'username': username,
                'password': password
            }
        }
        _LOGGER.warning("Connecting to trackimo")
        self._trackimo = Trackimo(self._config, loop=hass.loop, logger=_LOGGER)
        self._trackimo.addListener(self.locationUpdates)
        self._trackimo.connect()
        _LOGGER.warning("Connected to trackimo")
        _LOGGER.warning("Trackimo token: %s" % self._trackimo._token)
        # try:
        #     self._trackimo.monitor()
        # except Exception as e:
        #     _LOGGER.error("error: %s", e)
        #     self.value = CONST_STATE_ERROR

    @asyncio.coroutine
    def locationUpdates(self, locations=None, ts=None):
        _LOGGER.warning("Have trackimo location data: %s" %
                        json.dumps(locations))
        alphaonly = re.compile('[\W_]+', re.UNICODE)
        for deviceId in locations:
            device = locations[deviceId]
            mqttPacket = OwntracksMQTT()
            topic = 'owntracks/'
            if 'name' in device:
                topic += alphaonly.sub('', device['name'].lower())
            else:
                topic += deviceId
            topic += '/trackimo'
            mqttPacket.conn = 'm'
            if 'lat' in device:
                mqttPacket.lat = device['lat']
            if 'lng' in device:
                mqttPacket.lon = device['lng']
            if 'time' in device:
                mqttPacket.tst = device['time']
            elif 'ts' in device:
                mqttPacket.tst = device['ts']
            if 'battery' in device:
                mqttPacket.batt = device['battery']
            if 'speed' in device:
                mqttPacket.vel = device['speed']
            if 'altitude' in device:
                mqttPacket.alt = device['altitude']
            _LOGGER.warning(mqttPacket.json())
            self.save_payload_to_mqtt(topic, mqttPacket.json())

    def update(self):
        _LOGGER.warning("Getting location updates from trackimo")
        self.value = CONST_STATE_RUNNING
        try:
            self._trackimo.updateLocations()
        except Exception as e:
            _LOGGER.error("error: %s" % e)
            self.value = CONST_STATE_ERROR
        self.value = CONST_STATE_SLEEPING

    def save_payload_to_mqtt(self, topic, payload):

        try:
            """mqtt.async_publish ( self.hass, topic, payload, self.mqtt_qos, self.mqtt_retain )"""
            _LOGGER.warning("topic: %s", topic)
            _LOGGER.warning("payload: %s", payload)
            mqtt.publish(self.hass, topic, payload,
                         self.mqtt_qos, self.mqtt_retain)
        except Exception as e:
            _LOGGER.error("Unable to send MQTT: %s" % e)
