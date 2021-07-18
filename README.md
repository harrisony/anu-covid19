Cheeky little app to parse the [Confirmed COVID-19 cases in the ANU community](https://www.anu.edu.au/news/all-news/confirmed-covid19-cases-in-our-community) page and spit out a REST API.

Mainly for use in my [home-assistant](https://www.home-assistant.io/) install

```yaml
sensor:
  - platform: rest
    resource: "https://anu-covid19.heisenbean.coffee/community-cases"
    name: ANU COVID-19 cases
    unit_of_measurement: people
    #icon_template: mdi:emoticon-sad-outline
    scan_interval: 1800
    value_template: "{{ value_json.count }}"
    json_attributes:
      - cases
  - platform: rest
    resource: "https://anu-covid19.heisenbean.coffee/alert-level"
    name: ANU COVIDSafe Campus Alert
    #icon_template: mdi:emoticon-sad-outline
    scan_interval: 1800
    value_template: "{{ value_json.alert_level }}"
```
