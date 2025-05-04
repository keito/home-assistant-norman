# Home Assistant integration for Norman smart blinds

This is an integration for Home Assistant for controlling Norman smart blinds. It provides control and status via **local network** to the Norman Hub (not to the cloud), and supports local push when the blinds' states change (e.g. if a remote is used).

It's currently only tested with the SmartDrape, but it should work well with any Norman blinds that use a bottom rail and middle rail (top down bottom up cellular, etc.) Pull requests and contributions of data to add new types of Norman covers are appreciated.

As with other kinds of blinds in Home Assistant, all position/tilt values are positive integers from 0 to 100.

## Actions
In addition to the standard position/tilt features of [Cover](https://www.home-assistant.io/integrations/cover/) entities, this integration also supports the following actions, for use in automations when you want to nudge the position/tilt of the blinds relative to their current position.

* `nudge_position` (takes one argument, `step`: positive for open, negative for close).
* `nudge_tilt` (takes one argument, `step`: behavior depends on the kind of blind; for SmartDrape, negative tilts left).

## Disclaimers
For interoperability; no vendor code included.
This project is unaffiliated with Norman. Use at your own risk; may void warranty.
