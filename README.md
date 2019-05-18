
# Home Assistant Component - Trackimo to MQTT

> Allowing you to use your Trackimo devices outside of their web interface.

Communicates with [Trackimo](https://trackimo.com) via the [Trackimo API](https://dev.trackimo.com/docs/api/internal/v1/) and sends location data to MQTT.

This is a component for use with [Home Assistant](https://home-assistant.io/components/).

## Installation
Until somebody wants to integrate this into Home Assistant - you will need to download or clone this repo and place the `trackimo` folder in your `custom_components` folder. Configuration is all via Home Assistant's config files - so please don't try and edit the contents of the component itself.

## Configuration
Fairly simple configuration setting up the username, password and MQTT information.

```yaml
sensors:
  - platform: trackimo
    name: trackimo_family
    username: user@example.com		#Your Trackimo Username
    password: 5uP3rS3cUrE11			#Your Trackimo Password
    mqtt_topic: "trackimo/family"
```
